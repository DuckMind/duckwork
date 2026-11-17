#!/usr/bin/env python3
"""B2b probes (peer-review owed items): (A) empty-array query shares the save law,
(B) retain-on-overwrite refuses to read a corrupt previous envelope."""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_b2b"
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

G = {"name": "B2b Demo", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
call(action="save", graph=G, name="b2b", tags=["domain:net"])

# (A) one tags grammar: the empty array errors on library exactly like save (#50)
qa = call(action="library", tags=[])
check("B2b-A library(tags:[]) errors with the save-law message",
      "error" in qa and "1-10" in qa["error"], json.dumps(qa))
check("B2b-A2 omitted tags stays the match-all path",
      any(r.get("name") == "b2b" for r in call(action="library").get("library", [])))

# (B) corrupt previous envelope must NOT silently wipe tags on re-shelve
p = hw.library_root() / "b2b.json"
p.write_text("{not json!!")
rb = call(action="save", graph=G, name="b2b")
check("B2b-B re-shelve over corrupt entry fails closed", "error" in rb and "corrupt" in rb["error"], json.dumps(rb))
check("B2b-B2 corrupt bytes preserved on disk (retain-on-overwrite)",
      (hw.library_root() / "b2b.json").read_text() == "{not json!!")

# fail-the-process contract (est-3pvk): FAIL lines must surface in the exit code
print(f"\n{'ALL PASS' if ok else 'FAILED'} (b2b)")
sys.exit(0 if ok else 1)
