#!/usr/bin/env python3
"""est-g255 P255-4 (zap, MED) — an exception AFTER Popen but before the polling
try/finally leaks the seat and skips child cleanup.

Base failure (zap independent-results.json / post_popen_exception_release):
fault-injecting a RuntimeError at _route_receipt_bake left one seat ticket and
one registered live child on disk — _seat_bind/_route_receipt_bake/
write_spawn_record/ledger_row all run OUTSIDE the try that owns the
finally-releasing cleanup, so anything raising there escapes with the seat
held and the child un-reaped. The independent harness had to kill/reap the
child and delete the ticket itself.

Fix contract (wf.py): ONE cleanup boundary over the whole acquired-seat/child
lifetime including post-Popen setup — any exception releases the seat,
terminates+reaps the immediate child, closes the log fd, deregisters
meta['_procs'] — then re-raises.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_popen_exception_g255.py
"""
import importlib.util, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-p255-4"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
(HOME / "config.yaml").write_text("model:\n  default: p255-default\n")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
_spec = importlib.util.spec_from_file_location("hw_g255_exc", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

run = HOME / "workflows" / "r-exc"
(run / "nodes").mkdir(parents=True)
node = {"id": "exc", "type": "agent", "goal": "ok"}
(run / "graph.json").write_text(json.dumps({"name": "r", "nodes": [node]}))
meta = {"_run": run, "duckwork_bin": str(HERE / "fake"), "_spawn_n": {},
        "_procs_lock": threading.Lock(), "_procs": {}, "_stop": threading.Event(),
        "node_timeout": 30}
seats = HOME / "seats"
os.environ["WF_SEATS_DIR"] = str(seats)

# Fault injection at the exact zap seam: a non-OSError exception raised after
# Popen, before the polling loop's try. Monkeypatch a post-Popen setup hook —
# the same channel zap used (_route_receipt_bake).
orig_bake = wf._route_receipt_bake
class Boom(RuntimeError):
    pass
def _boom(meta_, node_):
    raise Boom("injected post-Popen failure")
wf._route_receipt_bake = _boom
try:
    raised = None
    try:
        wf.run_child(meta, node, {"exc": node}, "ok", "", None, skey="wf:r:exc")
    except BaseException as e:      # the fix must re-raise, not swallow
        raised = e
    wf._route_receipt_bake = orig_bake
finally:
    pass

check("the injected post-Popen exception propagates (no silent swallow)",
      isinstance(raised, Boom), repr(raised))

# The child that HAD been Popen'd before the raise must be terminated and reaped,
# the seat ticket gone, the _procs registry empty.
time.sleep(0.3)
leftover = list((seats).glob("*.json")) if seats.exists() else []
check("the seat is RELEASED despite the post-Popen exception (no leaked ticket)",
      not leftover, f"leaked tickets: {[p.name for p in leftover]}")
live_procs = list(meta["_procs"].values())
check("meta['_procs'] deregistered on the exception path", not live_procs,
      f"still registered: {live_procs}")
# any spawned fake child must be dead: scan for our fake under this run's logs
logs = list((run / "logs").glob("*.log")) if (run / "logs").exists() else []
check("a spawn did happen before the raise (the control exercises the seam)",
      len(logs) >= 1, f"no spawn logs — control never reached post-Popen: {logs}")
import subprocess as _sp
ps = _sp.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
ours = [l for l in ps.splitlines() if "fake_duckwork.py" in l and str(HOME) in l]
check("the immediate child is reaped/terminated (no orphan fake child)",
      not ours, f"survivors: {ours}")

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
