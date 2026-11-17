#!/usr/bin/env python3
"""Core-10 #89 review blocker: the EFFECTIVE synthesis prompt must not carry the
seat-only blindness prohibition.

The door bakes defaults.context ONTO every agent's own context (apply_graph_defaults
is an addition, not an override). A prohibition phrased for reviewers that lives in
defaults.context therefore reaches the synthesis seat too — which is REQUIRED to
merge and attribute the seat payloads — and the effective prompt contradicts itself.
Checking the raw `synthesis.context` field alone misses this (round-1 near-miss).

Regression law: seat-only rules live in per-seat `context`; defaults.context carries
only grounding rules every seat AND synthesis can obey. Asserted on the BAKED graph.
"""
import copy, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

SEAT_ONLY = "must not assume, guess, or address what they said"
MERGE_LAW = "You merge council verdicts"

g = json.load(open(ROOT / "examples" / "review" / "blind-council.workflow.json"))
baked = wfcommon.apply_graph_defaults(copy.deepcopy(g))
nodes = {n["id"]: n for n in baked["nodes"]}

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}"  + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1

# every reviewer seat, after baking, carries the seat-only blindness contract
for sid in ("seat-a", "seat-b", "seat-local"):
    ctx = nodes[sid].get("context", "")
    check(SEAT_ONLY in ctx, f"{sid} baked context keeps seat-only blindness contract")

# synthesis, after baking, must NOT — and must keep its merge mandate
sctx = nodes["synthesis"].get("context", "")
check(SEAT_ONLY not in sctx,
      "synthesis baked context free of seat-only prohibition (defaults is additive)")
check(MERGE_LAW in sctx, "synthesis keeps its merge mandate")

# defaults.context itself must be neutral enough for BOTH audiences
dctx = g["defaults"]["context"]
check(SEAT_ONLY not in dctx, "defaults.context carries no seat-only wording")

# terminology law: no undeclared field names in the synthesis instructions
check("open_items" not in sctx and "open_items" not in nodes["synthesis"].get("goal", ""),
      "synthesis prose names only schema fields (open_items removed; ledger is `risks`)")

# schema teeth: verify_list stays required
check("verify_list" in json.load(open(ROOT / "examples" / "review" / "blind-council.workflow.json"))
      ["nodes"][3]["schema"]["required"], "verify_list remains a required synthesis field")

print(f"test_example_blind_council: {ok} checks PASS")
