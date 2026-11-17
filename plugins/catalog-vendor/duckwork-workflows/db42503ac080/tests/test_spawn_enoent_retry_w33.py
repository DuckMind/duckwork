#!/usr/bin/env python3
"""est-ulwpg — runner spawn ENOENT: <run>/work/<node> deleted between wd capture
and Popen must not be a 100% typed spawn death (witness 20261009-072611-fb-closeout-batch).

Witness receipt (nodes/triage.json): status=failed, error_class=spawn, ms=0,
attempts=1, "launcher spawn failed: [Errno 2] No such file or directory:
'<run>/work/triage'" — the run dir NEVER had a work/ subtree, events show a
34-min seat.wait between node.started and node.failed, so the deleater struck
in the window between the wd capture (run_child, `wd = str(child_work_dir(...))`
BEFORE _seat_acquire) and the launch-instant Popen (inside the _procs_lock
section). The typed death gave the batch zero retries.

Fix contract (wf.py):
  (a) the spawn seam re-ensures the child cwd IMMEDIATELY before
      subprocess.Popen — call child_work_dir(run, node, index) again inside the
      _procs_lock section (mkdir parents=True, exist_ok=True is idempotent) —
      so an external deleter that prunes <run>/work/<node> during the seat
      wait can no longer outrun the snapshot;
  (b) if Popen STILL raises OSError ENOENT whose filename is the cwd, the seam
      re-creates wd once and retries the Popen exactly once, in the same lock
      section, before declaring error_class=spawn;
  (c) an ENOENT about ANYTHING ELSE (missing duckwork_bin -> filename==argv[0])
      keeps failing typed — the retry must not paper over other ENOENTs.

RED on base: leg A dies with error_class=spawn ms=0 (the witness shape), leg
B's first Popen ENOENT escapes as the same typed death, leg C stays green on
both (the guard).

Run: cd tests && PYTHONPATH=/opt/duckwork:.. WF_RUNS_ROOT=$(mktemp -d) timeout 900 python3 test_spawn_enoent_retry_w33.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

HOME = Path(tempfile.mkdtemp(prefix="wf-w33-enoent-"))
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
(HOME / "config.yaml").write_text("model:\n  default: w33-default\n")
_spec = importlib.util.spec_from_file_location("hw_w33_enoent", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

# stock quiet-CLI fake: prints the fenced answer and exits (same shape as
# tests/test_11_runner_profile.py's duckwork stub).
BIN = HOME / "duckwork"
BIN.write_text("#!/usr/bin/python3\nprint('```json\\\\n{}\\\\n```')\n")
BIN.chmod(0o755)

SEATS = HOME / "seats"
os.environ["WF_SEATS_DIR"] = str(SEATS)
os.environ["WORKFLOW_MAX_SEATS"] = "4"

def fresh_run(rid):
    run = HOME / "workflows" / rid
    (run / "nodes").mkdir(parents=True)
    node = {"id": "triage", "type": "agent", "goal": "ok"}
    (run / "graph.json").write_text(json.dumps({"name": rid, "nodes": [node]}))
    meta = {"_run": run, "duckwork_bin": str(BIN), "_spawn_n": {},
            "_procs_lock": threading.Lock(), "_procs": {}, "_stop": threading.Event(),
            "node_timeout": 30, "max_seats": 4}
    return run, node, {"triage": node}, meta

# ---- leg A (H1 witness shape): delete <run>/work/<node> DURING the seat wait.
# run_child captures wd at `wd = str(child_work_dir(...))` BEFORE _seat_acquire;
# an external deleter active while the seat is contended removes the dir after
# creation and before Popen. Fixed runner re-ensures the cwd inside the lock
# section immediately before Popen, so the spawn still lands done.
run_a, node_a, byid_a, meta_a = fresh_run("r-w33-a")
wd_a = run_a / "work" / "triage"
real_seat_acquire = wf._seat_acquire
def seat_acquire_deleter(*a, **kw):
    shutil.rmtree(wd_a, ignore_errors=True)   # after wd creation, before Popen
    return real_seat_acquire(*a, **kw)
wf._seat_acquire = seat_acquire_deleter
try:
    rec_a = wf.run_child(meta_a, node_a, byid_a, "ok", "", None, skey="wf:r-a:triage")
finally:
    wf._seat_acquire = real_seat_acquire
check("A: spawn survives a work-dir delete during the seat wait (re-ensure pre-Popen)",
      rec_a.get("status") == "done",
      f"witness shape reproduced at base: {rec_a}")
check("A: no seat ticket leaked", not list(SEATS.glob("*.json")),
      str([p.name for p in SEATS.glob('*.json')]))
check("A: the work dir exists again after the run (re-created, not just spared)",
      wd_a.is_dir(), str(wd_a))
check("A: _procs deregistered", not meta_a["_procs"], str(meta_a["_procs"]))

# ---- leg B (fix shape (b)): delete between the re-ensure and Popen itself —
# monkeypatch seam at the Popen call: first call for OUR cwd deletes the dir
# then runs the REAL Popen (which ENOENTs on the cwd, exactly the witness
# errno/filename); the fix must re-create wd and retry the Popen EXACTLY once.
run_b, node_b, byid_b, meta_b = fresh_run("r-w33-b")
wd_b = run_b / "work" / "triage"
_real_popen = subprocess.Popen
popen_calls = {"ours": 0}
def popen_deleter_once(*a, **kw):
    if str(kw.get("cwd") or "") == str(wd_b) or str(kw.get("cwd") or "") == str(Path(wd_b).resolve()):
        popen_calls["ours"] += 1
        if popen_calls["ours"] == 1:
            shutil.rmtree(wd_b, ignore_errors=True)   # after re-ensure, before exec
    return _real_popen(*a, **kw)
subprocess.Popen = popen_deleter_once
try:
    rec_b = wf.run_child(meta_b, node_b, byid_b, "ok", "", None, skey="wf:r-b:triage")
finally:
    subprocess.Popen = _real_popen
check("B: ENOENT-on-cwd is retried once and the spawn lands done",
      rec_b.get("status") == "done",
      f"typed death reproduced at base (no retry): {rec_b}; popen_calls={popen_calls}")
check("B: exactly one retry — two Popen attempts on our cwd, never a retry loop",
      popen_calls["ours"] == 2, f"popen_calls={popen_calls}")
check("B: work dir re-created for the retry", wd_b.is_dir(), str(wd_b))
check("B: no seat ticket leaked", not list(SEATS.glob("*.json")),
      str([p.name for p in SEATS.glob('*.json')]))

# ---- leg C (guard (c)): a missing duckwork_bin is still an ENOENT — but its
# filename is argv[0], NOT the cwd: it must fail typed on the FIRST attempt,
# no retry, no wd resurrection loop.
run_c, node_c, byid_c, meta_c = fresh_run("r-w33-c")
meta_c["duckwork_bin"] = str(HOME / "definitely-not-duckwork")
wd_c = run_c / "work" / "triage"
_real_popen_c = subprocess.Popen
calls_c = {"ours": 0}
def popen_count(*a, **kw):
    if str(kw.get("cwd") or "") == str(wd_c):
        calls_c["ours"] += 1
    return _real_popen_c(*a, **kw)
subprocess.Popen = popen_count
try:
    rec_c = wf.run_child(meta_c, node_c, byid_c, "ok", "", None, skey="wf:r-c:triage")
finally:
    subprocess.Popen = _real_popen_c
check("C: missing duckwork_bin keeps the typed launcher spawn failure",
      rec_c.get("status") == "failed" and rec_c.get("error_class") == "spawn"
      and "launcher spawn failed" in (rec_c.get("error") or ""),
      f"papered over: {rec_c}")
check("C: no ENOENT retry for a non-cwd ENOENT (exactly one Popen on our cwd)",
      calls_c["ours"] == 1, f"popen_calls={calls_c}")
check("C: no seat ticket leaked", not list(SEATS.glob("*.json")),
      str([p.name for p in SEATS.glob('*.json')]))

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE spawn_enoent_retry_w33")
sys.exit(0 if ok else 1)
