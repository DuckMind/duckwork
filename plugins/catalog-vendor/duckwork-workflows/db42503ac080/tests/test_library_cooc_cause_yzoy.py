#!/usr/bin/env python3
"""#146 item 2 (est-yzoy): an EMPTY multi-term query must NAME the killer.

tag_match_counts lets a human infer the cause; it does not state it. When
EVERY queried term exists library-wide yet zero rows return, the response says
only {term: 1, term: 1} and leaves the reader to do the co-occurrence math —
and it never distinguishes a spelling-miss term from a co-occurrence starve in
one machine-readable field. Law asserted: a filtered EMPTY result carries
`empty_cause` naming it — `spelling_miss` lists the queried terms at 0 (the
killers you can fix by re-spelling); when NO term is at 0, `co_occurrence_starved`
is true and the hint says so, naming the rarest term as the one to drop. A
NON-empty filtered result never grows the key (golden bytes), and an unfiltered
call never carries it."""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_cooc_cause"
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

G = {"name": "Cooc Cause", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
call(action="save", graph=G, name="x", tags=["domain:net", "use_case:triage"])
call(action="save", graph=G, name="y", tags=["domain:db", "use_case:triage"])
call(action="save", graph=G, name="z", tags=["domain:net", "use_case:testing"])

# E1 pure co-occurrence starvation: both terms exist (1, 1), never together
r = call(action="library", tags=["domain:db", "use_case:testing"])
ec = r.get("empty_cause") or {}
check("E1 co-occur starve names itself, no spelling-miss terms",
      r.get("library") == [] and ec.get("co_occurrence_starved") is True
      and ec.get("spelling_miss") == [], json.dumps(r)[:300])
check("E1b the hint states the co-occurrence cause with a fix",
      "co-occur" in r.get("hint", ""), r.get("hint", ""))

# E2 spelling miss among a compound query names the ZERO term as the killer
r2 = call(action="library", tags=["domain:net", "use_case:testing", "repo:absent"])
ec2 = r2.get("empty_cause") or {}
check("E2 spelling-miss term named as killer",
      r2.get("library") == [] and ec2.get("spelling_miss") == ["repo:absent"]
      and ec2.get("co_occurrence_starved") is False, json.dumps(r2)[:300])

# E3 both causes at once: one zero term AND a never-together pair
r3 = call(action="library", tags=["domain:db", "use_case:testing", "note:ghost"])
ec3 = r3.get("empty_cause") or {}
check("E3 mixed query still names the spelling miss, no false starve claim",
      ec3.get("spelling_miss") == ["note:ghost"] and ec3.get("co_occurrence_starved") is False,
      json.dumps(r3)[:300])

# E4 golden-bytes law: a NON-empty filtered response never grows empty_cause
r4 = call(action="library", tags=["domain:net", "use_case:testing"])
check("E4 non-empty filtered result has no empty_cause key",
      [x["name"] for x in r4.get("library", [])] == ["z"] and "empty_cause" not in r4,
      json.dumps(list(r4)))

# E5 unfiltered call never carries it
r5 = call(action="library")
check("E5 unfiltered response has no empty_cause key", "empty_cause" not in r5,
      json.dumps(list(r5)))

# E6 the counts stay as the quantitative companion (no regression of #70)
check("E6 tag_match_counts still rides the empty response",
      r.get("tag_match_counts") == {"domain:db": 1, "use_case:testing": 1},
      json.dumps(r.get("tag_match_counts")))

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
