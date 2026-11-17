#!/usr/bin/env python3
"""Measure the detector, and other products' rules, on the same labelled texts.

Protocol (the same for every detector):

1. Every detector gives each text a number (higher = more AI-like).
2. "Own rule": the detector's own published decision (ours: the surface
   threshold; yomiyasu: any finding; natural-japanese: machine score below 70,
   i.e. 要修正 or worse in its diagnose.md; extracted rule sets: any hit).
3. "Dev-tuned": the cut-off that catches the most AI texts on the dev + tune
   splits while flagging at most 10% of the human texts there, applied
   unchanged to the test split (the unseen holdout). Ours is tuned the same way only for this column; the
   plugin itself ships the fixed surface thresholds.

Usage:
    python eval/run_eval.py                       # ours only, test split
    python eval/run_eval.py --yomiyasu ../yomiyasu \
        --natural-japanese ../natural-japanese --nj-python /path/to/python-with-sudachipy \
        --baselines eval/baselines --json eval/results.json

Data lives in eval/data/<split>/<ai_ish|ai|human>/NNN_<surface>.txt (see eval/data/README.md).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
PACKAGE = "ja_writing_guard_plugin"


def load_plugin():
    if PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(PACKAGE, ROOT / "__init__.py",
                                                      submodule_search_locations=[str(ROOT)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(PACKAGE + ".detector")


SETS = {
    "A": ("ai_ish", "AI-ish texts (an LLM asked for typical generative-AI style) vs human"),
    "B": ("ai", "default AI output (an LLM writing as it normally does) vs human"),
}


def load_split(split: str, ai_dir: str = "ai_ish") -> list[dict]:
    items = []
    for label, folder in (("ai", ai_dir), ("human", "human")):
        meta = DATA / split / folder / "meta.json"
        strengths = {m["file"]: m.get("strength") for m in json.loads(meta.read_text(encoding="utf-8"))} if meta.exists() else {}
        for p in sorted((DATA / split / folder).glob("*.txt")):
            surface = p.stem.split("_", 1)[1]
            items.append({"id": f"{split}/{folder}/{p.name}", "label": label, "surface": surface,
                          "path": p, "text": p.read_text(encoding="utf-8"),
                          "strength": strengths.get(p.name)})
    return items


# ------------------------------------------------------------------ detectors

def ours(items):
    det = load_plugin()
    out = {}
    for it in items:
        r = det.check(it["text"], it["surface"])
        out[it["id"]] = {"value": r.score, "own": r.over_threshold, "verdict": r.needs_rewrite}
    return out


def yomiyasu(items, repo: Path):
    spec = importlib.util.spec_from_file_location("yomiyasu_lint", repo / "scripts" / "yomiyasu_lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = {}
    for it in items:
        r = mod.lint_text(it["text"])
        out[it["id"]] = {"value": 100 - r["score"], "own": not r["is_clean"]}
    return out


def natural_japanese(items, repo: Path, python: str):
    lint = repo / "skills" / "natural-japanese" / "scripts" / "lint.py"
    out = {}
    for it in items:
        genre = {"tech_doc": "tech", "sns": "essay", "chat": "essay"}.get(it["surface"], "business")
        proc = subprocess.run([python, str(lint), "--json", "--genre", genre, str(it["path"])],
                              capture_output=True, text=True, timeout=300)
        data = json.loads(proc.stdout or "{}")
        findings = data.get("findings", data if isinstance(data, list) else [])
        sev = {"critical": 8, "warn": 4, "info": 0.5}
        penalty = sum(sev.get(f.get("severity"), 0) for f in findings)
        penalty *= 1000 / max(len(it["text"]), 1000)
        machine = max(100 - penalty, 20)  # diagnose.md: 機械ベース
        out[it["id"]] = {"value": round(100 - machine, 2), "own": machine < 70}
    return out


def rule_set(items, path: Path):
    ns: dict = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    compiled = []
    for entry in ns["RULES"]:
        rid, pattern = entry[0], entry[1]
        try:
            compiled.append(re.compile(pattern, re.M))
        except re.error:
            continue
    out = {}
    for it in items:
        hits = sum(len(c.findall(it["text"])) for c in compiled)
        # density per 500 characters, so long texts are not flagged for length alone
        value = hits / math.sqrt(max(1.0, len(it["text"]) / 500))
        out[it["id"]] = {"value": round(value, 3), "own": hits > 0}
    return out


# ------------------------------------------------------------------- metrics

def confusion(items, preds) -> dict:
    tp = sum(1 for it in items if it["label"] == "ai" and preds[it["id"]])
    fn = sum(1 for it in items if it["label"] == "ai" and not preds[it["id"]])
    fp = sum(1 for it in items if it["label"] == "human" and preds[it["id"]])
    tn = sum(1 for it in items if it["label"] == "human" and not preds[it["id"]])
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "detection_rate": round(tp / max(1, tp + fn), 3),
            "false_positive_rate": round(fp / max(1, fp + tn), 3)}


def tune(dev_items, dev_scores, max_fpr=0.10):
    """Lowest cut-off whose dev false-positive rate stays at or under max_fpr."""
    values = sorted({v["value"] for v in dev_scores.values()})
    best = None
    for cut in values + [math.inf]:
        preds = {k: v["value"] >= cut for k, v in dev_scores.items()}
        c = confusion(dev_items, preds)
        if c["false_positive_rate"] <= max_fpr:
            if best is None or c["detection_rate"] > best[1]["detection_rate"]:
                best = (cut, c)
    return best[0]


def auc(items, scores) -> float:
    """Chance that a random AI text scores above a random human text (ties count half)."""
    ai = [scores[it["id"]]["value"] for it in items if it["label"] == "ai"]
    hu = [scores[it["id"]]["value"] for it in items if it["label"] == "human"]
    wins = sum((a > h) + 0.5 * (a == h) for a in ai for h in hu)
    return round(wins / max(1, len(ai) * len(hu)), 3)


def detection_at_fpr_on_test(items, scores, max_fpr=0.10) -> float:
    """Reference only: the cut-off is chosen on the test split itself (an upper bound)."""
    values = sorted({v["value"] for v in scores.values()}) + [math.inf]
    best = 0.0
    for cut in values:
        c = confusion(items, {k: v["value"] >= cut for k, v in scores.items()})
        if c["false_positive_rate"] <= max_fpr:
            best = max(best, c["detection_rate"])
    return best


def by_surface(items, preds):
    rows = {}
    for s in sorted({it["surface"] for it in items}):
        sub = [it for it in items if it["surface"] == s]
        rows[s] = confusion(sub, preds)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--yomiyasu", type=Path)
    ap.add_argument("--natural-japanese", type=Path)
    ap.add_argument("--nj-python", default=sys.executable)
    ap.add_argument("--baselines", type=Path, help="directory of rules_*.py extracted rule sets")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    runners = {"ja-writing-guard (this plugin)": ours}
    if args.yomiyasu:
        runners["yomiyasu"] = lambda items: yomiyasu(items, args.yomiyasu)
    if args.natural_japanese:
        runners["natural-japanese"] = lambda items: natural_japanese(items, args.natural_japanese, args.nj_python)
    if args.baselines:
        for p in sorted(args.baselines.glob("rules_*.py")):
            runners[p.stem[len("rules_"):]] = (lambda path: (lambda items: rule_set(items, path)))(p)

    results = {}
    for set_name, (ai_dir, title) in SETS.items():
        dev = load_split("dev", ai_dir) + load_split("tune", ai_dir)
        test = load_split("test", ai_dir)
        print(f"\n== Set {set_name}: {title}")
        results[set_name] = run_set(runners, dev, test)
    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return results


def run_set(runners, dev, test):
    results = {}
    print(f"tuning (dev+tune): {sum(i['label']=='ai' for i in dev)} AI / {sum(i['label']=='human' for i in dev)} human; "
          f"test: {sum(i['label']=='ai' for i in test)} AI / {sum(i['label']=='human' for i in test)} human")
    header = (f"{'detector':34s} | {'own rule: det / FP':>20s} | {'dev-tuned: det / FP':>20s} | "
              f"AUC  | det@FP<=10% (cut on test, ref.)")
    print(header)
    print("-" * len(header))
    for name, run in runners.items():
        d_scores, t_scores = run(dev), run(test)
        own = confusion(test, {k: v["own"] for k, v in t_scores.items()})
        cut = tune(dev, d_scores)
        tuned = confusion(test, {k: v["value"] >= cut for k, v in t_scores.items()})
        strength = {}
        for level in ("strong", "weak"):
            sub = [it for it in test if it["label"] == "ai" and it.get("strength") == level]
            if sub:
                hit = sum(1 for it in sub if t_scores[it["id"]]["own"])
                strength[level] = f"{hit}/{len(sub)}"
        extra = {}
        if "verdict" in next(iter(t_scores.values())):
            extra["with_register_policy"] = confusion(test, {k: v["verdict"] for k, v in t_scores.items()})
        results[name] = {"own_rule": own, "dev_tuned": tuned, "cutoff": cut, "own_by_strength": strength, **extra,
                         "auc_test": auc(test, t_scores),
                         "detection_at_fpr10_cutoff_chosen_on_test": detection_at_fpr_on_test(test, t_scores),
                         "own_by_surface": by_surface(test, {k: v["own"] for k, v in t_scores.items()}),
                         "scores": {k: v["value"] for k, v in t_scores.items()}}
        print(f"{name:34s} | {own['detection_rate']:>8.0%} / {own['false_positive_rate']:>8.0%}  "
              f"| {tuned['detection_rate']:>8.0%} / {tuned['false_positive_rate']:>8.0%}  "
              f"| {results[name]['auc_test']:.2f} | {results[name]['detection_at_fpr10_cutoff_chosen_on_test']:.0%}"
              + (f"  strong {strength.get('strong')} weak {strength.get('weak')}" if strength else ""))
    return results


if __name__ == "__main__":
    main()
