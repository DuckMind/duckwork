#!/usr/bin/env python3
"""#8 (P0): the runner must leave the caller's process tree before handle() returns.

Four incidents, one mechanism: the door spawns the runner as a CHILD of the caller
(gateway seat / tool process). start_new_session=True only escapes GROUP-directed
signals; the actual killers walk the tree by pid and SIGKILL per-pid from a
descendants snapshot taken WHILE the parent is alive:
  * gateway restart (s6 service stop: SIGTERM to the process TREE + group kills),
  * process_registry completion sweep (_terminate_host_pid: snapshot descendants,
    SIGTERM parent, escalate SIGKILL to every snapshot pid, re-scan while the
    parent lives).
Only an orphan whose ppid chain no longer passes through the caller survives.
So: daemonize the spawn (double-fork + setsid -> the runner leaves the caller's
tree BEFORE handle() returns), keep the runner-side flock as the admission gate
(loser WORKFLOW_BUSY), and stamp wf.pid from the runner's OWN ready-pipe write —
the door must never stamp a pid at all (see tests/test_wfpid_owner_8.py).

The sweep here is the incident's OWN semantics (per-pid kills over a live-parent
descendants snapshot + the service-stop group SIGKILL), reproduced without psutil
via /proc.

CLAIM BOUNDARY — two properties, deliberately separated (#8 deep review, finding 2):
  (a) CLAIMED here: escaping the ORDINARY CALLER TREE. T1/T2 prove the runner is
      out of the caller's descendant subtree at snapshot time and survives the
      caller-tree sweeps. The test process holds PR_SET_CHILD_SUBREAPER only as a
      fixture to pin the ADOPTION TARGET (a naive "just survive the caller dying"
      reparent-under-the-caller trick must fail); it asserts nothing about
      surviving cleanup OF this enclosing tree.
  (b) NOT claimed by this diff: surviving an ENCLOSING subreaper/service cleanup.
      double-fork/setsid never changes cgroup membership — a sweep that kills by
      service/cgroup membership (unit-cgroup ExecStopPost; an enclosing
      subreaper's own descendant sweep) still reaches runner and children (the
      reviewer proved both). External supervision is a mitigation outside this
      diff, and those #8 parts stay open.

RED pre-fix: the snapshot contains runner+child (ppid chain through the caller)
and both die; wf.pid ends on a dead loser's pid. GREEN: runner and its child
survive the whole sweep and the run commits, wf.pid == the live runner.

Standalone, stdlib-only:  PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_daemonize_8.py
"""
import ctypes, importlib.util, json, os, select, shutil, signal, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE.parent)
scratch = HERE / "home-daemonize8"   # tests/home-*/ — ignored by .gitignore + .graphifyignore
if scratch.exists():
    shutil.rmtree(scratch)
home = scratch / "home"; home.mkdir(parents=True)
runs = home / "workflows"
os.environ["WF_RUNS_ROOT"] = str(runs)   # #71: pin the env door to the SAME scratch
                                          # root DUCKWORK_HOME derives (the pop was a
                                          # cleanliness step; equal values, pinned)
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "tests" / "fake")
sys.path.insert(0, str(BUILD))
spec = importlib.util.spec_from_file_location("hw8", BUILD / "__init__.py")
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

# This process asks to be the test tree's subreaper so T1 can assert the ADOPTION
# TARGET: the orphaned runner must be adopted HERE (a live parent standing for the
# service tree), never drift back under the caller. Correct call:
# PR_SET_CHILD_SUBREAPER = 36 (prctl(1,...) would set PR_SET_PDEATHSIG — a
# different option; the deep review caught the fixture using it unchecked). We
# check the return value AND read back PR_GET_CHILD_SUBREAPER = 37.
_SUBREAPER = False
_SUBREAPER_RC = _SUBREAPER_READBACK = None
try:
    _libc = ctypes.CDLL(None)
    _SUBREAPER_RC = _libc.prctl(36, 1, 0, 0, 0)             # PR_SET_CHILD_SUBREAPER
    _flag = ctypes.c_int(-1)
    _SUBREAPER_READBACK = _libc.prctl(37, ctypes.byref(_flag), 0, 0, 0)  # PR_GET_...
    _SUBREAPER = (_SUBREAPER_RC == 0 and _SUBREAPER_READBACK == 0 and _flag.value == 1)
except Exception as _e:
    print(f"NOTE subreaper fixture unavailable: {_e!r}")
print(f"subreaper fixture: set_rc={_SUBREAPER_RC} get_rc={_SUBREAPER_READBACK} active={_SUBREAPER}")

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def call(**a):
    return json.loads(hw.handle(a))

SLOW = {"name": "daemonize8-slow", "nodes": [
    {"id": "slow", "type": "agent", "goal": "SLEEP 4 cook the report"}]}

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

def ppid_of(pid):
    try:
        return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    except (OSError, IndexError):
        return -1

def proc_map():
    m = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return m
    for e in entries:
        if e.isdigit():
            try:
                m[int(e)] = int(Path(f"/proc/{e}/stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError):
                pass
    return m

def descendants(root):
    """psutil children(recursive) equivalent: live ppid links, /proc only."""
    kids = {}
    for p, pp in proc_map().items():
        kids.setdefault(pp, []).append(p)
    out, stack = [], [root]
    while stack:
        p = stack.pop()
        for c in kids.get(p, []):
            out.append(c); stack.append(c)
    return out

def _kill(p):
    try:
        os.kill(p, signal.SIGKILL)
    except OSError:
        pass

def registry_sweep(pid):
    """process_registry._terminate_host_pid semantics (1038-1133): snapshot
    descendants WHILE the parent lives, SIGTERM the parent, escalate SIGKILL to
    every snapshot pid (re-scanning while the parent still lives), plus the
    service-stop group SIGKILL. Returns the pid set it aimed at."""
    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = None
    snap = set(descendants(pid))                       # taken while parent alive
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    t0 = time.time()
    while alive(pid) and time.time() - t0 < 2.0:
        time.sleep(0.05)
    if alive(pid):                                     # parent alive after grace:
        snap |= set(descendants(pid))                  # registry re-scan line 1128
        _kill(pid)
    for p in sorted(snap):
        if alive(p):
            _kill(p)
    t0 = time.time()
    while any(alive(p) for p in snap) and time.time() - t0 < 2.0:
        time.sleep(0.02)
    for p in sorted(snap):                             # escalation, re-probed
        if alive(p):
            _kill(p)
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGKILL)            # service-stop group sweep
        except OSError:
            pass
    return snap

def read_child_pids(logpath):
    try:
        return [int(x) for x in Path(logpath).read_text().split() if x.isdigit()]
    except (OSError, ValueError):
        return []

CALLER_SRC = """
import importlib.util, json, os, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("hw", os.environ["WF_TEST_BUILD"] + "/__init__.py")
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
G = {"name": "daemonize8-slow", "nodes": [
    {"id": "slow", "type": "agent", "goal": "SLEEP 4 cook the report"}]}
res = json.loads(hw.handle({"action": "run", "graph": G}))
rid = res["run_id"]
print("RID=" + rid, flush=True)
p = Path(os.environ["FAKE_PID_LOG"])
# READY := the run is ADMITTED (wf.pid stamped by the runner) AND the child is
# visibly cooking — the preconditions are race-free, no sleep-based waits.
t = time.time()
while time.time() - t < 20:
    try:
        admitted = int((Path(os.environ["DUCKWORK_HOME"]) / "workflows" / rid / "wf.pid").read_text().strip()) > 0
    except (OSError, ValueError):
        admitted = False
    if admitted and p.exists() and p.read_text().strip():
        break
    time.sleep(0.05)
print("READY", flush=True)
"""
Caller = scratch / "caller.py"          # scratch, never tests/ (91b9a3de precedent)
Caller.write_text(CALLER_SRC + 'time.sleep(float(os.environ.get("CALLER_LIFE", "300")))\n')
CallerExit = scratch / "caller_exit.py"
CallerExit.write_text(CALLER_SRC)       # ... then EXITS (turn end) — sweep after

def launch_caller(script, life=None):
    env = {**os.environ, "WF_TEST_BUILD": str(BUILD),
           "FAKE_PID_LOG": str(scratch / ("fpid-" + script.stem + ".log"))}
    if life:
        env["CALLER_LIFE"] = str(life)
    p = subprocess.Popen([sys.executable, str(script)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, start_new_session=True, cwd=str(BUILD))
    rid, ready = None, False
    t0 = time.time()
    while time.time() - t0 < 40:
        r, _, _ = select.select([p.stdout], [], [], max(0.0, 40 - (time.time() - t0)))
        if not r:
            break
        line = p.stdout.readline()
        if not line:
            break
        if line.startswith("RID="):
            rid = line[4:].strip()
        elif line.startswith("READY"):
            ready = True
            break
    return p, rid, ready

def settle(rid, budget=40.0):
    """Poll status ONLY (no respawn): recovery must come from the SURVIVING
    runner, not from a door re-spawn."""
    t0 = time.time()
    while time.time() - t0 < budget:
        st = call(action="status", run_id=rid)
        if st.get("status") in ("done", "failed", "stopped"):
            return st
        time.sleep(0.4)
    return call(action="status", run_id=rid)

def wfpid_of(rid):
    try:
        return int((runs / rid / "wf.pid").read_text().strip())
    except (OSError, ValueError):
        return -1

# ---- T0 sanity: a plain run completes (environment guard) -----------------------
r0 = call(action="run", graph=SLOW)
rid0 = r0.get("run_id")
check("T0 run launches", bool(rid0), r0)
st0 = settle(rid0, 30)
check("T0 run completes", st0.get("status") == "done", json.dumps({k: st0.get(k) for k in ("status", "runner_live")}))

# ---- T1 PROPERTY (a): ordinary caller-tree escape + live-parent sweep ----------
# caller lives under our subreaper FIXTURE (adoption-target pin only — see the
# claim boundary in the module docstring); it spawns the runner via the real door
# path (handle(run)), child visibly cooking; then the sweep: snapshot while caller
# alive, SIGTERM->SIGKILL the caller, SIGKILL every snapshot pid, group-SIGKILL.
# This tests escaping the CALLER TREE — NOT surviving this enclosing fixture's
# own cleanup (property (b), not claimed by this diff).
check("T1 fixture: PR_SET_CHILD_SUBREAPER actually took (prctl 36 rc=0, readback 37 -> 1)",
      _SUBREAPER, f"set_rc={_SUBREAPER_RC} get_rc={_SUBREAPER_READBACK}")
p1, rid1, ready1 = launch_caller(Caller)
check("T1 caller launched the run through the door", bool(rid1) and ready1, f"rid={rid1} ready={ready1}")
if rid1 and ready1:
    rpid = wfpid_of(rid1)
    t0 = time.time()                            # preconditions race-free, generous
    while time.time() - t0 < 10:
        rpid = wfpid_of(rid1)
        if rpid > 0 and alive(rpid):
            break
        time.sleep(0.1)
    kids_before = set(descendants(p1.pid))
    runner_in_tree = f"{os.sep}wf.py run {rid1}" in cmdline(rpid)
    check("T1 pre-sweep: runner is live, child is cooking", alive(rpid) and runner_in_tree
          and bool(read_child_pids(scratch / "fpid-caller.log")), f"rpid={rpid}")
    check("T1 escape law: by handle(run) return the runner is already OUT of the "
          "caller's descendant subtree (sweep can never snapshot it)",
          rpid not in kids_before, "runner still hangs under the caller — a live-parent "
          "descendants snapshot targets it (the #8 incident shape)")
    aimed = registry_sweep(p1.pid)
    try:
        p1.wait(timeout=10)
    except Exception:
        pass
    survived = alive(rpid) and f"{os.sep}wf.py run {rid1}" in cmdline(rpid)
    # Adoption target read while the survivor is still LIVE (settling later would
    # race the runner's own natural exit -> unreadable /proc, a flaky -1).
    ppid_after = ppid_of(rpid) if survived else -1
    check("T1 adoption target: orphan adopted by the enclosing subreaper fixture, "
          "never the dead caller (ppid == test process, not caller)",
          (ppid_after == os.getpid()) if (_SUBREAPER and survived)
          else (ppid_after not in (p1.pid, -1) if survived else False),
          f"ppid={ppid_after} want={os.getpid() if _SUBREAPER else 'not caller'}")
    check("T1 runner SURVIVES the caller-tree sweep incl. the fixture's group-kill "
          "(property (a): escaped the ordinary caller tree — NOT an enclosing-"
          "subreaper/service-survival claim)", survived,
          f"runner pid {rpid} dead — reaped by the sweep aimed at {sorted(aimed)[:6]}…")
    st1 = settle(rid1)
    check("T1 run COMMITS after the sweep (children survived with the runner)",
          st1.get("status") == "done" and (st1.get("nodes") or {}).get("slow", {}).get("status") == "done",
          json.dumps({k: st1.get(k) for k in ("status", "runner_live", "done", "total")}))
    check("T1 summary written by the surviving runner",
          (runs / rid1 / "summary.md").exists())
    fake_kids = [k for k in read_child_pids(scratch / "fpid-caller.log") if alive(k)]
    for k in fake_kids:
        _kill(k)

# ---- T2 PROPERTY (a): caller run -> exit -> caller-tree completion sweep -------
p2, rid2, ready2 = launch_caller(CallerExit)
check("T2 caller launched and exited", bool(rid2) and ready2, f"rid={rid2} ready={ready2}")
if rid2 and ready2:
    rpid2 = wfpid_of(rid2)
    snap2 = set(descendants(p2.pid))          # registry snapshot: taken at spawn/turn boundary
    try:
        p2.wait(timeout=10)                    # the caller exits (turn end)
    except Exception:
        pass
    for p2p in sorted(snap2):                  # completion sweep over the snapshot
        if alive(p2p):
            _kill(p2p)
    t0 = time.time()
    while any(alive(p) for p in snap2) and time.time() - t0 < 2.0:
        time.sleep(0.02)
    for p2p in sorted(snap2):
        if alive(p2p):
            _kill(p2p)
    survived2 = alive(rpid2) and f"{os.sep}wf.py run {rid2}" in cmdline(rpid2)
    check("T2 runner alive after caller exit + completion snapshot sweep", survived2,
          f"runner pid {rpid2} dead; snapshot was {sorted(snap2)[:6]}…")
    st2 = settle(rid2)
    check("T2 run COMMITS after caller-exit sweep (no door respawn — status polls only)",
          st2.get("status") == "done" and (st2.get("nodes") or {}).get("slow", {}).get("status") == "done",
          json.dumps({k: st2.get(k) for k in ("status", "runner_live", "done", "total")}))

# ---- T3 admission law under daemonization ---------------------------------------
# (a) contender against a LIVE run: exactly one WORKFLOW_BUSY loser, and the loser
# must NOT stamp wf.pid (door must not stamp a pid it cannot observe).
r3 = call(action="run", graph=SLOW)
rid3 = r3["run_id"]
t0 = time.time()
while wfpid_of(rid3) <= 0 and time.time() - t0 < 15:
    time.sleep(0.05)
winner = wfpid_of(rid3)
rdir3 = runs / rid3
hw._spawn_runner(rdir3)                        # guaranteed loser (flock held)
time.sleep(1.0)
busy = sum(1 for line in (rdir3 / "runner.log").read_text(errors="replace").splitlines()
           if "WORKFLOW_BUSY" in line)
check("T3a concurrent spawn against live runner -> exactly one WORKFLOW_BUSY", busy == 1, f"busy={busy}")
check("T3a loser did NOT stamp wf.pid (== the live winner's pid; ready-pipe stamp law)",
      wfpid_of(rid3) == winner and alive(winner), f"wf.pid={wfpid_of(rid3)} winner={winner}")

# (b) fresh run dir (no runner yet): two CONCURRENT spawns -> exactly one loser,
# exactly one live runner, wf.pid == that live runner.
G3 = dict(SLOW, name="daemonize8-race")
g3 = {"name": "daemonize8-race", "nodes": SLOW["nodes"]}
base3 = time.strftime("%Y%m%d-%H%M%S") + "-daemonize8race"
rdir4 = runs / base3
(rdir4 / "nodes").mkdir(parents=True); (rdir4 / "gates").mkdir()
(rdir4 / "graph.json").write_text(json.dumps(g3))
(rdir4 / "run.json").write_text(json.dumps({"name": g3["name"],
                                            "duckwork_bin": os.environ["DUCKWORK_WF_DUCKWORK_BIN"]}))
th = [threading.Thread(target=lambda: hw._spawn_runner(rdir4)) for _ in range(2)]
for t in th: t.start()
for t in th: t.join(timeout=15)
time.sleep(1.2)
busy4 = sum(1 for line in (rdir4 / "runner.log").read_text(errors="replace").splitlines()
            if "WORKFLOW_BUSY" in line)
check("T3b double-spawn on a fresh run -> exactly one WORKFLOW_BUSY loser", busy4 == 1, f"busy={busy4}")
live = [pid for pid, _ in proc_map().items()
        if f"{os.sep}wf.py run {base3}" in cmdline(pid)]
check("T3b exactly one live runner for the raced run", len(live) == 1, f"live={live}")
check("T3b wf.pid names that live runner (ready-pipe handshake, door never stamps the loser)",
      bool(live) and wfpid_of(base3) == live[0] and alive(live[0]), f"wf.pid={wfpid_of(base3)} live={live}")
st3 = settle(base3)
check("T3b the raced run still completes", st3.get("status") == "done", st3.get("status"))

# ---- cleanup: ONLY this test's own runs (never another suite's processes) ------
for pid, _ in proc_map().items():
    c = cmdline(pid)
    if (f"{os.sep}wf.py run {base3}" in c or f"{os.sep}wf.py run {rid1}" in c
            or f"{os.sep}wf.py run {rid2}" in c or f"{os.sep}wf.py run {rid3}" in c
            or f"{os.sep}wf.py run {rid0}" in c):
        _kill(pid)
for k in read_child_pids(scratch / "fpid-caller.log") + read_child_pids(scratch / "fpid-caller_exit.log"):
    _kill(k)
while True:
    try:
        if os.waitpid(-1, os.WNOHANG)[0] == 0:
            break
    except ChildProcessError:
        break

print(f"daemonize8: {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
