#!/usr/bin/env python3
"""est-2ek.1.666 — a terminating runner must never orphan its agent-node child.

Witnessed shape (2026-10-04 15:32Z, fb-closeout): runner terminated (SIGTERM /
SIGKILL-tested paths / crash) -> the current agent-node child survives in its
own session and keeps mutating real state unsupervised.

Law pinned here (RED on base, GREEN on branch):
  T1  SIGTERM the runner mid-child: the child AND its setsid-detached
      grandchild are dead within the grace window and the grandchild's
      heartbeat file STOPS ADVANCING (the orphan-mutates-real-state shape).
  T2  SIGKILL the runner mid-child (no handler can run): the belt-braces fire —
      a cooperating child that notices its runner died self-exits non-zero;
      the detached grandchild's heartbeat stops.
  T3  the seam exists: spawn pins the runner pid into the child env
      (wf.RUNNER_PID_ENV), the child-side helper is wf.child_parent_watch, and
      the runner registers termination cleanup (killpg on every exit path).
  T4  the belt's lane probe confirms a held runner.lock: a PEER belt's µs
      probe flock is never misread as a replacement runner (CI red 37265560243
      — one misread reset the grace and T2's orphan outlived the window); a
      real holder still reads live (adoption law kept).

The grandchild heartbeats to FAKE_HB_666 every 0.2 s (stub_orphan_666_child.py),
detached double-fork+setsid so the child group's killpg alone cannot reach it.
"""
import json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + ("  " + str(detail)[:400] if detail else "")))
    ok = ok and bool(cond)

HOME = Path(tempfile.mkdtemp(prefix="wf-orphan666-"))
RUNS = HOME / "workflows"
STUB = HERE / "stub_orphan_666_child.py"
STUB.chmod(0o755)

def mk(run_id):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [
        {"id": "work", "type": "agent", "goal": "do the closeout work"}]}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": str(STUB),
                                            "node_timeout": 300}))
    return r

def start(run_id):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / f"{run_id}.fake.log"),
               FAKE_HB_666=str(HOME / f"{run_id}.hb"),
               FAKE_GC_666=str(HOME / f"{run_id}.gc"),
               STUB_SLEEP="300", PYTHONDONTWRITEBYTECODE="1")
    for k in ("FAKE_MODE", "FAKE_PID_LOG", "FAKE_ARGV_LOG", "FAKE_PROMPT_LOG"):
        env.pop(k, None)
    return subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)

def wait_for(pred, timeout, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.05)
    return False

def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return not st.startswith("Z")

def beats(run_id):
    try:
        return (HOME / f"{run_id}.hb").read_text().strip()
    except OSError:
        return ""

def gc_pids(run_id):
    try:
        return [int(x) for x in (HOME / f"{run_id}.gc").read_text().split() if x.strip()]
    except OSError:
        return []

def child_pids(run_id):
    try:
        return [int(x) for x in (HOME / f"{run_id}.fake.log").read_text().split() if x.strip()]
    except OSError:
        return []

GRACE_S = 10.0

def settle_and_watch(run_id):
    """Child + detached grandchild live and heartbeating."""
    return (child_pids(run_id) and gc_pids(run_id)
            and len(beats(run_id).splitlines()) >= 3)

# ---------- T1: SIGTERM the runner -> child + grandchild dead, heartbeat frozen ----
run_id = "t666-term"
r = mk(run_id)
(HOME / f"{run_id}.fake.log").write_text("")
runner = start(run_id)
check("T1 setup: runner reaches a live child with a detached heartbeating grandchild",
      wait_for(lambda: settle_and_watch(run_id), 45, "child+grandchild live"),
      f"child={child_pids(run_id)} gc={gc_pids(run_id)} beats={len(beats(run_id).splitlines())}")
kids = child_pids(run_id)
gcs = gc_pids(run_id)
try:
    runner.send_signal(signal.SIGTERM)
    runner.wait(timeout=30)
except Exception:
    pass
check("T1 runner process gone after SIGTERM", not alive(runner.pid), runner.pid)
t0 = time.time()
while time.time() - t0 < GRACE_S and any(alive(p) for p in kids + gcs):
    time.sleep(0.05)
check("T1 SIGTERM: the agent-node child is dead within the grace window",
      not any(alive(p) for p in kids), f"still alive: {[p for p in kids if alive(p)]}")
check("T1 SIGTERM: the setsid-detached grandchild is dead within the grace window",
      not any(alive(p) for p in gcs), f"still alive: {[p for p in gcs if alive(p)]}")
b1 = beats(run_id)
time.sleep(1.5)
b2 = beats(run_id)
check("T1 SIGTERM: the orphan heartbeat file STOPPED advancing (no unsupervised mutation)",
      b1 == b2, f"{len(b1.splitlines())} -> {len(b2.splitlines())} beats after the runner died")

# ---------- T2: SIGKILL (no handler can run) -> the child-side belt cuts the tree --
run_id = "t666-kill"
r = mk(run_id)
(HOME / f"{run_id}.fake.log").write_text("")
runner = start(run_id)
check("T2 setup: runner reaches a live child with a detached heartbeating grandchild",
      wait_for(lambda: settle_and_watch(run_id), 45, "child+grandchild live"),
      f"child={child_pids(run_id)} gc={gc_pids(run_id)} beats={len(beats(run_id).splitlines())}")
gcs = gc_pids(run_id)
try:
    os.kill(runner.pid, signal.SIGKILL)
    runner.wait(timeout=30)
except Exception:
    pass
t0 = time.time()
while time.time() - t0 < GRACE_S and any(alive(p) for p in gcs):
    time.sleep(0.05)
check("T2 SIGKILL: the belt-braces fire — the detached grandchild self-exits when its runner dies",
      not any(alive(p) for p in gcs), f"still alive: {[p for p in gcs if alive(p)]}")
b1 = beats(run_id)
time.sleep(1.5)
check("T2 SIGKILL: the heartbeat STOPPED advancing", b1 == beats(run_id),
      f"{len(b1.splitlines())} -> {len(beats(run_id).splitlines())}")

# ---------- T3: the seam exists (unit half of the law) ----------------------------
check("T3 child-side liveness helper exists (wf.child_parent_watch)",
      callable(getattr(wf, "child_parent_watch", None)))
check("T3 spawn pins the runner pid for the belt (wf.RUNNER_PID_ENV = DUCKWORK_WF_RUNNER_PID)",
      getattr(wf, "RUNNER_PID_ENV", None) == "DUCKWORK_WF_RUNNER_PID")
check("T3 runner registers termination cleanup (killpg on every exit path)",
      callable(getattr(wf, "_runner_term_cleanup", None)))

# ---------- T4: the belt's lane probe is not fooled by a PEER probe ----------------
# CI red (run 37265560243): the agent child's belt and the grandchild's belt probe
# runner.lock with the same µs LOCK_EX|LOCK_NB; one sample read a peer's probe as
# "a replacement runner holds the lane", reset the grace, and the orphan outlived
# its SIGKILLed runner past the window. Deterministic: a peer holds the lock for a
# probe-length instant -> NOT a live runner; a real holder that never releases ->
# still a live runner (adoption law intact).
import fcntl, threading
lane = HOME / "t666-probe"; lane.mkdir(parents=True, exist_ok=True)
(lane / "runner.lock").write_text("")
def _peer_probe(held, release):
    fd = os.open(str(lane / "runner.lock"), os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    held.set(); release.wait(5)
    fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
misreads = 0
for _ in range(5):
    held, release = threading.Event(), threading.Event()
    th = threading.Thread(target=_peer_probe, args=(held, release)); th.start()
    held.wait(5)
    threading.Timer(0.003, release.set).start()   # a probe holds for µs; 3ms is generous
    misreads += bool(wf._lane_has_live_runner(str(lane)))
    th.join(5)
check("T4 a peer's transient probe flock is NOT read as a live runner on the lane",
      misreads == 0, f"{misreads}/5 peer probes misread as a replacement runner")
hfd = os.open(str(lane / "runner.lock"), os.O_RDWR)
fcntl.flock(hfd, fcntl.LOCK_EX)                   # a runner: holds for its whole life
check("T4 a real holder (replacement runner) still reads as live — adoption kept",
      wf._lane_has_live_runner(str(lane)) is True)
fcntl.flock(hfd, fcntl.LOCK_UN); os.close(hfd)
check("T4 a free lane reads as no runner", wf._lane_has_live_runner(str(lane)) is False)

shutil.rmtree(HOME, ignore_errors=True)
print("RESULT", "GREEN" if ok else "RED")
raise SystemExit(0 if ok else 1)
