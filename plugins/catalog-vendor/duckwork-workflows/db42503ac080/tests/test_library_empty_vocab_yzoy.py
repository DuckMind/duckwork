#!/usr/bin/env python3
"""#146 item 2 (est-yzoy) zap r4: the empty-result cause is promised by the
FILTER, not earned by the vocabulary — an EMPTY vocab must not gate it.

zap's CHANGES read reproduced it: the `empty_cause` block (and the cause hint)
sat INSIDE `if vocab:`. A filtered query over a shelf with no vocabulary —
an empty shelf, a fully tagless/bare one, a wiped-to-`[]` erase, a
quarantined-only one — returned library:[] with `tag_match_counts` (est-bvg0
#251 moved the COUNTS onto the filter) but NO cause: the reader still had to
do the diagnosis itself, exactly the gap #146 item 2 exists to close. Law
asserted here: whenever an explicit tags filter returns an EMPTY result, the
response NAMES the cause — `empty_cause {spelling_miss, co_occurrence_starved}`
plus the cause-naming hint — whatever the vocab set holds, including the empty
set. Golden bytes stay sacred: an UNFILTERED tagless response grows neither
key; a NON-empty filtered response never grows `empty_cause`.
"""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_empty_vocab"
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

G = {"name": "Empty Vocab", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
WANT = ["use_case:code-review", "repo:nope"]

# V1 EMPTY shelf (no entries at all): vocab set is empty — the cause is still owed.
r = call(action="library", tags=WANT)
ec = r.get("empty_cause") or {}
check("V1 empty-vocab filtered empty names the cause (all terms at 0 = spelling_miss)",
      r.get("library") == [] and ec.get("spelling_miss") == WANT
      and ec.get("co_occurrence_starved") is False, json.dumps(r)[:300])
check("V1b the hint states the cause with a fix",
      "spelling miss" in r.get("hint", ""), r.get("hint", "")[-160:])

# V2 fully TAGLESS shelf (bare pre-#50 entries): vocab stays empty — owed.
call(action="save", graph=dict(G, name="Bare A"), name="bare-a")
r2 = call(action="library", tags=["domain:db"])
ec2 = r2.get("empty_cause") or {}
check("V2 tagless-shelf filtered empty names the cause",
      r2.get("library") == [] and ec2.get("spelling_miss") == ["domain:db"]
      and ec2.get("co_occurrence_starved") is False, json.dumps(r2)[:300])

# V3 ERASED shelf (hand-edited meta.tags [] — the only tags the shelf ever had):
# vocab empty again — owed.
call(action="save", graph=dict(G, name="Tagged T"), name="tagged-t", tags=["domain:net"])
P = hw.library_root() / "tagged-t.json"
e = json.loads(P.read_text()); e["meta"]["tags"] = []; P.write_text(json.dumps(e))
r3 = call(action="library", tags=["domain:net"])
ec3 = r3.get("empty_cause") or {}
check("V3 erased-tags shelf filtered empty names the cause",
      r3.get("library") == [] and ec3.get("spelling_miss") == ["domain:net"]
      and ec3.get("co_occurrence_starved") is False, json.dumps(r3)[:300])

# V4 QUARANTINED-only shelf (a garbage entry names itself; rows empty, vocab empty): owed.
shutil.rmtree(HOME, ignore_errors=True)
lib = hw.library_root(); lib.mkdir(parents=True, exist_ok=True)
(lib / "junk.json").write_text("{\"meta\": {\"tags\": [\"domain:db\"]}}")
r4 = call(action="library", tags=["domain:db"])
ec4 = r4.get("empty_cause") or {}
check("V4 quarantined-only shelf filtered empty names the cause",
      r4.get("library") == [] and r4.get("skipped") == ["junk.json"]
      and ec4.get("spelling_miss") == ["domain:db"], json.dumps(r4)[:300])

# V5 GOLDEN BYTES: the UNFILTERED tagless response is untouched — no tag_vocab,
# no tag_match_counts, no empty_cause (junk gone: a clean empty tagless shelf).
(lib / "junk.json").unlink()
r5 = call(action="library")
check("V5 unfiltered tagless keeps golden keys (no empty_cause / counts / vocab)",
      "empty_cause" not in r5 and "tag_match_counts" not in r5
      and "tag_vocab" not in r5 and set(r5) == {"library", "hint"}, json.dumps(sorted(r5)))

# V6 GOLDEN BYTES: a NON-empty filtered response never grows empty_cause,
# counts still ride (healthy vocab present — the pre-#146 shape).
shutil.rmtree(HOME, ignore_errors=True)
call(action="save", graph=dict(G, name="Healthy H"), name="healthy-h", tags=["domain:net"])
r6 = call(action="library", tags=["domain:net"])
check("V6 non-empty filtered response has no empty_cause (counts ride)",
      [x["name"] for x in r6.get("library", [])] == ["healthy-h"]
      and "empty_cause" not in r6
      and r6.get("tag_match_counts") == {"domain:net": 1}, json.dumps(r6)[:300])

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
