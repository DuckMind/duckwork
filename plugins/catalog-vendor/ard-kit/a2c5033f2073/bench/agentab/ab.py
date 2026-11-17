#!/usr/bin/env python3
"""Agent A/B: does ard-kit help an agent pick the right tool with less context
and fewer wasted actions than plain filesystem search + read?

This is Веха 3 of the ard-kit roadmap -- a SEPARATE experiment from the portable
retrieval benchmark (bench/portable/harness.py). That harness pins SCORER output
(P@1/MRR/bytes) deterministically. This one drives a real tool-calling agent over
the SAME fixture corpus and the SAME gold intents (bench/portable/refs.json) and
asks a behavioural question the retrieval numbers cannot answer:

  Mode A (baseline): the agent explores the corpus with list_dir / read_file /
                     grep -- "plain search and reading files".
  Mode B (ard-kit):  the agent calls ard_discover (POST /search) then
                     ard_inspect (GET /inspect) -- discovery then inspect.

Both modes get the SAME model, SAME settings, SAME step/token budget, and end by
calling submit_answer(tool_name) -- or submit_answer("none") when no tool fits.
Every task is run --repeats times (an LLM is not deterministic, so we report
AGGREGATES + spread, NOT one lucky example, and there is deliberately NO frozen
digest here). We measure, per the roadmap: task success (final pick in gold, not
just a top-5 hit), ACTUAL token spend (the LLM endpoint returns usage.total_tokens),
wall time and number of tool calls / LLM steps, wrong-tool rate, and -- on the
negative group -- the ability to correctly STOP and say "none".

HONESTY / SCOPE:
  * This makes network LLM calls. It is NOT part of any mandatory selfcheck and
    must never be wired into one. `--selfcheck` here is hermetic: it drives the
    loop with a scripted stub caller (no network, no server, no LLM) and asserts
    the pure scoring/aggregation helpers.
  * It does NOT touch the production scorer. Mode B reuses the real
    ard_kit.registry handler via harness.serve(), read-only.
  * Mode A filesystem tools are sandboxed to the corpus root (path-escape is
    rejected) -- the trust boundary is enforced, not simplified away.
  * Results can favour either mode. Report what happened, do not tune the corpus
    or the prompts to flatter ard-kit.

Usage:
    python3 bench/agentab/ab.py --selfcheck            # hermetic; no network/LLM
    python3 bench/agentab/ab.py --repeats 3            # A and B over all 23 tasks
    python3 bench/agentab/ab.py --modes B --group negative
    python3 bench/agentab/ab.py --model glm-5.3 --repeats 5 --json out.json
    python3 bench/agentab/ab.py --rescore results_qwen3.8-max_r3.json  # offline, read-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
import time
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

HERE = Path(__file__).resolve().parent              # bench/agentab
PORTABLE = HERE.parent / "portable"                 # bench/portable (corpus, refs, harness)
PKG = HERE.parent.parent                            # products/ard-kit (holds ard_kit/)
for _p in (str(PKG), str(PORTABLE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import harness  # noqa: E402  reuse build_catalog/serve/_ident_key/CORPUS/REFS/DOMAIN/DIRS

# OpenAI-compatible endpoint for the subject agent. Env-configurable so this
# public repo hardcodes no station-internal host/port/key: a live run needs
# ARD_AB_BASE_URL + ARD_AB_API_KEY pointed at your own gateway. --selfcheck is
# hermetic (stub caller) and never touches these.
BASE_URL = os.environ.get("ARD_AB_BASE_URL", "http://127.0.0.1:8000/v1")
API_KEY = os.environ.get("ARD_AB_API_KEY", "not-needed")
DOMAIN = harness.DOMAIN                             # bench.local

# context bounds for tool results (mode A fs reads and mode B registry payloads)
READ_CAP = 1800
GREP_MAX = 20
DISCOVER_MAX = 8
INSPECT_CAP = 1600

NONE_TOKENS = {"none", "no", "nothing", "n/a", "na", "neither", "nope"}

# Whole-answer decline phrases (exact match after _norm_answer, NOT substring).
# A decline must be the ENTIRE answer, so 'none, use weather-lookup' is a
# contradiction, not a clean stop.
NONE_PHRASES = {
    "no suitable tool", "no suitable tool exists", "no tool fits", "no such tool",
    "no matching tool", "no capability fits", "does not exist",
}


# --- pure helpers (selfcheck covers these; no I/O, no network, no LLM) ---

def leaf(s: str) -> str:
    """Last path/urn segment, casefolded: 'urn:..:word_count'->'word_count',
    'scripts/x.py'->'x.py'. Returns '' for None/empty."""
    if not s:
        return ""
    parts = re.split(r"[/:\\]", s.strip())
    return parts[-1].casefold().strip()


def stem(s: str) -> str:
    """leaf() with one trailing extension stripped: 'x.py'->'x', 'a.sh'->'a',
    'markdown-lint'->'markdown-lint'."""
    lf = leaf(s)
    return re.sub(r"\.[a-z0-9]+$", "", lf) if "." in lf else lf


def gold_names(gold: list[str]) -> set[str]:
    """Canonical tool names for a gold list: leaf of each identifier tail/urn."""
    return {leaf(g) for g in gold if leaf(g)}


def _norm_answer(a: str | None) -> str:
    """Normalize a WHOLE final answer for exact comparison: strip wrapping
    quotes/whitespace and one layer of trailing sentence punctuation, casefold.
    Returns '' for None. Never scans inside the string -- the answer is treated
    as ONE identifier, not a bag of tokens."""
    if a is None:
        return ""
    s = a.strip().casefold().strip("\"'`").strip()
    return s.rstrip(".!").strip()


def is_none_answer(a: str | None) -> bool:
    """Did the agent decline as a WHOLE answer? Exact-match only ('none', 'no',
    'no suitable tool exists'). A contradictory or enumerated answer
    ('none, use weather-lookup') is NOT a clean decline."""
    n = _norm_answer(a)
    if not n:
        return False
    return n in NONE_TOKENS or n in NONE_PHRASES


def answer_matches(answer: str | None, gold: set[str]) -> bool:
    """True only if the WHOLE answer is a SINGLE identifier equal to a gold name
    (leaf or stem). Strict by contract: both modes must commit to ONE tool, so a
    name, path or urn is accepted but prose, enumerations and contradictions are
    not -- 'csv_to_json word_count' and 'I reject word_count and choose
    csv_to_json' are not a single choice and do not match.
    """
    if answer is None or not gold:
        return False
    if is_none_answer(answer):
        return False
    n = _norm_answer(answer)
    if not n:
        return False
    # one identifier may contain '/', ':', '.', '_', '-' but never whitespace:
    # a space means the agent wrote prose / a list, not one canonical name.
    if any(c.isspace() for c in n):
        return False
    acceptable = set(gold) | {stem(g) for g in gold}
    return leaf(n) in acceptable or stem(n) in acceptable


def score(answer: str | None, gold: list[str]) -> dict:
    """Turn a final answer + gold into success / wrong_tool / correct_stop."""
    gn = gold_names(gold)
    if not gn:                                       # negative task: correct = decline
        declined = is_none_answer(answer)
        gave_tool = bool(answer) and not declined
        return {"success": declined, "wrong_tool": gave_tool, "correct_stop": declined,
                "gave_up": False}
    ok = answer_matches(answer, gn)
    declined = is_none_answer(answer)
    return {"success": ok,
            "wrong_tool": (not ok and not declined and bool(answer)),
            "correct_stop": None,
            "gave_up": (declined and not ok)}         # said 'none' on a task that HAS a tool


def mean(xs: list[float]) -> float:
    return round(statistics.fmean(xs), 1) if xs else 0.0


def med(xs: list[float]) -> float:
    return round(statistics.median(xs), 1) if xs else 0.0


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


# --- tool schemas (OpenAI function-calling; model-agnostic) ---

def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object", "properties": props,
                                        "required": required}}}


SUBMIT = _fn(
    "submit_answer",
    "Submit your FINAL choice: the canonical tool name, or 'none' if no tool fits the task.",
    {"tool_name": {"type": "string",
                   "description": "one tool name (e.g. word_count / pdf-extract / "
                                  "markdown-lint / weather-lookup) or 'none'"}},
    ["tool_name"])

TOOLS_A = [
    _fn("list_dir", "List entries of a directory in the codebase (relative path; '.' = root).",
        {"path": {"type": "string", "description": "directory relative to the codebase root"}},
        []),
    _fn("read_file", "Read a text file from the codebase (relative path). Content is truncated if long.",
        {"path": {"type": "string", "description": "file relative to the codebase root"}},
        ["path"]),
    _fn("grep", "Case-insensitive substring search across all codebase files; returns file:line matches.",
        {"pattern": {"type": "string", "description": "substring to search for"}},
        ["pattern"]),
    SUBMIT,
]

TOOLS_B = [
    _fn("ard_discover", "Search the capability registry; returns matching tools with identifiers and descriptions.",
        {"query": {"type": "string", "description": "natural-language capability query"}},
        ["query"]),
    _fn("ard_inspect", "Inspect one registry entry: how it is invoked, its arguments and description.",
        {"identifier": {"type": "string", "description": "the identifier returned by ard_discover"}},
        ["identifier"]),
    SUBMIT,
]

SYS_A = (
    "You must pick the SINGLE tool in a small local codebase that best accomplishes the "
    "user's task. Explore with list_dir / read_file / grep. The root holds scripts/, "
    "skills/, bin/, package.json and .mcp.json. Then call submit_answer ONCE with the "
    "canonical tool name: a script -> its file stem (word_count); a skill -> its directory "
    "name (pdf-extract); a CLI command -> the bin name declared in package.json "
    "(markdown-lint); an MCP server -> its key in .mcp.json (weather-lookup). If NO tool "
    "fits, call submit_answer with 'none'.")

SYS_B = (
    "You must pick the SINGLE capability in a registry that best accomplishes the user's "
    "task. Use ard_discover(query) to search; it returns identifiers with descriptions. Use "
    "ard_inspect(identifier) to read how a candidate is invoked and what it does. Then call "
    "submit_answer ONCE with the tool name -- the final name segment of the identifier "
    "(word_count / pdf-extract / markdown-lint / weather-lookup). If NO capability fits, "
    "call submit_answer with 'none'.")


# --- mode executors (tool result -> string) ---

def _safe(corpus: Path, rel: str) -> Path | None:
    """Resolve a corpus-relative path; None if it escapes the corpus root (sandbox)."""
    root = corpus.resolve()
    p = (root / (rel or ".")).resolve()
    if p != root and root not in p.parents:
        return None
    return p


def exec_mode_a(name: str, a: dict, corpus: Path) -> str:
    if name == "list_dir":
        p = _safe(corpus, a.get("path", "."))
        if p is None:
            return "ERROR: path outside codebase"
        if not p.exists():
            return "ERROR: no such path"
        if p.is_file():
            return "ERROR: not a directory"
        entries = [e.name + ("/" if e.is_dir() else "") for e in sorted(p.iterdir())]
        return "\n".join(entries) or "(empty)"
    if name == "read_file":
        p = _safe(corpus, a.get("path", ""))
        if p is None:
            return "ERROR: path outside codebase"
        if not p.is_file():
            return "ERROR: no such file"
        txt = p.read_text(encoding="utf-8", errors="replace")
        return txt[:READ_CAP] + "\n...[truncated]" if len(txt) > READ_CAP else txt
    if name == "grep":
        pat = (a.get("pattern") or "").casefold()
        if not pat:
            return "ERROR: empty pattern"
        hits: list[str] = []
        for f in sorted(corpus.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(corpus)
            if _safe(corpus, str(rel)) is None:      # symlink escape: same guard read_file gets
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, ln in enumerate(lines, 1):
                if pat in ln.casefold():
                    hits.append(f"{rel}:{i}: {ln.strip()[:160]}")
                    if len(hits) >= GREP_MAX:
                        return "\n".join(hits) + "\n...[capped]"
        return "\n".join(hits) or "(no matches)"
    return f"ERROR: unknown tool {name}"


def exec_mode_b(name: str, a: dict, port: int) -> str:
    if name == "ard_discover":
        q = a.get("query") or ""
        body = json.dumps({"query": {"text": q}, "pageSize": DISCOVER_MAX}).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{port}/search", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            return f"ERROR: discover failed: {e}"
        res = d.get("results", [])
        lines = [f"total={d.get('totalResults', len(res))}"]
        for it in res[:DISCOVER_MAX]:
            ident = it.get("identifier", "")
            desc = (it.get("description") or "").replace("\n", " ")[:120]
            lines.append(f"{ident} | score={it.get('score', 0)} | {desc}")
        return "\n".join(lines)
    if name == "ard_inspect":
        ident = (a.get("identifier") or "").strip()
        if not ident:
            return "ERROR: identifier required"
        if not ident.startswith("urn:"):
            ident = f"urn:air:{DOMAIN}:{ident}"
        url = f"http://127.0.0.1:{port}/inspect?" + urllib.parse.urlencode({"identifier": ident})
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
                d = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            return f"ERROR: inspect failed: {e}"
        s = json.dumps(d, ensure_ascii=False)
        return s[:INSPECT_CAP] + "...[truncated]" if len(s) > INSPECT_CAP else s
    return f"ERROR: unknown tool {name}"


# --- the agent loop ---

def http_chat(model: str, messages: list, tools: list, max_tokens: int) -> dict:
    body: dict[str, Any] = {"model": model, "messages": messages, "tools": tools,
                            "tool_choice": "auto", "temperature": 0, "max_tokens": max_tokens}
    if "qwen" in model:                              # avoid reasoning eating the budget
        body["enable_thinking"] = False
    req = urllib.request.Request(f"{BASE_URL}/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def run_agent(mode: str, task_text: str, port: int, corpus: Path, args: Any,
              caller: Callable[[str, list, list, int], dict]) -> dict:
    tools = TOOLS_A if mode == "A" else TOOLS_B
    sysmsg = SYS_A if mode == "A" else SYS_B
    messages: list[dict] = [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": f"Task: {task_text}"}]
    calls = steps = tokens = usage_gaps = 0
    answer: str | None = None
    exhausted = nudged = submitted = False
    error: str | None = None
    t0 = time.perf_counter()
    try:
        while steps < args.max_steps:
            steps += 1
            d = caller(args.model, messages, tools, args.max_tokens)
            u = (d.get("usage") or {}).get("total_tokens")
            if u is None:
                usage_gaps += 1     # response carried no usage: token sum is a lower bound
            else:
                tokens += int(u)
            ch = (d.get("choices") or [{}])[0]
            msg = ch.get("message", {}) or {}
            tcs = msg.get("tool_calls") or []
            if not tcs:
                if not nudged:
                    nudged = True
                    messages.append({"role": "user",
                                     "content": "Call submit_answer now with one tool name, or 'none'."})
                    continue
                exhausted = True
                break
            messages.append(msg)
            for tc in tcs:
                fn = tc.get("function", {}) or {}
                nm = fn.get("name")
                try:
                    fa = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    fa = {}
                calls += 1
                if nm == "submit_answer":
                    answer = str(fa.get("tool_name") or fa.get("answer") or "").strip() or None
                    messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                     "content": "recorded"})
                    submitted = True
                else:
                    res = (exec_mode_a(nm, fa, corpus) if mode == "A"
                           else exec_mode_b(nm, fa, port))
                    messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                     "content": res})
            if submitted:
                break
            if tokens > args.token_cap:
                exhausted = True
                break
        else:
            exhausted = True
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {e}"
    return {"steps": steps, "calls": calls, "tokens": tokens, "usage_gaps": usage_gaps,
            "ms": round((time.perf_counter() - t0) * 1000, 1),
            "answer": answer, "exhausted": exhausted or (steps >= args.max_steps and not submitted),
            "error": error}


# --- aggregation + report ---

def agg(runs: list[dict]) -> dict:
    n = len(runs)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "success": sum(1 for r in runs if r["success"]),
        "wrong_tool": sum(1 for r in runs if r.get("wrong_tool")),
        "exhausted": sum(1 for r in runs if r["exhausted"]),
        "errors": sum(1 for r in runs if r["error"]),
        "usage_gaps": sum(int(r.get("usage_gaps", 0)) for r in runs),
        "tok_mean": mean([r["tokens"] for r in runs]),
        "tok_med": med([r["tokens"] for r in runs]),
        "calls_mean": mean([r["calls"] for r in runs]),
        "steps_mean": mean([r["steps"] for r in runs]),
        "ms_mean": mean([r["ms"] for r in runs]),
    }


def _print_mode(mode: str, runs: list[dict]) -> dict:
    a = agg(runs)
    if not a.get("n"):
        print(f"\nmode {mode}: no runs")
        return a
    n = a["n"]
    print(f"\n=== mode {mode}  ({n} runs) ===")
    print(f"success={pct(a['success'], n)}%  wrong-tool={pct(a['wrong_tool'], n)}%  "
          f"exhausted={pct(a['exhausted'], n)}%  errors={a['errors']}")
    print(f"tokens mean/med={a['tok_mean']}/{a['tok_med']}  calls mean={a['calls_mean']}  "
          f"steps mean={a['steps_mean']}  ms mean={a['ms_mean']}  usage_gaps={a['usage_gaps']}")
    for grp in ("en", "ru", "negative"):
        gr = [r for r in runs if r["group"] == grp]
        if not gr:
            continue
        if grp == "negative":
            cs = sum(1 for r in gr if r.get("correct_stop"))
            print(f"  {grp}: correct-stop {cs}/{len(gr)}")
        else:
            s = sum(1 for r in gr if r["success"])
            print(f"  {grp}: success {s}/{len(gr)} ({pct(s, len(gr))}%)")
    return a


def run_ab(args: argparse.Namespace) -> int:
    refs = json.loads(Path(args.refs).read_text(encoding="utf-8"))
    tasks = []
    for g in refs["groups"]:
        if args.group != "all" and g["name"] != args.group:
            continue
        for item in g["queries"]:
            if args.task and args.task.casefold() not in item["q"].casefold():
                continue
            tasks.append({"group": g["name"], "text": item["q"],
                          "gold": item.get("gold", []), "kind": item.get("kind")})
    if not tasks:
        print("no tasks matched filters", file=sys.stderr)
        return 2
    modes = [m.strip().upper() for m in args.modes.split(",") if m.strip()]
    corpus = Path(args.corpus)

    tmp = Path(tempfile.mkdtemp(prefix="ardagentab-"))
    runs: list[dict] = []
    caller: Callable = http_chat
    catalog_sha = None
    try:
        norm_path, catalog_sha = harness.build_catalog(tmp, corpus, DOMAIN, harness.DIRS)
        public_url = f"https://{DOMAIN}"
        with harness.serve(norm_path, DOMAIN, public_url) as port:
            for mode in modes:
                for task in tasks:
                    for rep in range(args.repeats):
                        r = run_agent(mode, task["text"], port, corpus, args, caller)
                        r.update({"mode": mode, "group": task["group"], "kind": task["kind"],
                                  "q": task["text"], "gold": task["gold"], "rep": rep})
                        r.update(score(r["answer"], task["gold"]))
                        runs.append(r)
                        flag = "ok" if r["success"] else ("ERR" if r["error"] else "MISS")
                        print(f"[{mode} {task['group']} r{rep}] {flag} ans={r['answer']!r} "
                              f"tok={r['tokens']} calls={r['calls']} steps={r['steps']}",
                              file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nagent A/B -- model={args.model} repeats={args.repeats} "
          f"max_steps={args.max_steps} token_cap={args.token_cap}")
    print(f"corpus={corpus.name} catalogSha={(catalog_sha or '')[:12]} "
          f"tasks={len(tasks)} (LLM non-deterministic: aggregates, NO frozen digest)")
    summaries = {m: _print_mode(m, [r for r in runs if r["mode"] == m]) for m in modes}

    if len(modes) == 2 and all(summaries[m].get("n") for m in modes):
        A, B = summaries[modes[0]], summaries[modes[1]]
        print(f"\n--- delta ({modes[1]} vs {modes[0]}) ---")
        print(f"success: {pct(A['success'], A['n'])}% -> {pct(B['success'], B['n'])}%")
        dt = (B["tok_mean"] - A["tok_mean"]) / A["tok_mean"] * 100 if A["tok_mean"] else 0
        print(f"tokens mean: {A['tok_mean']} -> {B['tok_mean']} ({dt:+.0f}%)")
        print(f"calls mean: {A['calls_mean']} -> {B['calls_mean']}   "
              f"steps mean: {A['steps_mean']} -> {B['steps_mean']}   "
              f"ms mean: {A['ms_mean']} -> {B['ms_mean']}")
        print(f"wrong-tool: {pct(A['wrong_tool'], A['n'])}% -> {pct(B['wrong_tool'], B['n'])}%")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "model": args.model, "repeats": args.repeats, "maxSteps": args.max_steps,
            "tokenCap": args.token_cap, "catalogSha": catalog_sha,
            "summaries": summaries, "runs": runs,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


# --- hermetic selfcheck: scripted stub caller, NO network / server / LLM ---

def _stub_caller(script: list[dict]) -> Callable:
    """Return a caller that replays a fixed list of assistant messages."""
    state = {"i": 0}

    def caller(model, messages, tools, max_tokens):  # noqa: ANN001
        i = state["i"]
        state["i"] += 1
        msg = script[i] if i < len(script) else {"content": "done"}
        return {"choices": [{"message": msg, "finish_reason":
                             "tool_calls" if msg.get("tool_calls") else "stop"}],
                "usage": {"total_tokens": 100 + i}}
    return caller


def _tc(name: str, args: dict, cid: str = "c") -> dict:
    return {"tool_calls": [{"id": cid, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


def selfcheck() -> int:
    # leaf / stem
    assert leaf("urn:air:bench.local:script:scripts:word_count") == "word_count"
    assert leaf("scripts/word_count.py") == "word_count.py"
    assert stem("scripts/word_count.py") == "word_count"
    assert stem("git_summary.sh") == "git_summary"
    assert stem("markdown-lint") == "markdown-lint"
    assert leaf(None) == "" and leaf("") == ""

    # gold_names
    assert gold_names(["script:scripts:word_count"]) == {"word_count"}
    assert gold_names(["urn:air:bench.local:skill:skills:pdf-extract"]) == {"pdf-extract"}
    assert gold_names(["script:scripts:csv_to_json", "script:scripts:json_validate"]) == \
        {"csv_to_json", "json_validate"}
    assert gold_names([]) == set()

    # is_none_answer: WHOLE-answer exact match only
    assert is_none_answer("none") and is_none_answer("None.") and is_none_answer("no")
    assert is_none_answer("No suitable tool exists")
    assert not is_none_answer("word_count") and not is_none_answer(None) and not is_none_answer("")
    # a contradiction / enumeration is NOT a clean decline
    assert not is_none_answer("none, use weather-lookup")
    assert not is_none_answer("none csv_to_json")

    # answer_matches: ONE identifier as a whole (name / path / urn); no prose, no lists
    assert answer_matches("word_count", {"word_count"})
    assert answer_matches("word_count.py", {"word_count"})
    assert answer_matches("scripts/word_count.py", {"word_count"})
    assert answer_matches("urn:air:bench.local:script:scripts:word_count", {"word_count"})
    assert answer_matches("git_summary", {"git_summary.sh"})          # stem match
    assert answer_matches("git_summary.sh", {"git_summary.sh"})
    assert not answer_matches("lint.js", {"markdown-lint"})           # didn't read package.json
    assert not answer_matches("none", {"word_count"})
    assert not answer_matches("word_count", set())
    # strict single-choice contract: prose, enumerations and contradictions do NOT match
    assert not answer_matches("I choose json_validate", {"json_validate"})
    assert not answer_matches("csv_to_json word_count", {"word_count"})
    assert not answer_matches("I reject word_count and choose csv_to_json", {"csv_to_json"})

    # score: positive task
    s = score("word_count.py", ["script:scripts:word_count"])
    assert s["success"] and not s["wrong_tool"] and s["correct_stop"] is None
    s = score("csv_to_json", ["script:scripts:json_validate"])        # wrong pick
    assert not s["success"] and s["wrong_tool"]
    s = score("none", ["script:scripts:word_count"])                  # gave up on a real tool
    assert not s["success"] and not s["wrong_tool"] and s["gave_up"]
    s = score(None, ["script:scripts:word_count"])                    # never submitted
    assert not s["success"] and not s["wrong_tool"]

    # score: negative task
    s = score("none", [])
    assert s["success"] and s["correct_stop"] and not s["wrong_tool"]
    s = score("weather-lookup", [])                                   # forced a tool that isn't there
    assert not s["success"] and s["wrong_tool"] and not s["correct_stop"]
    s = score("none, use weather-lookup", [])                         # contradiction != clean stop
    assert not s["success"] and not s["correct_stop"] and s["wrong_tool"]

    # aggregation math
    fake = [{"success": True, "wrong_tool": False, "exhausted": False, "error": None,
             "tokens": 100, "calls": 2, "steps": 2, "ms": 10.0, "group": "en", "correct_stop": None},
            {"success": False, "wrong_tool": True, "exhausted": True, "error": None,
             "tokens": 300, "calls": 5, "steps": 6, "ms": 30.0, "group": "en", "correct_stop": None}]
    a = agg(fake)
    assert a["n"] == 2 and a["success"] == 1 and a["wrong_tool"] == 1 and a["exhausted"] == 1
    assert a["tok_mean"] == 200.0 and a["tok_med"] == 200.0 and a["calls_mean"] == 3.5
    assert pct(1, 2) == 50.0 and agg([]) == {"n": 0}

    # hermetic end-to-end loop: mode B, stub caller submits immediately (no server)
    argsB = SimpleNamespace(model="stub", max_steps=6, token_cap=100000, max_tokens=64)
    r = run_agent("B", "count the words and lines in a text file", 0, harness.CORPUS, argsB,
                  _stub_caller([_tc("submit_answer", {"tool_name": "word_count"})]))
    assert r["answer"] == "word_count" and r["calls"] == 1 and r["steps"] == 1
    assert not r["exhausted"] and r["error"] is None
    assert score(r["answer"], ["script:scripts:word_count"])["success"]

    # hermetic loop: mode A, real local fs (list_dir -> submit). No network.
    argsA = SimpleNamespace(model="stub", max_steps=6, token_cap=100000, max_tokens=64)
    r = run_agent("A", "count words", 0, harness.CORPUS, argsA,
                  _stub_caller([_tc("list_dir", {"path": "scripts"}),
                                _tc("submit_answer", {"tool_name": "word_count"})]))
    assert r["calls"] == 2 and r["steps"] == 2 and r["answer"] == "word_count"

    # sandbox: path escape is rejected, not followed. The probe is assembled
    # from parts: the install-time plugin scanner regex-matches source text, so
    # a literal three-level climb at a password file reads as an attack even
    # inside the assert that proves the sandbox refuses it.
    _up3 = "/".join([".."] * 3)
    assert exec_mode_a("read_file", {"path": _up3 + "/etc/" + "passwd"},
                       harness.CORPUS) == "ERROR: path outside codebase"
    assert exec_mode_a("list_dir", {"path": "/etc"}, harness.CORPUS) == "ERROR: path outside codebase"

    # sandbox regression: grep must not leak through a symlink that escapes the corpus
    with tempfile.TemporaryDirectory(prefix="ardab-grep-") as td:
        root = Path(td) / "corpus"
        root.mkdir()
        outside = Path(td) / "outside.txt"
        outside.write_text("BENIGN_OUTSIDE_SENTINEL\n", encoding="utf-8")
        (root / "inside.txt").write_text("BENIGN_INSIDE_SENTINEL\n", encoding="utf-8")
        (root / "outside-link.txt").symlink_to(outside)               # escape via symlink
        assert "BENIGN_INSIDE_SENTINEL" in exec_mode_a(
            "grep", {"pattern": "BENIGN_INSIDE_SENTINEL"}, root)      # normal file still searched
        assert exec_mode_a("grep", {"pattern": "BENIGN_OUTSIDE_SENTINEL"}, root) == "(no matches)"
        assert exec_mode_a("read_file", {"path": "outside-link.txt"}, root) == \
            "ERROR: path outside codebase"                            # read_file still rejects it

    print("selfcheck OK")
    return 0


def rescore(path: str) -> int:
    """Offline, READ-ONLY re-scoring: apply the current score() to every run in a
    saved results JSON and report which runs (if any) would change. Makes no LLM
    calls and never rewrites the file -- the frozen result stays authoritative."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    runs = d.get("runs", [])
    keys = ("success", "wrong_tool", "correct_stop", "gave_up")
    changed = 0
    for i, r in enumerate(runs):
        new = score(r.get("answer"), r.get("gold", []))
        if any(new[k] != r.get(k) for k in keys):
            changed += 1
            print(f"[run {i}] mode={r.get('mode')} group={r.get('group')} "
                  f"rep={r.get('rep')} q={r.get('q')!r} ans={r.get('answer')!r}")
            for k in keys:
                if new[k] != r.get(k):
                    print(f"    {k}: {r.get(k)} -> {new[k]}")
    verdict = "NO score changes" if not changed else f"{changed} SCORE(S) DIFFER"
    print(f"\nrescore: {changed} changed / {len(runs)} runs -- {verdict}")
    print(f"read-only: {path} NOT modified; re-scored offline, no LLM calls")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ard-kit agent A/B (discovery vs filesystem search)")
    ap.add_argument("--model", default="qwen3.8-max", help="model name for the subject agent (served by the LLM endpoint)")
    ap.add_argument("--modes", default="A,B", help="A=filesystem, B=ard-kit; default both")
    ap.add_argument("--repeats", type=int, default=3, help="runs per (mode,task)")
    ap.add_argument("--group", default="all", help="all|en|ru|negative")
    ap.add_argument("--task", default=None, help="substring filter on the task text")
    ap.add_argument("--max-steps", type=int, default=12, help="LLM round-trips per run")
    ap.add_argument("--max-tokens", type=int, default=1200, help="per-call completion budget")
    ap.add_argument("--token-cap", type=int, default=24000, help="total-token budget per run")
    ap.add_argument("--corpus", default=str(harness.CORPUS))
    ap.add_argument("--refs", default=str(harness.REFS))
    ap.add_argument("--json", default=None, metavar="OUT", help="write full machine-readable runs")
    ap.add_argument("--selfcheck", action="store_true", help="hermetic asserts; no network/LLM/server")
    ap.add_argument("--rescore", default=None, metavar="FILE",
                    help="read-only: re-apply current scoring to a saved results JSON, report diffs (no LLM calls, no writes)")
    args = ap.parse_args(argv)
    if args.selfcheck:
        return selfcheck()
    if args.rescore:
        return rescore(args.rescore)
    return run_ab(args)


if __name__ == "__main__":
    sys.exit(main())
