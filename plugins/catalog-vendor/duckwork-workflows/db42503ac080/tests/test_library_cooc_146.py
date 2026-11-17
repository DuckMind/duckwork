#!/usr/bin/env python3
"""#146 item 2 (peer review): the empty-result self-diagnosis must
distinguish SPELLING misses from CO-OCCURRENCE starvation ACROSS MULTIPLE TERMS.
Committed regression for the probe behavior: each queried term present
library-wide yet never together must yield 0 rows with per-term counts that
prove existence (a filter returning 0 that looks alive); a typo term must
count 0 (spelling miss); a compound query mixes both shapes."""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_cooc"
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

G = {"name": "Cooc Demo", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
# net+triage | db+triage | net+testing — every pair below is individually present,
# together never, or a pure spelling miss.
call(action="save", graph=G, name="x", tags=["domain:net", "use_case:triage"])
call(action="save", graph=G, name="y", tags=["domain:db", "use_case:triage"])
call(action="save", graph=G, name="z", tags=["domain:net", "use_case:testing"])

r = call(action="library", tags=["domain:db", "use_case:testing"])
check("C1 co-occurrence starvation: 0 rows, both terms exist",
      r.get("library") == [] and r.get("tag_match_counts") == {"domain:db": 1, "use_case:testing": 1},
      json.dumps({k: r.get(k) for k in ("library", "tag_match_counts")}))

r2 = call(action="library", tags=["domain:dbb"])
check("C2 spelling miss: term at 0 names itself",
      r2.get("library") == [] and r2.get("tag_match_counts") == {"domain:dbb": 0},
      json.dumps({k: r2.get(k) for k in ("library", "tag_match_counts")}))

r3 = call(action="library", tags=["domain:net", "use_case:testing", "repo:absent"])
check("C3 compound mixes both causes in one response",
      r3.get("library") == [] and r3.get("tag_match_counts") == {"domain:net": 2, "use_case:testing": 1, "repo:absent": 0},
      json.dumps({k: r3.get(k) for k in ("library", "tag_match_counts")}))

r4 = call(action="library", tags=["domain:net", "use_case:testing"])
check("C4 the co-occurring pair still resolves (no false starvation)",
      [x["name"] for x in r4.get("library", [])] == ["z"],
      json.dumps([x.get("name") for x in r4.get("library", [])]))

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
