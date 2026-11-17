#!/usr/bin/env python3
"""workflow{action:"validate"}: dry-run of the door's validation pipeline —
no liveness ping, no writes. A bad graph returns errors:[{node,field,msg}] and
leaves the runs root and library untouched; a good graph returns ok + routes.
Hermetic (sandboxed HOME, fake launcher). Stdlib-only; PASS/FAIL lines; exit 0 = green.
"""
import importlib.util, json, os, shutil, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_validate"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
os.environ["DUCKWORK_HOME"] = str(HOME)
# Shelf-audit S3 (test_shelf_isolation_71.py): an in-process door writer must pin
# BOTH doors — WF_RUNS_ROOT env AND the plugin's settings.runs_root — since the
# owner setting outranks the env pin (09-30 pollution law).
os.environ["WF_RUNS_ROOT"] = str(HOME / "runs-pin")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "tests"))
spec = importlib.util.spec_from_file_location("hw_validate", str(root / "__init__.py"))
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71
_iso71.install(hw)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

def call(**a): return json.loads(hw.handle(a))

GOOD = {"name": "v-good", "nodes": [
    {"id": "a", "type": "agent", "goal": "LIST: go"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "ok?", "options": ["y", "n"]}]}

# V1 good graph -> ok + resolved_routes, nothing written
r = call(action="validate", graph=GOOD)
check("V1 ok", r.get("ok") is True, r)
check("V1 routes", "a" in (r.get("resolved_routes") or {}), r)
check("V1 no errors key leaks", r.get("errors") == [], r)
check("V1 nothing written", not (HOME / "workflows").exists() or
      not any((HOME / "workflows").glob("*")), list((HOME / "workflows").glob("*")))
check("V1 library untouched", not (HOME / "workflows" / "library").exists() or
      not any((HOME / "workflows" / "library").glob("*.json")))

# V2 bad graph -> errors, no writes
BAD = {"name": "v-bad", "bogus_key": 1, "nodes": [
    {"id": "a", "type": "agent", "goal": "go", "after": ["nope"]}]}
r = call(action="validate", graph=BAD)
check("V2 not ok", r.get("ok") is False, r)
errs = r.get("errors") or []
check("V2 error rows shaped", bool(errs) and all({"node", "field", "msg"} >= set(e) for e in errs), r)
check("V2 names both defects",
      any(e["field"] == "bogus_key" for e in errs) and
      any(e.get("node") == "a" and e["field"] == "after" or "nope" in e["msg"] for e in errs), r)
check("V2 no runs written", not (HOME / "workflows").exists() or
      not any(p for p in (HOME / "workflows").rglob("*") if p.is_file()))

# V3 unknown model is rejected here too (model/route policy stage), still no write
r = call(action="validate", graph={"name": "v-model", "nodes": [
    {"id": "a", "type": "agent", "goal": "go", "model": "not-a-real-model-zzz"}]})
check("V3 unknown model rejected", r.get("ok") is False and "model" in json.dumps(r), r)

# V4 graph_path source works, same no-write promise
gp = HOME / "g.json"
gp.write_text(json.dumps(GOOD), encoding="utf-8")
r = call(action="validate", graph_path=str(gp))
check("V4 graph_path ok", r.get("ok") is True, r)

# V5 no source -> honest error, not a crash
r = call(action="validate")
check("V5 needs a source", r.get("ok") is None and "source" in r.get("error", "").lower()
      or "graph" in r.get("error", "").lower(), r)

print("ALL PASS: validate action" if ok else "FAILURES: validate action")
sys.exit(0 if ok else 1)
