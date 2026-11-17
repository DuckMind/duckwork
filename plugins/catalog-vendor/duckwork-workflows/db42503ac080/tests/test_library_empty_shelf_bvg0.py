#!/usr/bin/env python3
"""est-bvg0 (PR #136 adversarial read, probe empty_shelf_filter): the promised
self-diagnosis must survive an EMPTY or fully-TAGLESS shelf.

SKILL.md:30 and references/grammar.md:39 promise: "`library` with tags:[...]
filters ALL-match and an empty result's tag_match_counts says which term
starved". __init__.py gates tag_match_counts behind `if vocab:` — on a shelf
with no tags anywhere (no entries, or entries with no tags at all) the vocab is
empty and a FILTERED query returns library:[] with no diagnosis, so an agent
cannot tell a spelling miss from an empty library. The unfiltered tagless
response must keep its pre-#70 golden bytes exactly (golden-bytes law).
"""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_bvg0"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
shutil.rmtree(HOME, ignore_errors=True)
sys.path.insert(0, str(BUILD))
import importlib.util
spec = importlib.util.spec_from_file_location("hw", str(BUILD.parent / "__init__.py"))
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as iso; iso.install(hw)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
def call(**a): return json.loads(hw.handle(a))
ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

G = {"name": "Shelf Demo", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}

# E1 EMPTY shelf + explicit tags filter: the diagnosis is promised even here —
# every queried term starved at 0 (spelling-miss shape; grammar.md:39).
r = call(action="library", tags=["use_case:code-review", "repo:nope"])
check("E1 empty shelf filtered self-diagnoses (library [] + counts all 0)",
      r.get("library") == [] and r.get("tag_match_counts") == {"use_case:code-review": 0, "repo:nope": 0},
      json.dumps({k: r.get(k) for k in ("library", "tag_match_counts")}))

# E2 fully-TAGLESS shelf (untagged entries exist): same promised diagnosis.
call(action="save", graph=dict(G, name="Untagged A"), name="untagged-a")
call(action="save", graph=dict(G, name="Untagged B"), name="untagged-b")
r2 = call(action="library", tags=["domain:db"])
check("E2 tagless shelf filtered self-diagnoses (counts name the starved term at 0)",
      r2.get("library") == [] and r2.get("tag_match_counts") == {"domain:db": 0},
      json.dumps({k: r2.get(k) for k in ("library", "tag_match_counts")}))

# E3 GOLDEN-BYTES: the UNFILTERED tagless response is untouched — no new keys,
# the 1.1 hint verbatim, no tag_vocab, no tag_match_counts.
r3 = call(action="library")
check("E3 unfiltered tagless keeps pre-#70 golden keys (no tag_vocab / tag_match_counts)",
      "tag_vocab" not in r3 and "tag_match_counts" not in r3
      and set(r3) == {"library", "hint"},
      json.dumps(sorted(r3)))

# E4 no false diagnosis once the shelf carries tags (the healthy path is the
# pre-existing one — counts must reflect the whole-library vocab, not zeros).
call(action="save", graph=dict(G, name="Tagged C"), name="tagged-c",
     tags=["use_case:code-review"])
r4 = call(action="library", tags=["use_case:code-review", "repo:absent"])
check("E4 tagged shelf still diagnoses per-vocab (count 1 + starved 0)",
      r4.get("library") == [] and r4.get("tag_match_counts") == {"use_case:code-review": 1, "repo:absent": 0},
      json.dumps({k: r4.get(k) for k in ("library", "tag_match_counts")}))
r5 = call(action="library", tags=["use_case:code-review"])
check("E4b a NONEMPTY filtered response keeps the pre-change shape (entry resolves, counts still ride per grammar.md)",
      [x["name"] for x in r5.get("library", [])] == ["tagged-c"]
      and r5.get("tag_match_counts") == {"use_case:code-review": 1},
      json.dumps({k: r5.get(k) for k in ("library", "tag_match_counts")}))

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
