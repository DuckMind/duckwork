#!/usr/bin/env python3
"""End-to-end test of the `workflow` tool door against fake duckwork."""
import importlib.util, json, os, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(BUILD / "home")
os.environ["WF_RUNS_ROOT"] = str(BUILD / "home" / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
sys.path.insert(0, str(BUILD))          # import 'duckwork-workflows' isn't identifier-safe -> load by path
spec = importlib.util.spec_from_file_location("hw", BUILD.parent / "__init__.py")
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

def call(**a):
    return json.loads(hw.handle(a))

G = {"name": "door-test", "nodes": [
    {"id": "plan", "type": "agent", "goal": "LIST: go"},
    {"id": "fan", "type": "agent", "after": ["plan"], "fanout": {"items_from": "plan.result", "goal": "handle {item}"}},
    {"id": "g1", "type": "gate", "after": ["fan"], "question": "ship?", "options": ["yes", "no"]},
    {"id": "synth", "type": "agent", "after": ["g1"], "goal": "combine"},
]}

r = call(action="run", graph=G)
rid = r.get("run_id"); check("run launches", bool(rid), r)
st = call(action="wait", run_id=rid, timeout=60)
check("wait lands on held gate", st.get("status") == "held" and st.get("gate", {}).get("id") == "g1",
      json.dumps({k: st.get(k) for k in ('status','gate','note')}))
rel = call(action="release", run_id=rid, gate_id="g1", answer="yes")
check("release auto-resumes", rel.get("ok") and rel.get("auto_resumed"), rel)
st = call(action="wait", run_id=rid, timeout=60)
check("wait lands on done", st.get("status") == "done", json.dumps({k: st.get(k) for k in ('status','note')}))
check("all 4 nodes done", st.get("done") == 4, st)
check("summary written", (BUILD / "home/workflows" / rid / "summary.md").exists())

# steer on finished node reports honestly
s = call(action="steer", run_id=rid, node="synth", text="more please")
check("steer finished-node rejected without queuing", s.get("ok") is False
      and "done" in s.get("error", "") and not (BUILD / "home/workflows" / rid / "inbox.jsonl").exists(), s)

# amend after done -> replays, gate RE-holds (def unchanged but gate consumed? gate was consumed with _def match -> stays done; synth done -> run done again)
g2 = json.loads(json.dumps(G)); g2["nodes"][3]["goal"] = "combine v2"
am = call(action="amend", run_id=rid, graph=g2)
check("amend accepted", am.get("ok"), am)
st = call(action="wait", run_id=rid, timeout=60)
check("amended synth re-ran, run done again", st.get("status") == "done" and
      "v2" in json.dumps(st["nodes"]["synth"]["output"]), json.dumps(st.get("nodes", {}).get("synth")))

# stop
r3 = call(action="run", graph={"name": "stopme", "nodes": G["nodes"]})
time.sleep(0.4)
sp = call(action="stop", run_id=r3["run_id"])
time.sleep(1.5)
st = call(action="status", run_id=r3["run_id"])
check("stop lands", sp.get("ok") and st.get("status") in ("stopped", "running") and st.get("runner_live") == False,
      json.dumps({k: st.get(k) for k in ('status','runner_live')}))

# list
ls = call(action="list")
check("list sees runs", any(x["run_id"] == rid for x in ls.get("runs", [])), ls)

# bad graphs rejected
check("cycle rejected", "cycle" in json.dumps(call(action="run", graph={"name":"x","nodes":[
    {"id":"a","type":"agent","goal":"g","after":["b"]},{"id":"b","type":"agent","goal":"g","after":["a"]}]})))

# dashboard read-model matches
spec2 = importlib.util.spec_from_file_location("hwapi", BUILD.parent / "dashboard" / "plugin_api.py")
api = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(api)
v = api._view(BUILD / "home/workflows" / rid, full=True)
check("dashboard view consistent", v and v["status"] == "done" and len(v["nodes"]) == 4 and v["events"],
      json.dumps({k: v.get(k) for k in ('status','nodes')}))

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
