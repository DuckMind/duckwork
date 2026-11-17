#!/usr/bin/env python3
"""est-6226 — a gateway-restart SIGTERM wave must not kill live runners as
collateral, and when it DOES signal-kill one, the death must be attributed
honestly.

Witnessed shape (2026-10-06 10:06:17-19Z, run 20261006-041852-fb-fix-fb609):
the s6-supervise parent SIGTERMs the gateway; the wave propagates beyond the
gateway's own session and kills workflow runners spawned under the caller's
process family. The runner's handler recorded reason="terminated: SIGTERM" —
indistinguishable from a lane death — which fed ALERT storms and wrong
re-dispatch decisions (the dispatcher burned ~6 phantom-verifying wakes; the
reaper mass-revived 9 lanes at once).

Law pinned here:
  A. SPAWN DETACH: every runner spawn path (initial door spawn AND the
     wait-driven respawn through the same seam) places the runner in its OWN
     session — os.getsid(runner_pid) == runner_pid, never the caller's — so a
     session/group-directed wave aimed at the caller cannot reach it.
  B. WAVE SURVIVAL: SIGTERMing the CALLER's process group (the s6 wave shape,
     reproduced via /proc semantics with a real parent process) kills the
     caller but NOT the runner; the runner lives on and records its own later
     exit itself.
  C. HONEST ATTRIBUTION: a runner that IS signal-killed externally records
     reason="terminated: SIGTERM (external: source unknown)" — the external
     tag states the CLASS only, never the sender (a handler cannot see who
     fired; naming "gateway restart" from os.kill alone is false provenance —
     adversary probe 2026-10-06). Gateway-restart correlation is the reaper's
     separate file-evidenced "; gw-restart window match" clause. The door
     reaper makes the death loud with that observed
     reason, the read model keeps the run 'interrupted' (never 'failed'),
     the classification says respawn-eligible / death_class=external_kill,
     and NO node.failed event or verdict pollution is produced. The phantom
     gate stays accurate: a SIGKILLed runner with NO record still reads
     "crashed (no exit record)", distinct from the recorded external kill.

RED on the pre-fix base: the reason carries no external tag,
wfcommon.is_external_kill does not exist, and the reaper stays silent on a
recorded external death (it only fires on "crashed (no exit record)").
Standalone, stdlib-only: python3 tests/test_gateway_sigterm_detach_6226.py
"""
import importlib.util
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

checks = 0
failures = 0


def check(label, cond, detail=""):
    global checks, failures
    checks += 1
    if cond:
        print(f"PASS {label}")
    else:
        failures += 1
        print(f"FAIL {label}: {detail}")


FAKE = str(HERE / "fake")
PARENT_STUB = str(HERE / "stub_gwsigterm6226_parent.py")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ev_lines(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def mk_run(runs, run_id):
    r = runs / run_id
    if r.exists():
        shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [
        {"id": "work", "type": "agent", "goal": "hang a while"}]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 120}))
    return r


def wait_for(fn, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.05)
    return None


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return not st.startswith("Z")


def kill_soft(pid):
    for kw, sig in (({"killpg": True}, signal.SIGKILL), ({"killpg": False}, signal.SIGKILL)):
        try:
            if kw["killpg"]:
                os.killpg(pid, sig)
            else:
                os.kill(pid, sig)
            return
        except OSError:
            continue


def spawn_record(r):
    p = r / "nodes" / "work.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


with tempfile.TemporaryDirectory(prefix=".tmp-gwsig6226-", dir=HERE,
                                 ignore_cleanup_errors=True) as td:
    home = Path(td) / "home"
    runs = home / "workflows"
    runs.mkdir(parents=True)
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["FAKE_LOG"] = str(Path(td) / "fake.log")
    os.environ["FAKE_MODE"] = "hang"
    os.environ["FAKE_HANG_SEC"] = "300"

    wfcommon = load("gws6226_wfcommon", ROOT / "wfcommon.py")
    door = load("gws6226_door", ROOT / "__init__.py")
    os.environ["WF_RUNS_ROOT"] = str(runs)
    import wf_test_isolation as _iso6226
    _iso6226.install(door)

    # ---------- A. spawn detach: runner owns its session, every spawn path ----------
    r = mk_run(runs, "g6226-detach")
    door._spawn_runner(r)
    rec = wait_for(lambda: (lambda rec_: rec_ if rec_ and rec_.get("pid") else None)(spawn_record(r)))
    check("A setup: runner admitted and child spawned (spawn record claims running)",
          bool(rec) and rec.get("status") == "running", json.dumps(rec)[:200] if rec else "none")
    runner_pid = None
    try:
        runner_pid = int((r / "wf.pid").read_text().strip())
    except (OSError, ValueError):
        pass
    check("A: runner pid self-stamped and live", bool(runner_pid) and alive(runner_pid),
          f"wf.pid={runner_pid}")
    own_sid = os.getsid(os.getpid())
    child_sid = None
    try:
        child_sid = os.getsid(runner_pid)
    except OSError:
        pass
    check("A: initial spawn puts the runner in its OWN session (setsid at spawn)",
          child_sid is not None and child_sid == runner_pid and child_sid != own_sid,
          f"getsid(runner)={child_sid} runner_pid={runner_pid} caller_sid={own_sid}")

    # respawn path: the dead runner replaced through the door's resume seam
    # must land in a session of its OWN too (same spawn seam — the reaper's
    # revive rides the door's wait-respawn, which is _spawn_runner).
    kill_soft(runner_pid)
    wait_for(lambda: not alive(runner_pid))
    door.act_wait({"run_id": r.name, "timeout": 2})

    def _read_pid(r=r):
        try:
            return int((r / "wf.pid").read_text().strip())
        except (OSError, ValueError):
            return None

    new_pid = wait_for(lambda: (lambda p: p if p and p != runner_pid else None)(_read_pid()))
    check("A: the respawn path produced a new live runner", bool(new_pid) and alive(new_pid),
          f"new pid {new_pid}")
    if new_pid:
        try:
            new_sid = os.getsid(new_pid)
        except OSError:
            new_sid = None
        check("A: respawned runner is ALSO its own session leader",
              new_sid == new_pid and new_sid != own_sid,
              f"getsid={new_sid} pid={new_pid} caller_sid={own_sid}")
        kill_soft(new_pid)
        wait_for(lambda: not alive(new_pid))

    # ---------- B. the wave shape: SIGTERM the caller's group, runner lives ----------
    rb = mk_run(runs, "g6226-wave")
    wave_log = Path(td) / "wave-parent.log"
    parent = subprocess.Popen(
        [sys.executable, PARENT_STUB, str(ROOT), str(rb), str(wave_log)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True,
        env=dict(os.environ, WF_RUNS_ROOT=str(runs), DUCKWORK_HOME=str(home),
                 PYTHONDONTWRITEBYTECODE="1"))
    def _read_ready():
        rl, _, _ = select.select([parent.stdout], [], [], 0)
        if not rl:
            return None
        line = parent.stdout.readline()
        return line if line and line.strip() else None

    ready = wait_for(_read_ready, timeout=30)
    runner_b = int(ready.strip()) if ready and ready.strip().isdigit() else None
    check("B setup: caller-tree parent spawned a runner through the door seam",
          bool(runner_b) and alive(runner_b), f"runner pid {runner_b}")
    if runner_b:
        # the s6 wave: SIGTERM the WHOLE caller group (parent is its leader)
        try:
            os.killpg(os.getpgid(parent.pid), signal.SIGTERM)
        except OSError:
            pass
        parent_dead = wait_for(lambda: not alive(parent.pid), timeout=15)
        # grace: give any propagating wave every chance to land
        time.sleep(1.0)
        check("B: the wave killed the caller", parent_dead and not alive(parent.pid))
        check("B: the SIGTERM wave did NOT reach the runner (own session at spawn)",
              alive(runner_b), f"runner {runner_b} died with the caller's group")
        # the survivor keeps working: it must reach and record its OWN later exit
        st_b = wait_for(lambda: (lambda rec_: rec_ if rec_ and rec_.get("pid") else None)(spawn_record(rb)),
                        timeout=15)
        check("B: the surviving runner owns the run (spawn record carries a pid)",
              bool(st_b), json.dumps(st_b)[:120] if st_b else "none")
        # and it records its own exit later, honestly, when WE end it (part C
        # vocabulary): kill -TERM the survivor, its handler writes the record.
        os.kill(runner_b, signal.SIGTERM)
        died = wait_for(lambda: not alive(runner_b), timeout=20)
        check("B: the runner records its OWN exit after the later signal-kill",
              died and (rb / "runner_exit.json").exists(),
              (rb / "runner_exit.json").read_text()[:200]
              if (rb / "runner_exit.json").exists() else "no runner_exit.json")
        rx_b = None
        try:
            rx_b = json.loads((rb / "runner_exit.json").read_text())
        except (OSError, ValueError):
            pass
        check("B: the recorded reason carries the external tag",
              bool(rx_b) and str(rx_b.get("reason", "")).startswith("terminated: SIGTERM")
              and "(external:" in str(rx_b.get("reason", "")),
              json.dumps(rx_b)[:200] if rx_b else "none")

    # ---------- C. honest attribution + respawn-eligible classification ----------
    rc = mk_run(runs, "g6226-attr")
    door._spawn_runner(rc)
    rec_c = wait_for(lambda: (lambda rec_: rec_ if rec_ and rec_.get("pid") else None)(spawn_record(rc)))
    runner_c = int((rc / "wf.pid").read_text().strip()) if (rc / "wf.pid").exists() else None
    check("C setup: runner live with a running child claim", bool(rec_c) and alive(runner_c),
          f"runner={runner_c}")
    child_c = (rec_c or {}).get("pid")
    os.kill(runner_c, signal.SIGTERM)      # the wave reaching the runner itself
    died_c = wait_for(lambda: not alive(runner_c))
    check("C: runner is dead after the external SIGTERM", bool(died_c))
    rx_c = None
    try:
        rx_c = json.loads((rc / "runner_exit.json").read_text())
    except (OSError, ValueError):
        pass
    reason_c = str((rx_c or {}).get("reason") or "")
    check("C: runner_exit records an EXTERNAL signal death (not a lane-failure shape)",
          reason_c.startswith("terminated: SIGTERM") and "(external:" in reason_c,
          json.dumps(rx_c)[:250] if rx_c else "no runner_exit.json")
    check("C: the name is distinguishable from the bare lane-death vocabulary",
          reason_c != "terminated: SIGTERM", repr(reason_c))
    # honesty pin: the probe here IS a plain os.kill — no gateway was touched.
    # The handler cannot see the sender, so the tag must not NAME one: the
    # bare string claiming "gateway restart" was the adversary's false-
    # provenance finding (signal_probe.py, 2026-10-06).
    check("C: the reason states the class, never an unproven sender",
          "gateway restart" not in reason_c and "source unknown" in reason_c,
          repr(reason_c))
    # classification helper (the reaper/dispatcher's view): external kill =>
    # respawn-eligible, NOT a node failure.
    is_ext = getattr(wfcommon, "is_external_kill", None)
    check("C: the read model exposes an external-kill classifier (wfcommon.is_external_kill)",
          callable(is_ext), "attribute missing on wfcommon")
    if callable(is_ext):
        check("C: classifier says the recorded death IS an external kill",
              bool(is_ext(reason_c)), repr(reason_c))
        check("C: classifier does NOT call a lane failure (crashed:) external",
              not is_ext("crashed: RuntimeError: boom"))
        check("C: classifier does NOT call a clean exit external",
              not is_ext("done"))
    # the door reaper makes the recorded external death loud (no longer silent:
    # pre-fix it only fired on "crashed (no exit record)").
    pre = ev_lines(rc)
    reap = getattr(door, "_reap_silent_death", None)
    if callable(reap):
        reap(rc)
    post = ev_lines(rc)
    new_ev = post[len(pre):]
    reaped = [e for e in new_ev if e.get("event") == "runner.reaped"]
    check("C: reaper appends exactly one runner.reaped for the external death",
          len(reaped) == 1, json.dumps(new_ev)[:300])
    check("C: runner.reaped carries the observed external reason verbatim",
          bool(reaped) and str(reaped[0].get("reason", "")).startswith("terminated: SIGTERM")
          and "(external:" in str(reaped[0].get("reason", "")),
          json.dumps(reaped[0])[:250] if reaped else "none")
    check("C: NO node.failed anywhere (external kill is never a verdict)",
          not [e for e in ev_lines(rc) if e.get("event") == "node.failed"],
          json.dumps([e for e in ev_lines(rc) if e.get("event") == "node.failed"])[:200])
    st_c = door.run_state(rc)
    check("C: the read model keeps the run interrupted, never failed",
          st_c and st_c.get("status") == "interrupted",
          (st_c or {}).get("status"))
    check("C: the recorded external verdict is NOT promoted to a verdict/failed",
          st_c and not str((st_c.get("runner_exit") or {}).get("reason", "")).startswith("crashed:"),
          json.dumps(st_c.get("runner_exit"))[:200] if st_c else "none")
    # door view exposes the classification for reaper/dispatcher consumption
    view = door.act_status({"run_id": rc.name})
    rxv = view.get("runner_exit") or {}
    check("C: the door status view marks the death respawn-eligible / external_kill",
          rxv.get("respawn_eligible") is True and rxv.get("death_class") == "external_kill",
          json.dumps(rxv)[:250])
    # the phantom gate stays accurate: respawn must actually land a live runner
    res = door.act_wait({"run_id": rc.name, "timeout": 2})

    def _read_pid_c(r=rc, excl=runner_c):
        try:
            v = int((r / "wf.pid").read_text().strip())
        except (OSError, ValueError):
            return None
        return v if v and v != excl else None

    new_c = wait_for(_read_pid_c, timeout=20)
    check("C: an external-killed lane IS respawn-eligible (act_wait lands a live runner)",
          bool(new_c) and alive(new_c), f"new runner {new_c}; wait -> {json.dumps(res)[:160]}")
    if child_c and alive(child_c):
        kill_soft(child_c)
    if new_c and alive(new_c):
        kill_soft(new_c)
        wait_for(lambda: not alive(new_c))

    # ---------- D. phantom gate: an UNRECORDED death stays distinguishable ----------
    rd = mk_run(runs, "g6226-sigkill")
    door._spawn_runner(rd)
    rec_d = wait_for(lambda: (lambda rec_: rec_ if rec_ and rec_.get("pid") else None)(spawn_record(rd)))
    runner_d = int((rd / "wf.pid").read_text().strip()) if (rd / "wf.pid").exists() else None
    os.kill(runner_d, signal.SIGKILL)      # no handler can run — no record
    died_d = wait_for(lambda: not alive(runner_d))
    # The crash read asserts through runner_alive's ONE liveness law
    # (runner_lock flock HELD => live). The kernel releases the flock
    # ASYNCHRONOUSLY on death (delayed fput), so a raw os.kill(0)-dead pid can
    # still momentarily read as alive — the CI flake (run 37465629705):
    # runner_exit_read raced that window and returned None ("null"), not a
    # code defect. Wait on the SAME law the read consults before asserting.
    settled_d = wait_for(lambda: not wfcommon.runner_alive(rd), timeout=15)
    check("D setup: SIGKILLed runner recorded NOTHING",
          bool(died_d) and bool(settled_d)
          and not (rd / "runner_exit.json").exists())
    rx_d = wfcommon.runner_exit_read(rd)
    check("D: the phantom gate still reads the unrecorded death as a crash",
          (rx_d or {}).get("reason") == "crashed (no exit record)",
          json.dumps(rx_d)[:160])
    if callable(is_ext):
        check("D: the unrecorded crash is NOT classified as an external kill",
              not is_ext((rx_d or {}).get("reason")), json.dumps(rx_d)[:160])
    child_d = (rec_d or {}).get("pid")
    if child_d:
        kill_soft(child_d)

print(f"\ngateway_sigterm_detach_6226: {checks} checks, {failures} failure(s)")
sys.exit(1 if failures else 0)
