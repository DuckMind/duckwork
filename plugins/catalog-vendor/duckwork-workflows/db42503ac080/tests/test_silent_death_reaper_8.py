#!/usr/bin/env python3
"""#8 fix-law item 2 (crash-visibility half): a door respawn after a SILENT runner
death must make the death loud BEFORE re-spawning anything.

The failure mode this pins (issue #8, incidents 1-6): the runner + its children are
SIGKILLed by an out-of-band sweep. No runner_exit.json exists (SIGKILL records
nothing), events.jsonl's last runner-side line is from before the death, and node
records still claim status="running" — every watcher shape (tail|grep, offset loops,
wait) sees silence. act_wait then respawns WITHOUT leaving a trace of the death.

Law pinned here (door respawn path only — reads stay pure):
  * exactly one `runner.reaped` event (prev_pid + observed reason) appended to
    events.jsonl before Popen of the replacement runner;
  * one `node.interrupted` event per node record claiming a running child whose
    pid fails the ONE verification law (_verify_spawn_rec);
  * a respawned child that is STILL VERIFIABLY ALIVE is adopted, never interrupted;
  * a clean parked exit (valid runner_exit.json, e.g. a gate hold) is not a silent
    death — no reaper events;
  * a fresh `run` spawn (no prior pid file) writes no reaper events;
  * `status` (the read path) never appends anything, ever.

RED on f2991f2: the bridge does not exist — after the sweep, events.jsonl holds only
the pre-death lines and act_wait leaves zero trace of the reap.
"""
import importlib.util
import json
import os
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def ev_lines(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def mk_run(runs, run_id, goal):
    r = runs / run_id
    if r.exists():
        shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [
        {"id": "work", "type": "agent", "goal": goal}]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 60}))
    return r


def wait_for(fn, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.1)
    return None


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return not state.startswith("Z")


def kill_tree(r):
    """Sweep the current runner (own pgid via start_new_session) and every child
    the spawn records claim — the incident shape is runner+children dead together."""
    for f in (r / "nodes").glob("*.json"):
        try:
            pid = int(json.loads(f.read_text()).get("pid"))
        except (ValueError, TypeError, AttributeError):
            continue
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        pid = int((r / "wf.pid").read_text())
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            os.kill(pid, signal.SIGKILL)
    except (OSError, ValueError):
        pass


with tempfile.TemporaryDirectory(prefix="reaper8-", dir=HERE,
                                 ignore_cleanup_errors=True) as td:
    home = Path(td) / "home"
    runs = home / "workflows"
    runs.mkdir(parents=True)
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
    os.environ["FAKE_LOG"] = str(Path(td) / "fake.log")
    os.environ["FAKE_MODE"] = "hang"
    os.environ["FAKE_HANG_SEC"] = "120"

    wfcommon = load("reaper_wfcommon", ROOT / "wfcommon.py")
    door = load("reaper_door", ROOT / "__init__.py")
    os.environ["WF_RUNS_ROOT"] = str(runs)  # #71 r5: env pin — resolver takes this over settings/home default
    import wf_test_isolation as _iso71_reaper8; _iso71_reaper8.install(door)  # #71 r5: pin settings.runs_root too

    # ---- A. silent death -> act_wait respawn must leave the reap trace ----
    r = mk_run(runs, "r8-silent", "hang a while")
    door._spawn_runner(r)
    spawned = wait_for(lambda: (lambda rec: rec if rec and rec.get("pid") else None)(
        (lambda p: json.loads(p.read_text()) if p.exists() else None)(r / "nodes" / "work.json")))
    check("setup: child spawned with a spawn record claiming running",
          bool(spawned) and spawned.get("status") == "running", json.dumps(spawned)[:200])
    child_pid = spawned["pid"]
    runner_pid = int((r / "wf.pid").read_text())

    kill_tree(r)
    dead = wait_for(lambda: not alive(runner_pid) and not alive(child_pid))
    check("setup: runner and child are both dead (sweep simulated)", dead)
    check("setup: silent — no runner_exit.json exists", not (r / "runner_exit.json").exists())
    pre_events = ev_lines(r)
    check("setup: node record STILL claims running after the sweep",
          json.loads((r / "nodes" / "work.json").read_text()).get("status") == "running")

    res = door.act_wait({"run_id": r.name, "timeout": 2})
    ev = ev_lines(r)
    reaped = [e for e in ev if e.get("event") == "runner.reaped"]
    interrupted = [e for e in ev if e.get("event") == "node.interrupted"]
    check("reap: exactly one runner.reaped event appended by the respawn path",
          len(reaped) == 1, f"{len(reaped)} in {[e.get('event') for e in ev]}")
    check("reap: runner.reaped names the dead runner pid",
          bool(reaped) and reaped[0].get("prev_pid") == runner_pid,
          json.dumps(reaped[0])[:200] if reaped else "none")
    check("reap: reason observed from files, not invented",
          bool(reaped) and isinstance(reaped[0].get("reason"), str)
          and "crashed" in reaped[0]["reason"],
          json.dumps(reaped[0])[:200] if reaped else "none")
    check("reap: exactly one node.interrupted for the falsely-claimed node",
          len(interrupted) == 1 and interrupted[0].get("node") == "work",
          json.dumps(interrupted)[:200])
    check("reap: interrupted event carries the dead child pid",
          bool(interrupted) and interrupted[0].get("pid") == child_pid,
          json.dumps(interrupted[0])[:200] if interrupted else "none")
    resumed_ix = [i for i, e in enumerate(ev) if e.get("event") == "run.resumed"]
    reaped_ix = [i for i, e in enumerate(ev) if e.get("event") == "runner.reaped"]
    check("reap: the trace rides BEFORE the replacement runner's own first event",
          bool(resumed_ix) and bool(reaped_ix) and max(reaped_ix) < resumed_ix[0] + 1
          and min(reaped_ix) < resumed_ix[0],
          f"reaped@{reaped_ix} resumed@{resumed_ix}")
    check("reap: respawn still happened (act_wait behavior unchanged)",
          isinstance(res, dict) and "error" not in res, json.dumps(res)[:200])
    new_runner = wait_for(lambda: (lambda p: p if p and p != runner_pid else None)(
        (lambda f: int(f.read_text()) if f.exists() else None)(r / "wf.pid")))
    check("reap: the replacement runner is live", bool(new_runner) and alive(new_runner),
          f"new pid {new_runner}")
    kill_tree(r)
    wait_for(lambda: not alive(new_runner))

    # determinism check: the reaper itself is append-only — call it directly on a
    # frozen dir (no live runner to race the node records) and byte-compare.
    r4b = mk_run(runs, "r4b-intact", "hang a while")
    frozen = {"status": "running", "pid": 999999, "skey": "wf:r4b-intact:work:deadbeef.000001",
              "attempt": 1, "started": "2026-01-01T00:00:00+00:00",
              "efp": wfcommon.efp({"work": {"id": "work", "type": "agent", "goal": "hang a while"}},
                                  {"id": "work", "type": "agent", "goal": "hang a while"}),
              "fp_rule_version": wfcommon.FP_RULE_VERSION}
    (r4b / "nodes" / "work.json").write_text(json.dumps(frozen))
    (r4b / "wf.pid").write_text("999998")
    (r4b / "events.jsonl").write_text("")
    before_bytes = {p.name: p.read_bytes() for p in (r4b / "nodes").glob("*.json")}
    _reap = getattr(door, "_reap_silent_death", None)
    check("bridge: the door carries a crash-visibility reaper (_reap_silent_death)",
          callable(_reap), "attribute missing on the door module")
    if callable(_reap):
        _reap(r4b)
    after_bytes = {p.name: p.read_bytes() for p in (r4b / "nodes").glob("*.json")}
    check("reap: the falsely-claimed records are left byte-identical (append-only reaper)",
          before_bytes == after_bytes,
          f"{ {k: (before_bytes[k] != after_bytes.get(k)) for k in before_bytes} }")
    ev4b = ev_lines(r4b)
    check("reap: direct reaper call emits the pair once (prev_pid from wf.pid)",
          [e.get("event") for e in ev4b] == ["runner.reaped", "node.interrupted"]
          and ev4b[0]["prev_pid"] == 999998 and ev4b[1]["pid"] == 999999,
          json.dumps(ev4b)[:300])
    # a LIVE runner (flock held — the ONE admission proof) short-circuits the
    # reaper regardless of node claims: same-process two-fd probe, the shape
    # tests/test_cross_container_liveness_91b9a3de.py pins.
    r4c = mk_run(runs, "r4c-live", "hang a while")
    (r4c / "nodes" / "work.json").write_text(json.dumps(frozen))
    (r4c / "wf.pid").write_text("999998")
    (r4c / "events.jsonl").write_text("")
    import fcntl as _fc
    hold = os.open(str(r4c / "runner.lock"), os.O_RDWR | os.O_CREAT)
    _fc.flock(hold, _fc.LOCK_EX)
    try:
        if callable(_reap):
            _reap(r4c)
    finally:
        _fc.flock(hold, _fc.LOCK_UN)
        os.close(hold)
    check("reap: a live runner (held flock) short-circuits — no events",
          not ev_lines(r4c), json.dumps(ev_lines(r4c))[:200])

    # ---- B. adopted live child is never interrupted ----
    r2 = mk_run(runs, "r8-adopt", "hang a while")
    door._spawn_runner(r2)
    sp2 = wait_for(lambda: (lambda rec: rec if rec and rec.get("pid") else None)(
        (lambda p: json.loads(p.read_text()) if p.exists() else None)(r2 / "nodes" / "work.json")))
    runner2 = int((r2 / "wf.pid").read_text())
    child2 = sp2["pid"]
    os.kill(runner2, signal.SIGKILL)
    wait_for(lambda: not alive(runner2))
    check("setup B: runner dead, child STILL alive", alive(child2))
    door.act_wait({"run_id": r2.name, "timeout": 2})
    ev2 = ev_lines(r2)
    interrupted2 = [e for e in ev2 if e.get("event") == "node.interrupted"]
    check("adopt: a verifiably-alive child gets NO node.interrupted",
          not interrupted2, json.dumps(interrupted2)[:200])
    kill_tree(r2)
    wait_for(lambda: not alive(child2))
    # the replacement runner also spawned its own child (adoption happens at the
    # runner's own wave scheduling); sweep whatever tree exists now.

    # ---- C. clean parked exit is not a silent death ----
    r3 = mk_run(runs, "r8-held", "hang a while")
    (r3 / "graph.json").write_text(json.dumps({"name": "r8-held", "nodes": [
        {"id": "g", "type": "gate", "question": "proceed?", "options": ["yes"]}]}))
    out3 = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", r3.name],
                          env=dict(os.environ), capture_output=True, text=True, timeout=60)
    check("setup C: run parked at the gate with a recorded exit",
          out3.stdout.startswith("WORKFLOW_HELD") and (r3 / "runner_exit.json").exists(),
          out3.stdout[:120])
    before3 = len(ev_lines(r3))
    door.act_wait({"run_id": r3.name, "timeout": 2})
    ev3 = ev_lines(r3)
    check("hold: resuming a PARKED (cleanly exited) run appends no reaper events",
          not [e for e in ev3 if e.get("event") in ("runner.reaped", "node.interrupted")],
          json.dumps([e.get("event") for e in ev3[before3:]])[:200])
    kill_tree(r3)

    # ---- D. reads never write; fresh run writes nothing ----
    r4 = mk_run(runs, "r8-fresh", "quick task")
    del os.environ["FAKE_MODE"]
    door.act_status({"run_id": r4.name})
    ev4 = ev_lines(r4)
    check("purity: status on an untouched run appends nothing", not ev4, json.dumps(ev4)[:200])
    st4 = door.run_state(r4)
    check("purity: run_state is never a writer", not ev_lines(r4))
    # a run with a dead pid + running claim: status must STILL not write the reap
    # (the reaper fires on the respawn path only; reads stay pure).
    r5 = mk_run(runs, "r5-readonly", "hang a while")
    door._spawn_runner(r5)
    sp5 = wait_for(lambda: (lambda rec: rec if rec and rec.get("pid") else None)(
        (lambda p: json.loads(p.read_text()) if p.exists() else None)(r5 / "nodes" / "work.json")))
    runner5 = int((r5 / "wf.pid").read_text())
    os.kill(runner5, signal.SIGKILL)
    wait_for(lambda: not alive(runner5))
    try:
        os.kill(sp5["pid"], signal.SIGKILL)
    except ProcessLookupError:
        pass   # the fake child already died with its runner — nothing to sweep
    wait_for(lambda: not alive(sp5["pid"]))
    mid = len(ev_lines(r5))
    st5 = door.act_status({"run_id": r5.name})
    check("purity: act_status on a silently-dead run reports interrupted and writes nothing",
          st5["status"] == "interrupted" and len(ev_lines(r5)) == mid, st5["status"])
    kill_tree(r5)

    # ---- E. PR #82 review F1+F4: fan-out liveness is per-item-index ----
    # One live item (adoption owns it) + one dead item (interrupted), real
    # processes verified by the ONE law through the indexed path. The event
    # vocabulary must be {node: <parent id>, index: N} (F4), never "fan0".
    fo = {"id": "fan", "type": "agent", "fanout": {"items": ["a", "b"], "goal": "{item}"}}
    r6 = runs / "r6-fanout"
    r6.mkdir()
    (r6 / "nodes").mkdir()
    (r6 / "gates").mkdir()
    (r6 / "graph.json").write_text(json.dumps({"name": r6.name, "nodes": [fo]}))
    (r6 / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 2}))
    (r6 / "wf.pid").write_text("99999998")
    byid_fo = {"fan": fo}
    kids = []
    try:
        for i in range(2):
            sk = f"wf:r6-fanout:fan:{i}:fixture#a1"
            rec = {"status": "running", "skey": sk, "attempt": 1,
                   "started": "2026-01-01T00:00:00+00:00",
                   "efp": wfcommon.efp(byid_fo, fo),
                   "fp_rule_version": wfcommon.FP_RULE_VERSION}
            if i == 0:   # live item: a real child carrying the skey in argv
                kid = subprocess.Popen([sys.executable, "-c",
                                        "import time; time.sleep(120)", sk],
                                       start_new_session=True)
                kids.append(kid)
                rec["pid"] = kid.pid
            else:        # dead item: a pid that cannot exist
                rec["pid"] = 99999997
            (r6 / "nodes" / f"fan.{i}.json").write_text(json.dumps(rec))
        check("setup E: live fan item verifies under the ONE law (indexed entry point)",
              bool(wfcommon.active_child(r6, fo, byid_fo, 0)))
        if callable(_reap):
            _reap(r6)
        ev6 = ev_lines(r6)
        int6 = [e for e in ev6 if e.get("event") == "node.interrupted"]
        check("fanout (F1): a verifiably-live fan-out item is NOT interrupted",
              [e.get("index") for e in int6] == [1], json.dumps(int6)[:300])
        check("fanout (F4): the dead item keeps the runner's item vocabulary",
              bool(int6) and int6[0].get("node") == "fan" and int6[0].get("index") == 1
              and int6[0].get("pid") == 99999997, json.dumps(int6)[:300])
        # F3: the SAME observed death must not be re-appended on a retry
        # (offset watchers see one runner.reaped per death, pre-resume).
        if callable(_reap):
            _reap(r6)
            _reap(r6)
        reaped6 = [e for e in ev_lines(r6) if e.get("event") == "runner.reaped"]
        check("repeat (F3): re-observing the same frozen death appends once",
              len(reaped6) == 1, json.dumps([e.get("event") for e in ev_lines(r6)])[:300])
        # F3 is CONTENT-aware, not a mute switch: when the item-0 child dies
        # after the first reap, the changed scene is NEW evidence — exactly one
        # additional node.interrupted (index 0), still one runner.reaped.
        kids[0].kill()
        kids[0].wait()
        if callable(_reap):
            _reap(r6)
        ev6b = ev_lines(r6)
        int6b = [e for e in ev6b if e.get("event") == "node.interrupted"]
        check("changed-scene (F3): a child dying after the first reap is recorded",
              [e for e in ev6b if e.get("event") == "runner.reaped"].__len__() == 1
              and len(int6b) == 2 and {e.get("index") for e in int6b} == {0, 1},
              json.dumps([e.get("event") for e in ev6b])[:300])
    finally:
        for kid in kids:
            kid.kill()
            kid.wait()

    # ---- F. PR #82 review F2: amending a cleanly held run is not a death ----
    # act_amend replaces graph.json, which makes the recorded `held at g` exit
    # read as `stale` — fingerprint staleness is NOT proof of an unrecorded
    # death (the predecessor exited on purpose and said so).
    r7 = mk_run(runs, "r7-held-amend", "hang a while")
    (r7 / "graph.json").write_text(json.dumps({"name": r7.name, "nodes": [
        {"id": "g", "type": "gate", "question": "proceed?", "options": ["yes"]}]}))
    out7 = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", r7.name],
                          env=dict(os.environ), capture_output=True, text=True, timeout=60)
    check("setup F: run parked at the gate with a recorded held exit",
          out7.stdout.startswith("WORKFLOW_HELD")
          and (r7 / "runner_exit.json").read_text().find("held at") >= 0,
          out7.stdout[:120])
    _real_spawn7 = door._spawn_runner
    door._spawn_runner = lambda rr: None   # freeze the scene; the bridge is under test
    try:
        before7 = len(ev_lines(r7))
        amended7 = {"name": r7.name, "nodes": [
            {"id": "g", "type": "gate", "question": "proceed?", "options": ["yes"]},
            {"id": "later", "type": "echo", "after": ["g"], "output": {"ok": True}}]}
        res7 = door.act_amend({"run_id": r7.name, "graph": amended7})
    finally:
        door._spawn_runner = _real_spawn7
    ev7 = ev_lines(r7)[before7:]
    check("held-amend (F2): a stale fingerprint over a clean held exit reaps nothing",
          isinstance(res7, dict) and "error" not in res7
          and not [e for e in ev7 if e.get("event") in ("runner.reaped", "node.interrupted")],
          json.dumps([e.get("event") for e in ev7])[:200])
    kill_tree(r7)

print(f"\nTOTAL {checks} FAIL {failures}")
sys.exit(1 if failures else 0)
