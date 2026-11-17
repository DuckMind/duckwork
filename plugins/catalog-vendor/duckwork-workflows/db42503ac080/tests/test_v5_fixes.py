#!/usr/bin/env python3
"""Regression suite for signoff-v4 must-file items (v5). Each test must FAIL on
pre-v5 code. Run from the tests dir with plain python3.

S1  when-expression validation must be TOTAL and value-independent: literals and
    nested comparisons can never TypeError mid-parse, so trailing tokens are always
    caught; a syntactically valid expr must not crash startup.
S2  The shared READ MODEL must survive a broken 'when': every consumer (status/
    list/_view) shows held + when_error instead of raising.
S3  Cancellation admission at the spawn boundary: stop with concurrency=1 must
    launch exactly the in-flight child, never the queued ones; same for fanout;
    zero spawns after _stop across a forced interleave.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home5"
RUNS = HOME / "workflows"
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
sys.path.insert(0, str(BUILD.parent))
import wfcommon as W

env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake5.log"))
FAKE = str(BUILD / "fake")
ok = True

def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

def mk(run_id, nodes, name="t", **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf(run_id):
    return subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=120).stdout.strip()

shutil.rmtree(HOME, ignore_errors=True)
(BUILD / "fake5.log").write_text("")

# ---- S1: total, value-independent validation -----------------------------------
for e, why in [("1 > 'z')", "literal cmp masks trailing paren"),
               ("(out.a.result == None) > 'z')", "nested literal cmp masks trailing"),
               ("'a' >= 2 and out.x)", "literal cmp in and-chain, unbalanced paren")]:
    err = W.when_expr_ok(e)
    check(f"S1a rejects {e!r} ({why})", err is not None, str(err))
errs_before = W.validate_graph([{"id": "g", "type": "gate", "when": "1 > 'z'"}])
check("S1b valid literal expr accepted at submit (no crash)", errs_before is None, str(errs_before))
r = mk("s1", [{"id": "g", "type": "gate", "when": "1 > 'z'", "question": "q"}])
r2 = mk("s1b", [{"id": "g", "type": "gate", "when": "out.a.missing > 3", "question": "q"}])
# upstream agent so the gate is ready
(r2 / "graph.json").write_text(json.dumps({"name": "s1b", "nodes": [
    {"id": "a", "type": "agent", "goal": "ok"},
    {"id": "g", "type": "gate", "after": ["a"], "when": "out.a.result > 3", "question": "q"}]}))
out1 = wf("s1")   # no upstream, when compares literals — must not crash startup
check("S1c startup survives literal 'when' (holds, no exit-1 silence)",
      "HELD" in out1 or "WORKFLOW_HELD" in out1, out1[:100])
out2 = wf("s1b")  # TypeError at fire time: hold fail-safe, runner still emits lifecycle
check("S1d value-error when HOLDS with lifecycle event",
      "WORKFLOW_HELD s1b" in out2, out2[:100])

# ---- S2: every read-model consumer survives a broken when ----------------------
st = W.run_state(r2)
check("S2a run_state totals: held + when_error surfaced",
      st and st["status"] == "held" and (st["held_gate"] or {}).get("when_error"),
      json.dumps({k: st.get(k) for k in ("status", "held_gate")})[:160] if st else "None")
sys.path.insert(0, str(BUILD.parent / "dashboard"))
os.environ.setdefault("DUCKWORK_WORKFLOWS_DIR", str(RUNS))
try:
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("papi", str(BUILD.parent / "dashboard" / "plugin_api.py"))
    papi = ilu.module_from_spec(spec); spec.loader.exec_module(papi)
    v = papi._view(r2)
    check("S2b dashboard _view survives broken when", v and v["status"] == "held",
          json.dumps(v)[:120] if v else "None")
except Exception as e:
    check("S2b dashboard _view survives broken when", False, repr(e))
# door: status + list must not raise
spec = ilu.spec_from_file_location("hw", str(BUILD.parent / "__init__.py"))
hw = ilu.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
try:
    s = json.loads(hw.handle({"action": "status", "run_id": "s1b"}))
    l = json.loads(hw.handle({"action": "list"}))
    check("S2c door status+list survive", s.get("status") == "held" and any(
        x["run_id"] == "s1b" for x in l.get("runs", [])),
          json.dumps({k: s.get(k) for k in ("status",)}) + f" list={len(l.get('runs', []))}")
except Exception as e:
    check("S2c door status+list survive", False, repr(e))

# ---- S3: zero post-cancellation spawns ------------------------------------------
(BUILD / "fake5.log").write_text("")
# roots at concurrency=1: stop mid-first-child => only 1 spawn total
r = mk("s3a", [{"id": f"n{i}", "type": "agent", "goal": "SLEEP 2 root"} for i in range(4)],
         concurrency=1)
p = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "s3a"], env=env,
                     stdout=subprocess.PIPE, text=True)
time.sleep(0.8)
(r / "stop.request").write_text("1")
out = p.communicate(timeout=90)[0].strip()
spawned = (BUILD / "fake5.log").read_text().count("root")
check("S3a stop kills wave; queued roots never spawn",
      "WORKFLOW_STOPPED" in out and spawned <= 1, f"spawned={spawned} out={out[:60]}")

# forced interleave: fanout cap=1, stop while item0 in flight — items 1+ must not launch
(BUILD / "fake5.log").write_text("")
r = mk("s3b", [{"id": "f", "type": "agent", "fanout": {"items": ["a", "b", "c", "d"],
                                                       "goal": "SLEEP 2 it {item}", "quorum": 1}}],
         item_concurrency=1)
p = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "s3b"], env=env,
                     stdout=subprocess.PIPE, text=True)
time.sleep(0.8)
(r / "stop.request").write_text("1")
out = p.communicate(timeout=90)[0].strip()
spawned = (BUILD / "fake5.log").read_text().count("SLEEP 2")
check("S3b fanout queued items die unlaunched after stop",
      "WORKFLOW_STOPPED" in out and spawned <= 1, f"spawned={spawned} out={out[:60]}")

# S3c: THE interleave astra's probe demonstrated (v5.0 bug): watcher must never be
# able to set _stop while a spawn section holds the lock. Hook Popen.__init__ entry
# (line-number independent): drop stop.request at that instant; _stop must NOT become
# settable while our section still holds the lock. v5.0: True. v5.1 (set-under-lock): False.
import importlib.util as ilu2, threading
spec5 = ilu2.spec_from_file_location("wf_probe", str(BUILD.parent / "wf.py"))
wf5 = ilu2.module_from_spec(spec5); spec5.loader.exec_module(wf5)
r = mk("s3c", [{"id": "a", "type": "agent", "goal": "SLEEP 10 s3c-interleave"}], concurrency=1)
obs = {"hit": False, "set_during_section": None}
def trace(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "__init__" \
            and frame.f_code.co_filename.endswith("subprocess.py") and not obs["hit"]:
        f = frame.f_back
        while f and f.f_code.co_name != "run_child": f = f.f_back
        if f:
            meta = f.f_locals["meta"]
            assert meta["_procs_lock"].locked(), "spawn section must hold the lock at Popen"
            (r / "stop.request").write_text("1")
            # 5s > the watcher's 2s poll: pre-fix the watcher WOULD set stop here
            obs["set_during_section"] = meta["_stop"].wait(5.0)
            obs["hit"] = True
    return trace
threading.settrace(trace)
try:
    wf5.main("s3c")
finally:
    threading.settrace(None)
    if wf5._LOCK_FD is not None:
        os.close(wf5._LOCK_FD); wf5._LOCK_FD = None
term = json.loads((r / "events.jsonl").read_text().splitlines()[-1])["event"]
check("S3c watcher cannot set _stop mid-spawn-section (astra probe, closed)",
      obs["hit"] and obs["set_during_section"] is False,
      f"hit={obs['hit']} set={obs['set_during_section']} term={term}")
check("S3c cancellation still terminates honestly", term == "run.stopped", term)

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
