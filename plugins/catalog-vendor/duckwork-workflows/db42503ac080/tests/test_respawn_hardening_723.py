#!/usr/bin/env python3
"""PR #237 respawn-hardening blockers (zap review comment 6017431132).

Four gates the respawner must pass — each is the isolated failure-path control
zap ran through the real door:

  F1 (door-error-no-receipt): an unknown-run / door-error revive writes NO
     runner_respawn receipt and NO guard, so a later attempt may re-spawn;
     success is recorded ONLY on confirmed spawn (lock held or /proc pid
     identity — never receipt trust).
  F2 (partial fan-out): a single efp-valid `done` fan-out ITEM must not mask
     the missing aggregate commit — the aggregate (merged) node record is the
     commit; its absence is unfinished work.
  F3 (stale-efp done): a committed done whose efp no longer matches the graph
     (amended node) is pending, not finished — reuse the ONE validity rule.
  F4 (concurrent admits): two callers on the same scene produce exactly ONE
     spawn (serialized admission, not check-then-spawn).

  F5 (production revive): the door's act_wait return is propagated (error ->
     no receipt), and liveness confirmation reads the runner lock / /proc.

Injectable `spawn` contract: a truthy return means the spawn is CONFIRMED, a
falsy return means nothing spawned (no receipt, no guard, retries stay open).
The production revive path is tested by monkeypatching the module's _load_door
seam (the door import).

Plain script, no pytest: exits non-zero on the first red.
"""
import importlib.util
import json
import os
import sys
import threading
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import wfcommon as wc  # noqa: E402  (repo root IS the plugin dir; lane_recover mirrors it)


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


def mk_run(runs, run_id, fanout_items=None):
    r = runs / run_id
    r.mkdir(parents=True)
    (r / "nodes").mkdir()
    (r / "gates").mkdir()
    node = {"id": "build", "type": "agent", "goal": "ship it"}
    if fanout_items is not None:
        node["fanout"] = {"items": [{"goal": g} for g in fanout_items]}
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": "python3", "concurrency": 1}))
    return r


def current_efp(r, node_id):
    graph = json.loads((r / "graph.json").read_text())
    n = next(x for x in graph["nodes"] if x.get("id") == node_id)
    return wc.efp({n["id"]: n}, n)


def stamp(r, name, rec, node_id="build"):
    """Write a node record stamped with the CURRENT efp (an honest commit)."""
    rec = dict(rec)
    rec["efp"] = current_efp(r, node_id)
    rec["fp_rule_version"] = wc.FP_RULE_VERSION
    (r / "nodes" / f"{name}.json").write_text(json.dumps(rec))


def claim_running(r, node, pid, index=None):
    rec = {"status": "running", "pid": pid,
           "skey": f"wf:{r.name}:{node}:deadbeef.000001", "attempt": 1}
    name = node + (f".{index}" if index is not None else "")
    (r / "nodes" / f"{name}.json").write_text(json.dumps(rec))


def ev_lines(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def respawn_events(r):
    return [e for e in ev_lines(r) if e.get("event") == "runner_respawn"]


def main():
    lr = load("lane_recover_723", ROOT / "scripts" / "lane_recover.py")
    sig = getattr(lr, "crashed_no_exit_signature", None)
    recover = getattr(lr, "recover_crashed_runner", None)
    check("watchdog: crashed_no_exit_signature + recover_crashed_runner exposed",
          callable(sig) and callable(recover), "attribute missing")
    if not (callable(sig) and callable(recover)):
        print(f"FAILED: {FAILS}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="rh723-") as td:
        runs = Path(td) / "workflows"
        runs.mkdir()

        # ---- F1 door-error: unconfirmed spawn -> no receipt, no guard, retry live.
        r = mk_run(runs, "rh723-doorerr")
        claim_running(r, "build", DEAD_PID + 1)
        (r / "wf.pid").write_text(str(DEAD_PID))
        check("F1: crashed-no-exit scene matches the signature", bool(sig(r)), sig(r))
        calls = []

        def failing_spawn(rd):
            calls.append(rd)
            return None                      # the door answered with an error / nothing spawned

        res1 = recover(r, spawn=failing_spawn)
        check("F1: door-error call reports NOT respawned",
              isinstance(res1, dict) and not res1.get("respawned"), res1)
        check("F1: door-error writes NO runner_respawn receipt",
              not respawn_events(r), respawn_events(r))
        guard = r / "respawn_guard.json"
        check("F1: door-error writes NO guard",
              not guard.exists(), guard.read_text()[:200] if guard.exists() else None)
        # the whole point: a LATER attempt must still be able to spawn
        res2 = recover(r, spawn=lambda rd: "spawned")
        check("F1: after a failed revive, a later attempt DOES re-spawn",
              len(calls) == 1 and isinstance(res2, dict) and res2.get("respawned"),
              (calls, res2))
        check("F1: confirmed spawn appends exactly one receipt + guard",
              len(respawn_events(r)) == 1 and guard.exists(), respawn_events(r))

        # ---- F2 partial fan-out: one done item must not mask the missing aggregate.
        r2 = mk_run(runs, "rh723-fanout", fanout_items=["a", "b", "c"])
        (r2 / "wf.pid").write_text(str(DEAD_PID))
        stamp(r2, "build.0", {"status": "done", "output": {"result": "a done"}})
        check("F2: one done item + missing aggregate = unfinished (signature true)",
              bool(sig(r2)), sig(r2))
        stamp(r2, "build", {"status": "done",
                            "output": {"items": [{"result": "a done"}], "failed_items": 0}})
        check("F2: aggregate commit present = finished (signature false)",
              not sig(r2), sig(r2))
        # every item record missing but aggregate committed: still finished
        r2b = mk_run(runs, "rh723-fanout2", fanout_items=["a", "b", "c"])
        (r2b / "wf.pid").write_text(str(DEAD_PID))
        stamp(r2b, "build", {"status": "done", "output": {"items": []}})
        check("F2: aggregate alone is the commit (no item records needed)",
              not sig(r2b), sig(r2b))

        # ---- F3 stale-efp done: an amended node must read pending, not finished.
        r3 = mk_run(runs, "rh723-stale")
        (r3 / "wf.pid").write_text(str(DEAD_PID))
        stamp(r3, "build", {"status": "done", "output": {"result": "shipped"}})
        check("F3: efp-valid done commit = finished (signature false)",
              not sig(r3), sig(r3))
        # amend the node (changes its efp): the committed record is now stale.
        graph = json.loads((r3 / "graph.json").read_text())
        graph["nodes"][0]["goal"] = "ship it AGAIN (amended)"
        (r3 / "graph.json").write_text(json.dumps(graph))
        check("F3: stale-efp done hides pending work — signature must be true",
              bool(sig(r3)), sig(r3))

        # ---- F4 concurrent admits: two callers, exactly one spawn.
        r4 = mk_run(runs, "rh723-race")
        claim_running(r4, "build", DEAD_PID + 1)
        (r4 / "wf.pid").write_text(str(DEAD_PID))
        spawns4 = []
        spawns_lock = threading.Lock()

        def slow_spawn(rd):
            # hold the spawn window wide so a check-then-spawn race window is real
            with spawns_lock:
                spawns4.append(rd)
            import time
            time.sleep(0.4)
            return "spawned"                     # truthy = confirmed spawn

        threads = [threading.Thread(target=lambda: recover(r4, spawn=slow_spawn))
                   for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        check("F4: two concurrent admits produce EXACTLY ONE spawn",
              len(spawns4) == 1, spawns4)
        check("F4: exactly one runner_respawn receipt",
              len(respawn_events(r4)) == 1, respawn_events(r4))

        # ---- F5 production revive: door error propagates; lock-held = confirmed.
        r5 = mk_run(runs, "rh723-prod")
        claim_running(r5, "build", DEAD_PID + 1)
        (r5 / "wf.pid").write_text(str(DEAD_PID))
        fake = types.SimpleNamespace(act_wait=lambda a: {"error": "unknown run_id"})
        lr._load_door = lambda plugin: fake
        # CI runs under an empty DUCKWORK_HOME (scripts/suite.py): pin the plugin
        # dir to this checkout; live-plugin resolution is covered by
        # tests/test_plugin_resolution_live_not_old.py.
        lr.resolve_plugin_dir = lambda plugins_root=None: ROOT
        res5 = recover(r5)                                 # production path, failing door
        check("F5: door error -> not respawned, no receipt, no guard",
              isinstance(res5, dict) and not res5.get("respawned")
              and not respawn_events(r5) and not (r5 / "respawn_guard.json").exists(),
              res5)
        # confirmed revive: the fake door "spawns" by taking runner.lock inside
        # act_wait, exactly as a live runner does — the ONE liveness law then
        # reads HELD => live at confirmation time (the scene was dead before
        # the door call, so the signature still fires).
        import fcntl
        holder = {}

        def ok_spawn_and_wait(a):
            fd = os.open(str(r5 / "runner.lock"), os.O_RDWR | os.O_CREAT)
            fcntl.flock(fd, fcntl.LOCK_EX)
            holder["fd"] = fd
            return {"status": "running", "runner_live": True}

        try:
            fake_ok = types.SimpleNamespace(act_wait=ok_spawn_and_wait)
            lr._load_door = lambda plugin: fake_ok
            res6 = recover(r5)
            check("F5: door success + live runner -> respawned, receipt + guard",
                  isinstance(res6, dict) and res6.get("respawned")
                  and len(respawn_events(r5)) == 1
                  and (r5 / "respawn_guard.json").exists(),
                  (res6, respawn_events(r5)))
        finally:
            if holder.get("fd") is not None:
                fcntl.flock(holder["fd"], fcntl.LOCK_UN)
                os.close(holder["fd"])

    print(("ALL PASS" if not FAILS else f"FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
