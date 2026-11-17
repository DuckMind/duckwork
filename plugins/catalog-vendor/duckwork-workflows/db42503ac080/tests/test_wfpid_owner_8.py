#!/usr/bin/env python3
"""#8 (review findings 3+4, P1): the ADMITTED runner is the SOLE wf.pid owner.

Stamp law: the runner self-stamps wf.pid inside ready_stamp() immediately AFTER
it has won the runner-side flock (wf.py: acquire_lock -> ready_stamp). The door
must never write wf.pid at all — its post-observation write-back is wrong on
both schedules the deep review reproduced (comment 5914319654):

  W1 — ready-pipe second write (__init__.py _spawn_runner, the `if pid is not
       None: (r / "wf.pid").write_text(...)` tail): the door keeps the pid it
       observed on the ready pipe and writes it LATER — other work can run in
       between, a replacement runner can be admitted into the same run, and the
       late write resurrects the dead pid. Deterministic seam: pause door A
       right after _ready_pid observed admitted runner A; let A die and release
       the flock; admit runner B for the same run; only THEN release door A —
       buggy head leaves wf.pid naming dead A while live B holds the flock.

  W2 — refused-fork fallback (intermediate exits 3 -> _spawn_runner_legacy
       direct spawn): with a live winner holding the flock, the legacy child is
       flock-refused (WORKFLOW_BUSY) yet the door stamps its dead pid. Reviewer
       probe: winner 289668 live, dead loser 289683 ended up in wf.pid.

Returning an observed pid to the caller is fine — REWRITING wf.pid is not (the
legacy path needs no door stamp either: there the Popen'd child IS the runner
and self-stamps at admission exactly like the daemonized path).

The estate shelf is never touched: DUCKWORK_HOME and WF_RUNS_ROOT are BOTH
sandboxed into tests/home-wfpidowner8/ via os.environ before import.
Standalone, stdlib-only:
  PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_wfpid_owner_8.py
"""
import importlib.util, json, os, shutil, signal, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE.parent)
scratch = HERE / "home-wfpidowner8"   # tests/home-*/ — ignored by .gitignore + .graphifyignore
if scratch.exists():
    shutil.rmtree(scratch)
home = scratch / "home"; home.mkdir(parents=True)
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(home / "workflows")   # sandbox BOTH: never the estate shelf
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "tests" / "fake")
sys.path.insert(0, str(BUILD))
spec = importlib.util.spec_from_file_location("hwpo", BUILD / "__init__.py")
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
from wf_test_markers import read_pid_marker   # est-jue3: one parseable-content wait family (the #267 shape, shared)
runs = Path(os.environ["WF_RUNS_ROOT"])

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def call(**a):
    return json.loads(hw.handle(a))

def alive(pid):
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    try:
        st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return not st.startswith("Z")
    except OSError:
        return True

def cmdline(pid):
    try:
        return " " + Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").replace("\0", " ").strip() + " "
    except OSError:
        return ""

def runners_for(rid):
    """Live runner pids for THIS run id: cmdline carries the exact run dir name."""
    out = []
    for pid in _proc_pids():
        if f"{os.sep}wf.py run {rid}" in cmdline(pid):
            out.append(pid)
    return out

def _proc_pids():
    try:
        return [int(e) for e in os.listdir("/proc") if e.isdigit()]
    except OSError:
        return []

def wfpid_of(rid):
    try:
        return int((runs / rid / "wf.pid").read_text().strip())
    except (OSError, ValueError):
        return -1

def wait_live(rid, budget=20.0):
    """Poll until the run's admitted runner self-stamped wf.pid and is alive."""
    t0 = time.time()
    while time.time() - t0 < budget:
        w = wfpid_of(rid)
        if w > 0 and alive(w):
            return w
        time.sleep(0.05)
    return wfpid_of(rid)

# ---- W1: door A's late ready-pipe write must not resurrect dead A over B ------
# The reviewer's deterministic scheduling seam, driven WITHOUT touching the
# estate shelf. Run R gets runner A through the door with _ready_pid paused at
# the exact post-observation seam; A is then SIGKILLed (kernel releases the
# flock on any exit — same admission release as finishing); runner B is admitted
# for the SAME run and self-stamps wf.pid; only then door A resumes, where the
# buggy head re-writes its stale observed pid.
_orig_ready = hw._ready_pid
_seen = scratch / "w1-observed"            # door A publishes its observed pid here
_gate = scratch / "w1-gate"                # exists while door A must hold position

def _paused_ready(rd):
    pid = _orig_ready(rd)
    if pid is not None:
        _seen.write_text(str(pid))
        t0 = time.time()                   # hold door A AT the post-observe seam
        while _gate.exists() and time.time() - t0 < 30:
            time.sleep(0.05)
    return pid

try:
    # Fresh run dir built directly (T3b precedent) so nothing holds the flock
    # when door A spawns: door A's runner IS the first admitted runner.
    ridR = time.strftime("%Y%m%d-%H%M%S") + "-wfpidw1"
    rdirR = runs / ridR
    (rdirR / "nodes").mkdir(parents=True); (rdirR / "gates").mkdir()
    (rdirR / "graph.json").write_text(json.dumps(
        {"name": "wfpid-w1", "nodes": [{"id": "slow", "type": "agent", "goal": "SLEEP 6"}]}))
    (rdirR / "run.json").write_text(json.dumps(
        {"name": "wfpid-w1", "duckwork_bin": os.environ["DUCKWORK_WF_DUCKWORK_BIN"]}))

    _gate.write_text("hold")
    hw._ready_pid = _paused_ready
    ta = threading.Thread(target=lambda: hw._spawn_runner(rdirR))
    ta.start()                                # door A -> admits runner A

    # Wait until door A has OBSERVED admitted runner A on the ready pipe and is
    # parked at the post-observation seam (buggy head: its second write pending).
    # est-jue3: _seen is published by door A's thread with a non-atomic
    # write_text — existence precedes bytes; wait for the parseable pid, not
    # for mere existence (the #267 read_pid_marker shape). Honest timeout
    # raises into the harness's except below, same as the old -1 read did.
    aPid = read_pid_marker(_seen, timeout=20)[0]
    check("W1 seam: door A observed admitted runner A and is parked post-observation",
          aPid > 0 and alive(aPid) and ta.is_alive() and wfpid_of(ridR) == aPid,
          f"aPid={aPid} parked={ta.is_alive()} wf.pid={wfpid_of(ridR)}")

    # Runner A dies: the kernel drops its flock (same release as finishing).
    try:
        os.kill(aPid, signal.SIGKILL)
    except OSError:
        pass
    t0 = time.time()
    while alive(aPid) and time.time() - t0 < 15:
        time.sleep(0.1)
    check("W1: runner A dead, flock released", not alive(aPid))

    # Runner B admits for the same run (the wait-resume path uses the same
    # spawner). It self-stamps wf.pid at admission and lives, holding the flock.
    hw._ready_pid = _orig_ready
    hw._spawn_runner(rdirR)
    winnerB = None
    t0 = time.time()
    while time.time() - t0 < 20:
        live = [p for p in runners_for(ridR) if alive(p) and p != aPid]
        if len(live) == 1 and wfpid_of(ridR) == live[0]:
            winnerB = live[0]
            break
        time.sleep(0.1)
    check("W1: runner B admitted, live, self-stamped wf.pid", winnerB is not None,
          f"live={runners_for(ridR)} wf.pid={wfpid_of(ridR)}")

    _gate.unlink(missing_ok=True)          # release door A — buggy head writes dead A2 now
    ta.join(timeout=40)
    time.sleep(0.3)
    check("W1 sole-owner law: after door A's late return wf.pid still names live B "
          "(the door never re-stamps after admission)",
          winnerB is not None and wfpid_of(ridR) == winnerB and alive(winnerB),
          f"wf.pid={wfpid_of(ridR)} (dead A2={aPid}) live B={winnerB}")
except Exception as e:
    check("W1 completed without harness error", False, repr(e))
finally:
    hw._ready_pid = _orig_ready
    try:
        _gate.unlink(missing_ok=True)
    except OSError:
        pass

# ---- W2: refused-fork fallback loser must never stamp the winner's wf.pid -----
# The reviewer's probe: live winner holds the flock; the refused-fork return
# path (intermediate exits 3, no ready line) runs the door's _spawn_runner_legacy
# fallback. The legacy child is flock-refused (WORKFLOW_BUSY) — the buggy head
# stamps its DEAD pid; runner.lock keeps naming the live winner. The refused-fork
# branch is driven with the real door code: the intermediate is substituted to
# exit(3) pre-fork, exactly the reviewer's method.
try:
    os.environ["FAKE_PID_LOG"] = str(scratch / "fpid-w2.log")
    rC = call(action="run", graph={"name": "wfpid-w2", "nodes": [
        {"id": "slow", "type": "agent", "goal": "SLEEP 6 cook the report"}]})
    ridC = rC["run_id"]; rdirC = runs / ridC
    winnerC = wait_live(ridC)
    check("W2 setup: winner live, wf.pid self-stamped by the admitted runner",
          winnerC > 0 and alive(winnerC) and wfpid_of(ridC) == winnerC,
          f"wf.pid={wfpid_of(ridC)} winner={winnerC}")

    # (a) daemonized contender against the live winner: pipe EOF -> no observed
    # pid, rc 0 -> no fallback, nothing stamped (guard for the existing T3a law).
    hw._spawn_runner(rdirC)
    time.sleep(1.0)
    check("W2a flock-refused daemonized contender: wf.pid still names the live winner",
          wfpid_of(ridC) == winnerC and alive(winnerC),
          f"wf.pid={wfpid_of(ridC)} winner={winnerC}")

    # (b) FORCED refused-fork return: substitute the intermediate with one that
    # exits 3 before forking — the same exit code and branch the real
    # `except OSError: os._exit(3)` takes (the reviewer used the identical
    # substitution). pid stays None, rc=3 -> the door runs the legacy fallback
    # direct spawn, whose child is flock-refused by the live winner.
    _orig_intermediate = hw._DAEMON_INTERMEDIATE
    hw._DAEMON_INTERMEDIATE = "import os\nos._exit(3)\n"
    try:
        ret = hw._spawn_runner(rdirC)
        time.sleep(1.2)
        busy = sum(1 for line in (rdirC / "runner.log").read_text(errors="replace").splitlines()
                   if "WORKFLOW_BUSY" in line)
        check("W2b refused-fork fallback spawned a flock-refused loser (WORKFLOW_BUSY)",
              busy >= 2, f"door returned {ret} busy_lines={busy} (W2a contender adds 1)")
        dead_loser = ret if (ret is not None and ret != winnerC) else None
        check("W2b sole-owner law: refused-fork loser never stamped — wf.pid still the live winner "
              "(runner.lock also still names the winner)",
              wfpid_of(ridC) == winnerC and alive(winnerC),
              f"wf.pid={wfpid_of(ridC)} (forced loser pid={dead_loser}) winner={winnerC}")
    finally:
        hw._DAEMON_INTERMEDIATE = _orig_intermediate
except Exception as e:
    check("W2 completed without harness error", False, repr(e))

# ---- cleanup: ONLY this test's own processes -----------------------------------
ours = set()
for d in (os.listdir(runs) if runs.exists() else []):
    for p in runners_for(d):
        ours.add(p)
for pid in _proc_pids():
    c = cmdline(pid)
    if str(scratch) in c:                 # fake children carry our sandbox args
        ours.add(pid)
for pid in ours:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
for lf in scratch.glob("fpid-*.log"):     # fake children that logged pids
    for tok in lf.read_text(errors="replace").split():
        if tok.isdigit():
            try:
                os.kill(int(tok), signal.SIGKILL)
            except OSError:
                pass
while True:
    try:
        if os.waitpid(-1, os.WNOHANG)[0] == 0:
            break
    except ChildProcessError:
        break

print(f"wfpid_owner_8: {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
