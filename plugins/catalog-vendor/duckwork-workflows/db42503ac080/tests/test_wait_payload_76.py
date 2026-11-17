#!/usr/bin/env python3
"""Item #76 (verb-roadmap/wait-payload): mid-run status/wait must NOT
re-ship every committed node output (measured 91% of a real wait payload).
Compact default while running/pending (output pointer: keys + bytes + how to
get the bytes); detail="full" opts in; terminal payloads are always full.
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home76"
if HOME.exists(): shutil.rmtree(HOME)
HOME.mkdir(parents=True)
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake76.log"))

spec = importlib.util.spec_from_file_location("door76", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

graph = {"name": "f76-payload", "nodes": [
    {"id": "a", "type": "agent", "goal": "SLEEP 1 task a"},
    {"id": "b", "type": "agent", "goal": "SLEEP 6 task b", "after": ["a"]},
]}
out = door.act_run({"graph": graph,
                    "name": "f76-payload"})
rid = out["run_id"]
r = HOME / "workflows" / rid

# wait until a is committed done AND b is live (compact window open)
st = None
for _ in range(80):
    st = door.act_status({"run_id": rid})
    if st.get("nodes", {}).get("a", {}).get("status") == "done" and \
       st.get("nodes", {}).get("b", {}).get("status") == "running":
        break
    time.sleep(0.25)
check("setup: a done + b running (live runner, compact regime)",
      st and st.get("status") == "running" and st["nodes"]["a"]["status"] == "done"
      and st["nodes"]["b"]["status"] == "running", json.dumps(st)[:200])

st = door.act_status({"run_id": rid})
an = st["nodes"]["a"]
check("mid-run default carries NO committed output bytes",
      "output" in an and isinstance(an["output"], dict)
      and an["output"].get("output_ptr", "").startswith("nodes"), json.dumps(an)[:220])
check("pointer carries keys + bytes so the parent can decide",
      isinstance(an["output"].get("output_keys"), list)
      and isinstance(an["output"].get("output_bytes"), int), json.dumps(an)[:220])
# scout-scale committed output (the 91%-of-payload shape from the field report)
ar = r / "nodes" / "a.json"
rec = json.loads(ar.read_text())
rec["output"] = {"result": "ok", "goal": "a" * 80,
                 "items": [{"i": i, "blob": ("x%d" % i) * 50} for i in range(60)]}
ar.write_text(json.dumps(rec))
w = door.act_wait({"run_id": rid, "timeout": 1})   # live runner -> yields quickly
check("mid-run act_wait stays compact too (same regime)",
      "note" in w and isinstance(w["nodes"]["a"].get("output"), dict)
      and w["nodes"]["a"]["output"].get("output_ptr", "").startswith("nodes"), json.dumps(w)[:220])
st_full = door.act_status({"run_id": rid, "detail": "full"})
af = st_full["nodes"]["a"]
check("detail=full attaches the real committed output",
      isinstance(af.get("output"), dict) and af["output"].get("result") == "ok"
      and "output_ptr" not in json.dumps(af), json.dumps(af)[:220])
# same-instant comparison: outputs were the bulk of the reported field payload
committed_bytes = len(json.dumps(rec["output"]))
c1 = len(json.dumps(door.act_status({"run_id": rid})))
c2 = len(json.dumps(door.act_status({"run_id": rid})))
f1 = len(json.dumps(door.act_status({"run_id": rid, "detail": "full"})))
f2 = len(json.dumps(door.act_status({"run_id": rid, "detail": "full"})))
check("compact payload sheds the committed bytes (same-instant max-of-2)",
      max(c1, c2) + int(0.8 * committed_bytes) <= min(f1, f2),
      f"compact={max(c1,c2)} full={min(f1,f2)} committed={committed_bytes}")

# terminal payload: always full, pointer gone
stt = None
for _ in range(120):
    stt = door.act_status({"run_id": rid})
    if stt.get("status") == "done": break
    time.sleep(0.5)
check("terminal run status is done", stt and stt.get("status") == "done", json.dumps(stt)[:160])
check("terminal payload carries outputs without asking for detail",
      isinstance(stt["nodes"]["a"].get("output"), dict)
      and stt["nodes"]["a"]["output"].get("result") == "ok"
      and isinstance(stt["nodes"]["b"].get("output"), dict), json.dumps(stt.get("nodes"))[:300])
print("ALL PASS" if not fails else "FAILURES PRESENT"); sys.exit(0 if not fails else 1)
