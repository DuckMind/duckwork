#!/usr/bin/env python3
"""#146 item 3 (est-yzoy): the erase path, pinned whole — erase-by-file-edit is
a STATE; every garbage stored shape fails closed.

87826ef landed the retain-on-presence door fix: a hand-edited `meta.tags: []` is
the deliberate ERASE state and a later omit-tags save carries it forward (envelope
intact), while a non-list stored value — including JSON `null`, which is falsy and
so fell through truthiness checks pre-fix — refuses with repair-or-delete. The
issue asked for BOTH stored shapes covered by tests. L8s/L8t in test_library.py
pin the [] state and a string; this file pins the whole erase surface as its own
regression: []-erase survives a resave, `null` is garbage (never resurrected,
never silently dropped to bare bytes), the refused save leaves the file untouched,
and the documented escape hatch (explicit save naming tags) repairs it.
"""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_erase_yzoy"
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

G = {"name": "Erase Yzoy", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
call(action="save", graph=G, name="e", tags=["domain:net"], description="keep")
P = hw.library_root() / "e.json"

# F1 the documented erase: hand-edited meta.tags [] survives the next omit-tags save
e = json.loads(P.read_text()); e["meta"]["tags"] = []; raw = json.dumps(e); P.write_text(raw)
r = call(action="save", graph=G, name="e")
e2 = json.loads(P.read_text())
check("F1 stored [] erase survives the resave (envelope + [] stay)",
      r.get("saved") == "e" and e2.get("meta", {}).get("tags") == [] and "graph" in e2,
      json.dumps(e2)[:220])
check("F2 the erase is VISIBLE — library row shows tags [] and still lists",
      any(x.get("name") == "e" and x.get("tags") == []
          for x in call(action="library").get("library", [])))

# F3 the null shape: garbage, never the erase state — refuse, bytes untouched
e3 = json.loads(P.read_text()); e3["meta"]["tags"] = None
raw3 = json.dumps(e3); P.write_text(raw3)
r3 = call(action="save", graph=G, name="e")
check("F3 stored meta.tags null fails closed (never resurrect, never drop to bare)",
      "error" in r3 and "not a list" in r3["error"] and "null" not in json.dumps(r.get("saved", "")),
      json.dumps(r3)[:220])
check("F3b the refused resave left the null bytes untouched", P.read_text() == raw3)

# F4 escape hatch: an explicit save naming tags repairs the null-garbage entry
r4 = call(action="save", graph=G, name="e", tags=["domain:db"])
e4 = json.loads(P.read_text())
check("F4 explicit save repairs a null-garbage entry",
      r4.get("saved") == "e" and e4.get("meta", {}).get("tags") == ["domain:db"],
      json.dumps(e4)[:220])

# F5 the erased state survives that repair-path resave chain too (no resurrection)
e5 = json.loads(P.read_text()); e5["meta"]["tags"] = []; raw5 = json.dumps(e5); P.write_text(raw5)
r5 = call(action="save", graph=dict(G, description="re-shelved"), name="e")
e6 = json.loads(P.read_text())
# the incoming graph states its own description -> fresh wins over carried meta
# (established law); the erase state must still ride.
check("F5 erase stays erased across description-carrying resaves",
      e6.get("meta", {}).get("tags") == []
      and "graph" in e6
      and (e6.get("meta", {}).get("description") or e6["graph"].get("description")) == "re-shelved",
      json.dumps(e6)[:220])

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
