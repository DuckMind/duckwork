#!/usr/bin/env python3
"""Build examples/diagrams/README.md — the derived diagram table.

Owns that file wholesale (it lives beside the artifacts it describes; the
hand-authored map at examples/README.md is NOT touched — it carries jsonc
invocations other tests gate).

Stdlib-only. The table is derived: every row is computed from files on disk at
generation time — never hand-edited. Run after graph_diagram.py + render step.
"""
import hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from graph_diagram import example_graphs


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


QA_FIELDS = ("clipped", "legible", "chrome_free", "browser")


def qa_gates(dia, stem, cand):
    """Derive the gates column from the QA receipt body — never string memory.

    Twin of the census law: a row may claim `browser-check done` only if
    qa/<stem>.qa.json exists AND its expected_nodes equals the candidate's
    node count AND its verdicts are all true. Missing receipt -> honest
    `not-run`; lying receipt -> named red.
    """
    expected = len(cand["nodes"])
    qp = os.path.join(dia, "qa", stem + ".qa.json")
    base = "derived + rendered via vendored archify"
    if not os.path.exists(qp):
        return base + "; browser-check not-run — visual QA lap per diagram before edits land"
    qa = json.load(open(qp))
    missing = [f for f in QA_FIELDS if f not in qa]
    if missing or qa.get("expected_nodes") != expected:
        why = (f"missing fields {missing}" if missing else
               f"expected_nodes {qa.get('expected_nodes')} != candidate nodes {expected}")
        raise SystemExit(f"QA RED {stem}.qa.json: {why} — receipt disagrees with the"
                         " candidate; re-run the QA lap (named defendant: the receipt)")
    verdicts = ("clipped" if qa["clipped"] else "no-clip",
                "legible" if qa["legible"] else "ILLEGIBLE",
                "chrome-free" if qa["chrome_free"] else "CHROME-PRESENT")
    ok = (not qa["clipped"]) and qa["legible"] and qa["chrome_free"]
    tag = "browser-check done" if ok else "browser-check FAILED"
    return (f"{base}; {tag} ({qa['browser']}, {', '.join(verdicts)});"
            " receipts in qa/ (generator + renderer version-stamped)")


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ex = os.path.join(here, "examples")
    dia = os.path.join(ex, "diagrams")
    graphs = example_graphs(ex, dia)
    rows, pending_rows = [], []
    for g in graphs:
        stem = os.path.basename(g)[:-5]
        cand = os.path.join(dia, stem + ".candidate.json")
        stem_png = os.path.join(dia, stem + ".png")
        if not os.path.exists(cand):
            pending_rows.append(f"examples/{os.path.relpath(g, ex)}")
            continue
        c = json.load(open(cand))
        q = c["meta"].get("quality_profile", "standard")
        gates = qa_gates(dia, stem, c)
        rel = os.path.relpath(g, here)
        rows.append((f"examples/{os.path.relpath(g, ex)}",
                     f"[{stem}.png]({stem}.png)",
                     f"`{sha(cand)}`", f"`{sha(stem_png) if os.path.exists(stem_png) else '—'}`",
                     q, gates, rel))
    out = ["# examples/diagrams/ — derived diagram table",
           "",
           "Every template below ships with a diagram that is **derived from its",
           "graph bytes**, never drawn by hand (DIAGRAM LAW v1). The layout rule",
           "(lane/col/stack, compared bytes) is the **LAYOUT RULE paragraph in",
           "`scripts/graph_diagram.py`'s docstring** — one-source law: that",
           "paragraph is the spec, this README cites it, a contradiction between",
           "diagram and graph is a bug in that file (named defendant).",
           "Regenerate everything after editing any example:",
           "",
           "```sh",
           "python3 scripts/graph_diagram.py --all        # candidates (stdlib, deterministic)",
           "# render + shoot with the VENDORED archify (scripts/vendor/archify/, version in",
           "# ARCHIFY_VERSION — the only oven the repo owns; any machine with node >= 18:",
           "#   node scripts/vendor/archify/renderers/workflow/render-workflow.mjs \\",
           "#     examples/diagrams/<name>.candidate.json examples/diagrams/<name>.html",
           "#   # then screenshot examples/diagrams/<name>.html with any headless chromium",
           "#   # (chrome-headless-shell --headless --no-sandbox --screenshot=... works;",
           "#   #  strip the viewer chrome before saving the records png)",
           "#   # and record a QA lap per diagram at examples/diagrams/qa/<name>.qa.json:",
           "#   #  {browser, expected_nodes (= candidate nodes length), clipped, legible,",
           "#   #   chrome_free} — this table DERIVES the gates column from those receipts,",
           "python3 scripts/diagram_readme.py             # rebuild this table (derived)",
           "python3 scripts/graph_diagram.py --check --all # CI freshness gate: exit 1 on drift",
           "```",
           "",
           "| example | diagram | candidate sha256 | png sha256 | profile | gates |",
           "|---|---|---|---|---|---|"]
    for name, link, cs, hs, q, g_ in [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]:
        out.append(f"| {name} | {link} | {cs} | {hs} | {q} | {g_} |")
    out.append("")
    out.append("Cards (the two panels inside each diagram) are the ONLY hand-authored")
    out.append("diagram input; they live in `<name>.cards.json` beside the graph. Every")
    out.append("number in a card must be recomputable from the graph bytes it describes.")
    out.append("")
    out.append("Scope: every graph under `examples/` carries a conforming diagram.")
    out.append("Test fixtures (`tests/fixtures/`) are engine inputs consumed by test")
    out.append("code, not docs — no diagram (rung zero). Census command for the scope:")
    out.append(r"`git ls-tree -r --name-only HEAD | grep '\.json$' | grep -v '^graphify-out/'")
    out.append(r" | grep -v '^examples/diagrams/' | grep -v '\.cards\.json$'` —")
    out.append("every file whose parsed JSON has a non-empty `nodes` array must have a")
    out.append(f"table row or queue row in this table (receipt at build: examples/ {len(rows)+len(pending_rows)}")
    out.append(f"= {len(rows)} table + {len(pending_rows)} queue).")
    if pending_rows:
        out.append("")
        out.append("## Diagram queue (cards pending — generator skips, CI stays green)")
        out.append("")
        for p in sorted(pending_rows):
            out.append(f"- [ ] `{p}` — needs `<name>.cards.json`, then `--all` derives the row")
    out.append("")
    p = os.path.join(dia, "README.md")
    old = open(p).read() if os.path.exists(p) else ""
    if old != "\n".join(out) + "\n":
        open(p, "w").write("\n".join(out) + "\n")
        print(f"WROTE {p}")
    else:
        print(f"UNCHANGED {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
