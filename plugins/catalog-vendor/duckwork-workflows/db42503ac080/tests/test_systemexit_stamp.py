#!/usr/bin/env python3
"""SystemExit must never reach the crash net (phantom 'crashed: SystemExit: 0').

The runner's benign, self-reported exits — acquire_lock()'s lock-loser
sys.exit(0) after WORKFLOW_BUSY, and the no-graph sys.exit(2) — are BaseExceptions.
The last-resort net in the __main__ block (and main()'s own net around loop())
used to record them as "crashed: SystemExit: N" into runner_exit.json. Downstream,
`workflow status/wait` then renders status=failed + next:[amend] WHILE the real
runner and all its children are alive — and the operator reflex that invites
(rerun `wf.py run`, or `amend`) re-stamps or poisons the live run.

This test mirrors the live repro: hold the run's flock to emulate a working
runner, launch a second runner against it, and assert the second runner exits
clean WITHOUT touching the run's exit record. Also asserts the no-graph path
keeps its own honest stamp (rc=2; the net's same-process write was already a
no-op via write_runner_exit's first-writer-wins flag), and that a genuine
crash still reaches the net and stamps.
"""
import atexit, fcntl, json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
HOME = BUILD / "tests" / "home_systemexit"   # under tests/home*/ in .gitignore — never leak untracked
if HOME.exists():
    shutil.rmtree(HOME)
RUNS = HOME / "workflows"
RUNS.mkdir(parents=True)
atexit.register(shutil.rmtree, HOME, ignore_errors=True)  # cleanup even on mid-test failure
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
           DUCKWORK_WF_DUCKWORK_BIN=str(BUILD / "tests" / "fake"))

def mkrun(run_id, with_graph=True):
    r = RUNS / run_id
    r.mkdir(parents=True)
    (r / "nodes").mkdir(); (r / "gates").mkdir()
    if with_graph:
        (r / "graph.json").write_text(json.dumps(
            {"name": "sysexit", "nodes": [
                {"id": "ping", "type": "agent", "goal": "SLEEP 30"}]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": str(BUILD / "tests" / "fake"), "concurrency": 1,
         "node_timeout": 30}))
    return r

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail else "")
    ok += 1
    print(f"  ok: {msg}")

# ---- 1) BUSY lock-loser must not stamp a crash over a live run ----
r = mkrun("busy-run")
lk = os.open(r / "runner.lock", os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)   # emulate the live runner
try:
    p = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", "busy-run"],
                       capture_output=True, text=True, env=env, timeout=60)
    check(p.returncode == 0, "lock-loser exits 0", str(p.returncode))
    check("WORKFLOW_BUSY" in p.stdout, "lock-loser reports WORKFLOW_BUSY", p.stdout)
    check(not (r / "runner_exit.json").exists(),
          "live run's exit record untouched — no phantom 'crashed: SystemExit: 0'",
          (r / "runner_exit.json").read_text() if (r / "runner_exit.json").exists() else "")
    # and with a PRE-EXISTING honest record, the loser must not overwrite it:
    (r / "runner_exit.json").write_text(json.dumps({"reason": "done", "at": "x"}))
    p2 = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", "busy-run"],
                        capture_output=True, text=True, env=env, timeout=60)
    check(json.loads((r / "runner_exit.json").read_text())["reason"] == "done",
          "second loser run cannot overwrite the real verdict",
          (r / "runner_exit.json").read_text())
finally:
    fcntl.flock(lk, fcntl.LOCK_UN); os.close(lk)

# ---- 2) no-graph path keeps its own honest stamp, not the net's ----
r2 = mkrun("nograph-run", with_graph=False)
p3 = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", "nograph-run"],
                    capture_output=True, text=True, env=env, timeout=60)
check(p3.returncode == 2, "no-graph runner exits 2", str(p3.returncode))
rec = json.loads((r2 / "runner_exit.json").read_text())
check(rec["reason"] == "crashed: no graph.json",
      "no-graph stamp is the self-reported one, not 'crashed: SystemExit: 2'", rec)

# ---- 3) a REAL crash STILL stamps (the net still works) ----
# A genuine BaseException must reach the net AFTER the lock is held: an
# unparseable graph.json is swallowed by jload and exits via the honest
# no-graph branch, proving nothing about the net (a deleted net stays green).
# concurrency:"abc" raises TypeError inside ThreadPoolExecutor, past
# acquire_lock — only the net can record that death. (#11 ask 1, maintainer-
# verified trigger on the merged tree.)
r3 = mkrun("crash-run")
(r3 / "run.json").write_text(json.dumps(
    {"duckwork_bin": str(BUILD / "tests" / "fake"), "concurrency": "abc"}))
p4 = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", "crash-run"],
                    capture_output=True, text=True, env=env, timeout=60)
check(p4.returncode != 0, "genuine crash exits non-zero", str(p4.returncode))
rec4 = json.loads((r3 / "runner_exit.json").read_text()) if (r3 / "runner_exit.json").exists() else {}
check(rec4.get("reason", "").startswith("crashed: TypeError"),
      "genuine crash inside loop() still stamps runner_exit.json THROUGH the net", json.dumps(rec4))

shutil.rmtree(HOME, ignore_errors=True)
print(f"\nALL PASS ({ok})")
