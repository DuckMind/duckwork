#!/usr/bin/env python3
"""Regression suite from the mega-review fleet: each test is a mutant that USED to
survive. Run from the tests dir with plain python3 — sandboxed, no API calls."""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home"
RUNS = HOME / "workflows"
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
sys.path.insert(0, str(BUILD.parent))
import wfcommon

env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake.log"))
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE
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

def wf(run_id):
    return subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=120).stdout.strip()

# door-side helper (used by door tests below and by R4a submit-validation)
import importlib.util
_spec = importlib.util.spec_from_file_location("hw", BUILD.parent / "__init__.py")
hw = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

def call(**a):
    return json.loads(hw.handle(a))

def answer(r, gid, val="yes", graph=None):
    g = graph or json.loads((r / "graph.json").read_text())
    byid = {n["id"]: n for n in g["nodes"]}
    h = wfcommon.efp(byid, byid[gid])
    (r / "gates" / f"{gid}.json").write_text(json.dumps({"answer": val, "_def": h, "fp_rule_version": wfcommon.FP_RULE_VERSION}))

(BUILD / "fake.log").write_text("")

# R1: UPSTREAM-ONLY amend must invalidate downstream (the headline bug)
nodes = [
    {"id": "a", "type": "agent", "goal": "LIST: go"},
    {"id": "b", "type": "agent", "after": ["a"], "goal": "downstream"},
]
r = mk("r1", nodes)
wf("r1")
first_b = json.loads((r / "nodes/b.json").read_text())
g = json.loads((r / "graph.json").read_text())
g["nodes"][0]["goal"] = "LIST: go CHANGED"          # change ONLY the upstream
(r / "graph.json").write_text(json.dumps(g))
wf("r1")
rb = json.loads((r / "nodes/b.json").read_text())
ra = json.loads((r / "nodes/a.json").read_text())
check("R1 upstream amend: a re-ran", ra["output"]["result"] != "ok" or "CHANGED" in json.dumps(ra), json.dumps(ra))
check("R1 downstream b invalidated and re-ran with fresh upstream",
      rb.get("efp") != first_b.get("efp"), json.dumps(rb))

# R2: stale gate answer (wrong _def) must NOT auto-accept — gate re-holds
r = mk("r2", nodes + [{"id": "g", "type": "gate", "after": ["b"], "question": "q"}])
wf("r2")
(r / "gates/g.json").write_text(json.dumps({"answer": "old-yes", "_def": "deadbeef00000000"}))
out = wf("r2")
check("R2 stale gate answer forces re-hold", "HELD r2 g" in out, out)
answer(r, "g", "fresh")
check("R2 fresh answer releases", wf("r2").startswith("WORKFLOW_DONE r2"))

# R3: child exits non-zero WITH prose stdout => node failed, not false-done
r = mk("r3", [{"id": "c", "type": "agent", "goal": "CRASHME please"}])
out = wf("r3")
rec = json.loads((r / "nodes/c.json").read_text())
check("R3 rc!=0 prose is NOT committed done", out.startswith("WORKFLOW_FAILED r3 (c)") and rec["status"] == "failed",
      json.dumps(rec))

# R4: two-layer 'when' safety — malformed syntax is REJECTED at validation (submit
# and at runner startup, loudly), and a runtime type-error holds the gate (fail-safe).
# A gate can never be silently skipped by a broken expression.
bad_when = call(action="run", graph={"name": "r4", "nodes":
            [{"id": "b", "type": "agent", "goal": "ok"},
             {"id": "g", "type": "gate", "after": ["b"], "question": "q", "when": "out['b'] typo((("}]})
check("R4a malformed when rejected at submit", "when" in json.dumps(bad_when), bad_when)
r = mk("r4", nodes + [{"id": "g", "type": "gate", "after": ["b"], "question": "q",
                       "when": "out['b'] typo((( "}])
out = wf("r4")
check("R4b malformed when on disk => run refused (graph invalid)", "WORKFLOW_FAILED" in out and "when" in out, out)
r = mk("r4b", [{"id": "b", "type": "agent", "goal": "WORDSWITHME"},
               {"id": "g", "type": "gate", "after": ["b"], "question": "q", "when": "out.b.verdict > 3"}])
out = wf("r4b")
check("R4c type-error when holds the gate (never skips)", "HELD r4b g" in out, out)

# R5: stop.request at an IDLE/held run must be consumable => stopped
r = mk("r5", nodes + [{"id": "g", "type": "gate", "after": ["b"], "question": "q"}])
wf("r5")                                   # holds (runner exits)
(r / "stop.request").write_text("1")
out = wf("r5")
check("R5 stop honored at held run", out.startswith("WORKFLOW_STOPPED r5"), out)
(r / "stop.request").unlink() if (r / "stop.request").exists() else None

# door-side: import door for R6-R8
import importlib.util
spec = importlib.util.spec_from_file_location("hw", str(BUILD.parent / "__init__.py"))
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
def call(**a):
    return json.loads(hw.handle(a))

# R6: wait must RESPAWN a crashed/idle run (the lie-spinner fix)
G = {"name": "r6", "nodes": [{"id": "a", "type": "agent", "goal": "SLEEP 3"},
                             {"id": "b", "type": "agent", "after": ["a"], "goal": "after"}]}
res = call(action="run", graph=G)
rid = res["run_id"]
time.sleep(1.2)
pid = int((RUNS / rid / "wf.pid").read_text())
subprocess.run(["kill", "-9", str(pid)])    # simulate crash mid-wave (no terminal event)
st = call(action="wait", run_id=rid, timeout=60)   # this call must respawn+resume
check("R6 wait respawns dead mid-wave run and completes", st.get("status") == "done",
      json.dumps({k: st.get(k) for k in ('status', 'nodes')}))

# R7: stop while held through the DOOR (spawn-to-consume path)
res = call(action="run", graph={"name": "r7", "nodes": [{"id": "a", "type": "agent", "goal": "LIST: x"},
                                                        {"id": "g", "type": "gate", "after": ["a"], "question": "q"}]})
rid7 = res["run_id"]
st = call(action="wait", run_id=rid7, timeout=60)
check("R7 gate held", st.get("status") == "held", json.dumps(st.get("gate")))
sp = call(action="stop", run_id=rid7)
time.sleep(2)
st = call(action="status", run_id=rid7)
check("R7 stop at held gate => stopped", st.get("status") == "stopped", json.dumps({k: st.get(k) for k in ('status','nodes')}))

# R8: pid identity — a live NON-wf pid must read as not-alive
(r7 := RUNS / rid7)
(r7 / "wf.pid").write_text(str(os.getpid()))
check("R8 recycled/non-wf pid => runner_alive False", hw.runner_alive(r7) is False)

# R9: stop must be consumed so a FUTURE runner is not poisoned
(r7 / "wf.pid").unlink()
(r7 / "stop.request").write_text("1")
hw._spawn_runner(r7)
time.sleep(1.5)
check("R9 stop.request consumed by the respawn it summoned",
      not (r7 / "stop.request").exists() and json.loads(hw.handle({"action":"status","run_id":rid7}))["status"] == "stopped")

# R10: run_id collision cannot clobber (exclusive create)
base = json.loads((RUNS / rid7 / "graph.json").read_text())
a1 = call(action="run", graph={"name": "collide", "nodes": base["nodes"]})["run_id"]
a2 = call(action="run", graph={"name": "collide", "nodes": base["nodes"]})["run_id"]
check("R10 same-name runs get distinct ids", a1 != a2 and (RUNS / a1 / "nodes").exists() and (RUNS / a2 / "nodes").exists())

# R11: node id path-traversal rejected
bad = call(action="run", graph={"name": "bad", "nodes": [{"id": "../evil", "type": "agent", "goal": "x"}]})
check("R11 traversal node id rejected", "invalid node id" in json.dumps(bad), bad)

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
