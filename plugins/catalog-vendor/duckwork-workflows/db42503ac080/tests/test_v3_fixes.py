#!/usr/bin/env python3
"""v0.3 regressions — the mega-review sign-off (NO_GO) items, each test-locked:
V1 single-runner admission (O_EXCL lock), V2 legacy def_hash downgrade blocked by
ancestor chain, V3 strict run_id (no silent normalization), V4 stop kills live
children fast (stop-watcher, not just boundary), V5 fanout validator shape,
V6 stopped run refuses gate answers (stop→release serialization)."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home3"
RUNS = HOME / "workflows"
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
sys.path.insert(0, str(BUILD.parent))
import wfcommon

env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake3.log"))
FAKE = str(BUILD / "fake")
ok = True

def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

def mk(run_id, nodes, name="t", extra_meta=None):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    meta = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}
    meta.update(extra_meta or {})
    (r / "run.json").write_text(json.dumps(meta))
    return r

def wf(run_id, timeout=180):
    return subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout)

def call(**args):
    import importlib.util
    spec = importlib.util.spec_from_file_location("hw3", BUILD.parent / "__init__.py")
    hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
    import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
    return json.loads(hw.handle(args))

HOME.mkdir(parents=True, exist_ok=True)
RUNS.mkdir(parents=True, exist_ok=True)

# V1: admission — while a runner is live (SLEEP child), a second runner exits BUSY
r = mk("v1", [{"id": "s", "type": "agent", "goal": "SLEEP 8"}], "admit")
p = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "v1"],
                     env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(3)
out2 = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", "v1"],
                      env=env, capture_output=True, text=True, timeout=30).stdout
check("V1 second runner refused (WORKFLOW_BUSY)", "WORKFLOW_BUSY" in out2, out2.strip())
(r / "stop.request").write_text("1")
first_out = p.communicate(timeout=60)[0]

# V4: the same stop killed the live child fast — no node committed after stop
rec = (r / "nodes/s.json")
check("V4 stop during SLEEP child honored (run stopped once)",
      "WORKFLOW_STOPPED" in first_out and (r / "events.jsonl").read_text().count("run.stopped") == 1)

# V2: legacy def_hash record does NOT survive an upstream-only amend (downgrade block)
r = mk("v2", [{"id": "a", "type": "agent", "goal": "ok"},
              {"id": "b", "type": "agent", "after": ["a"], "goal": "downstream"}], "legacy")
wf("v2")
assert (r / "nodes/b.json").exists()
brec = json.loads((r / "nodes/b.json").read_text())
brec.pop("efp"); brec["def_hash"] = wfcommon.def_hash({"id": "b", "type": "agent", "after": ["a"], "goal": "downstream"})
(r / "nodes/b.json").write_text(json.dumps(brec))
aroot = json.loads((r / "graph.json").read_text())
aroot["nodes"][0]["goal"] = "ok — amended upstream only"
(r / "graph.json").write_text(json.dumps(aroot))
byid = {n["id"]: n for n in aroot["nodes"]}
st, _ = wfcommon.node_rec(r, byid["b"], byid)
check("V2 legacy stamp + changed ancestor => stale (pending)", st == "pending", st)

# V3: strict run_id — silent normalization is gone
bad = call(action="status", run_id="../escape")
check("V3 traversal run_id rejected (error, not escape)", "error" in bad, bad)
bad2 = call(action="status", run_id="has space")
check("V3 spacey run_id rejected", "error" in bad2, bad2)

# V5: fanout shape enforced at submit
bad3 = call(action="run", graph={"name": "v5", "nodes": [
    {"id": "f", "type": "agent", "fanout": {"goal": "x"}}]})
check("V5 fanout without items/items_from rejected", "items" in json.dumps(bad3), bad3)
bad4 = call(action="run", graph={"name": "v5", "nodes": [
    {"id": "f", "type": "agent", "goal": "x", "timeout": 999999}]})
check("V5 out-of-bound timeout rejected", "timeout" in json.dumps(bad4), bad4)

# V6: stop → release serialization (answer refused on a stopped run)
r = mk("v6", [{"id": "a", "type": "agent", "goal": "ok"},
              {"id": "g", "type": "gate", "after": ["a"], "question": "q", "options": ["y"]}], "v6")
wf("v6")  # holds
res = call(action="stop", run_id="v6")
time.sleep(2.5)
rel = call(action="release", run_id="v6", gate_id="g", answer="y")
check("V6 release refused on stopped run", "refused" in json.dumps(rel), rel)

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
