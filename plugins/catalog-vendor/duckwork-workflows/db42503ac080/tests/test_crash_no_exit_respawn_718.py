#!/usr/bin/env python3
"""est-2ek.1.718: a crashed runner (dead pid, NO runner_exit.json) with pending/
running items must be respawned by the watchdog WITHOUT waiting for an owner
wait call — exactly once per crash signature.

The incident: the runner crashed mid-fanout; the run sat `interrupted` with
runner_live=false for 20+ minutes until a manual wait respawned it. The
crashed-no-exit signature (dead pid + absent runner_exit.json + unfinished
nodes) is unambiguous, so the watchdog (scripts/lane_recover.py) respawns on
sight, guarded by a fingerprint file so one crash can never fan out into a
respawn storm, and appends one `runner_respawn` event as the receipt.

Law pinned here:
  * signature = runner pid dead (flock NOT held) + runner_exit.json absent
    + at least one node whose record claims running (or the graph has
    unfinished nodes); a VALID recorded exit is a verdict — never respawned;
  * first recover call on the signature attempts exactly one respawn and
    appends one runner_respawn event (with the dead prev pid + fingerprint);
  * the guard file carries the run fingerprint: while the fingerprint is
    unchanged, EVERY later call no-ops (no second spawn, no second event);
  * a live runner (held flock) never matches the signature.

Plain script, no pytest: exits non-zero on the first red.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:600]))
    if not cond:
        FAILS.append(name)


DEAD_PID = 999_998 if sys.maxsize > 2**16 else 32_766  # unallocated pid probe


def mk_run(runs, run_id, fanout=False):
    r = runs / run_id
    r.mkdir(parents=True)
    (r / "nodes").mkdir()
    (r / "gates").mkdir()
    nodes = [{"id": "build", "type": "agent", "goal": "ship it"}]
    if fanout:
        nodes = [{"id": "build", "type": "agent", "goal": "ship it",
                  "fanout": {"items": ["a", "b", "c"]}}]
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": "python3", "concurrency": 1}))
    return r


def claim_running(r, node, pid, efp=None, index=None):
    """A node record mid-crash: status=running with a pid the sweep took."""
    rec = {"status": "running", "pid": pid,
           "skey": f"wf:{r.name}:{node}:deadbeef.000001", "attempt": 1}
    name = node + (f".{index}" if index is not None else "")
    (r / "nodes" / f"{name}.json").write_text(json.dumps(rec))


def ev_lines(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def main():
    lr = load("lane_recover_718", ROOT / "scripts" / "lane_recover.py")
    sig = getattr(lr, "crashed_no_exit_signature", None)
    recover = getattr(lr, "recover_crashed_runner", None)
    check("watchdog: scripts/lane_recover.py exposes crashed_no_exit_signature",
          callable(sig), "attribute missing")
    check("watchdog: scripts/lane_recover.py exposes recover_crashed_runner",
          callable(recover), "attribute missing")
    if not (callable(sig) and callable(recover)):
        print(f"FAILED: {FAILS}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="cr718-") as td:
        runs = Path(td) / "workflows"
        runs.mkdir()

        # A. the incident shape: dead pid + no exit record + running claim.
        r = mk_run(runs, "r718-crash")
        claim_running(r, "build", DEAD_PID + 1)
        (r / "wf.pid").write_text(str(DEAD_PID))
        (r / "events.jsonl").write_text(
            json.dumps({"ts": "2026-10-06T07:00:00+00:00", "event": "node.started",
                        "node": "build"}) + "\n")
        check("A: signature observed on the crashed-no-exit scene",
              bool(sig(r)), "sig returned falsy")
        spawns = []
        res1 = recover(r, spawn=lambda rd: spawns.append(rd) or DEAD_PID + 42)
        check("A: first call attempts exactly one respawn",
              len(spawns) == 1, spawns)
        check("A: the result reports the respawn with the dead prev pid",
              isinstance(res1, dict) and res1.get("respawned")
              and res1.get("prev_pid") == DEAD_PID, res1)
        ev = ev_lines(r)
        respawns = [e for e in ev if e.get("event") == "runner_respawn"]
        check("A: exactly one runner_respawn event appended",
              len(respawns) == 1, [e.get("event") for e in ev])
        check("A: the receipt carries the run fingerprint",
              bool(respawns) and isinstance(respawns[0].get("fp"), str)
              and len(respawns[0]["fp"]) >= 8, respawns)
        guard = r / "respawn_guard.json"
        check("A: guard file written with the fingerprint",
              guard.exists() and json.loads(guard.read_text()).get("fp"),
              guard.read_text()[:200] if guard.exists() else "missing")

        # A2. second invocation, same frozen scene: no-ops via the guard.
        res2 = recover(r, spawn=lambda rd: spawns.append(rd) or 1)
        check("A2: second call on the same signature spawns NOTHING new",
              len(spawns) == 1, spawns)
        check("A2: second call reports the guard no-op",
              isinstance(res2, dict) and not res2.get("respawned")
              and "guard" in str(res2.get("reason", "")), res2)
        check("A2: no second runner_respawn event",
              len([e for e in ev_lines(r) if e.get("event") == "runner_respawn"]) == 1,
              ev_lines(r))

        # B. a VALID recorded exit is a verdict — never a crash, never respawned.
        r2 = mk_run(runs, "r718-held")
        claim_running(r2, "build", DEAD_PID + 1)
        (r2 / "wf.pid").write_text(str(DEAD_PID))
        from datetime import datetime, timezone
        # a well-formed exit record with reason=terminated (any reason) — the
        # crashed-no-exit probe must see the verdict, not the silence.
        (r2 / "runner_exit.json").write_text(json.dumps(
            {"reason": "terminated: SIGTERM",
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
        spawns2 = []
        check("B: valid recorded exit -> no signature", not sig(r2), sig(r2))
        res_b = recover(r2, spawn=lambda rd: spawns2.append(rd) or 1)
        check("B: verdict scene respawns nothing",
              not spawns2 and isinstance(res_b, dict) and not res_b.get("respawned"),
              (spawns2, res_b))

        # C. no unfinished claim -> nothing to revive (terminal / fresh dir).
        r3 = mk_run(runs, "r718-done")
        (r3 / "nodes" / "build.json").write_text(json.dumps(
            {"status": "done", "pid": DEAD_PID + 1, "skey": "wf:r718-done:build:x.y"}))
        (r3 / "wf.pid").write_text(str(DEAD_PID))
        check("C: committed-done nodes never match the signature",
              not sig(r3), sig(r3))

        # D. fresh run (no pid file) is not a crash.
        r4 = mk_run(runs, "r718-fresh")
        check("D: no wf.pid = fresh run, not a crash", not sig(r4), sig(r4))

        # E. live runner holding the flock is alive regardless of the pid file.
        import fcntl
        r5 = mk_run(runs, "r718-live")
        claim_running(r5, "build", DEAD_PID + 1)
        (r5 / "wf.pid").write_text(str(DEAD_PID))
        hold = os.open(str(r5 / "runner.lock"), os.O_RDWR | os.O_CREAT)
        fcntl.flock(hold, fcntl.LOCK_EX)
        try:
            check("E: held flock = live runner -> no signature", not sig(r5), sig(r5))
        finally:
            fcntl.flock(hold, fcntl.LOCK_UN)
            os.close(hold)

    print(("ALL PASS" if not FAILS else f"FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
