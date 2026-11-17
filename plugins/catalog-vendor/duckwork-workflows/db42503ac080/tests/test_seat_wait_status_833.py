"""est-2ek.1.833: status/next expose global-seat back-pressure.

Run 20261008-053450-ponytail-v5-estate-scope read runner_live=true with every node
`pending` through a 330s wait while events.jsonl held `node.started` then
`seat.wait cap=4` — status said nothing about WHY nothing progressed. The read
model now derives (derive-only, from events.jsonl + spawn-ledger.jsonl the runner
already writes) an open seat wait per spawning node: `nodes[id].seat_wait`
{since, age_s, cap, spawn, waiting} and the `next` wait row names
reason=seat_wait with the cap and the oldest wait age. No new queue, no new file.

Honest absence: a seat wait closed by a later child spawn (spawn-ledger child row),
a node terminal event, a stopped run, or a dead runner never shows.
"""
import fcntl, importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

HOME = Path(tempfile.mkdtemp(prefix="home-seat-wait-833-", dir=os.environ.get("TMPDIR")))
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("WF_RUNS_ROOT", None)
door = load("seat_wait_833_door", ROOT / "__init__.py")

ok = fail = 0
def check(cond, msg, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("PASS", msg)
    else:
        fail += 1; print("FAIL", msg, "—", detail)

LOCKS = []
def mk(rid, nodes, events, ledger=(), live=True):
    r = HOME / "workflows" / rid
    for d in ("nodes", "logs", "gates"):
        (r / d).mkdir(parents=True, exist_ok=True)
    (r / "graph.json").write_text(json.dumps({"name": rid, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": rid, "duckwork_bin": "/bin/true",
                                            "started": "2026-10-08T05:34:50+00:00"}))
    (r / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (r / "spawn-ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ledger))
    (r / "runner.lock").write_text("")
    if live:   # hold the runner's flock exactly as a live runner does (91b9a3de law)
        fd = os.open(str(r / "runner.lock"), os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        LOCKS.append(fd)
    return r

T0 = "2026-10-08T05:34:51+00:00"
RUNNER = {"ts": T0, "pid": 1, "role": "runner", "node": None, "index": None,
          "skey": None, "purpose": "workflow-runner"}
A = {"id": "node_a", "type": "agent", "goal": "probe node_a"}
B = {"id": "node_b", "type": "agent", "goal": "probe node_b"}

try:
    # ---- S1: the incident shape — node.started then seat.wait cap=4, nothing else
    ev = [{"ts": T0, "event": "run.started"},
          {"ts": T0, "event": "node.started", "node": "node_a", "skey": "wf:x:node_a:1"},
          {"ts": T0, "event": "steer.baked", "node": "node_a", "spawn_no": 0, "n_lines": 0},
          {"ts": T0, "event": "seat.wait", "node": "node_a", "index": None, "spawn": 0, "cap": 4}]
    mk("sw-incident", [A, B], ev, [RUNNER])
    st = wfcommon.run_state(HOME / "workflows" / "sw-incident")
    check(st["runner_live"] is True and st["status"] == "running", "S1 fixture reads live/running",
          f"{st['runner_live']} {st['status']}")
    sw = st["nodes"]["node_a"].get("seat_wait")
    check(isinstance(sw, dict), "S1 run_state: pending node carries seat_wait", repr(st["nodes"]["node_a"]))
    check(sw and sw.get("cap") == 4 and sw.get("since") == T0 and sw.get("spawn") == 0,
          "S1 seat_wait names cap=4, since, spawn", repr(sw))
    check(sw and isinstance(sw.get("age_s"), int) and sw["age_s"] > 0, "S1 seat_wait carries wait age_s", repr(sw))
    check("seat_wait" not in st["nodes"]["node_b"], "S1 a node that never waited gains no key")
    p = door.act_status({"run_id": "sw-incident"})
    check(p["nodes"]["node_a"].get("seat_wait") == sw, "S1 act_status passes seat_wait through",
          repr(p["nodes"]["node_a"]))
    nx = (p.get("next") or [{}])[0]
    check(nx.get("action") == "wait" and nx.get("reason") == "seat_wait",
          "S1 next wait row names reason=seat_wait", repr(p.get("next")))
    check(nx.get("cap") == 4 and nx.get("nodes") == ["node_a"] and isinstance(nx.get("age_s"), int),
          "S1 next row carries cap, waiting nodes and oldest age", repr(nx))

    # ---- S2: the wait closed by a child spawn (ledger child row) -> no seat_wait
    led = [RUNNER, {"ts": "2026-10-08T05:35:10+00:00", "pid": 9, "role": "child", "node": "node_a",
                    "index": None, "skey": "wf:x:node_a:1", "purpose": "workflow-runner"}]
    mk("sw-spawned", [A], ev, led)
    st = wfcommon.run_state(HOME / "workflows" / "sw-spawned")
    check("seat_wait" not in st["nodes"]["node_a"], "S2 a later child spawn closes the wait",
          repr(st["nodes"]["node_a"]))
    p = door.act_status({"run_id": "sw-spawned"})
    check(p.get("next") == [{"action": "wait"}], "S2 next stays the plain wait row", repr(p.get("next")))

    # ---- S3: retry attempt waits AGAIN after an earlier spawn -> open again
    ev3 = ev + [{"ts": "2026-10-08T05:40:00+00:00", "event": "seat.wait", "node": "node_a",
                 "index": None, "spawn": 1, "cap": 4}]
    mk("sw-rewait", [A], ev3, led)
    st = wfcommon.run_state(HOME / "workflows" / "sw-rewait")
    sw = st["nodes"]["node_a"].get("seat_wait")
    check(sw and sw.get("spawn") == 1 and sw.get("since") == "2026-10-08T05:40:00+00:00",
          "S3 a fresh wait after a spawn reopens with the newer since/spawn", repr(sw))

    # ---- S4: dead runner -> interrupted, no seat_wait (nobody is waiting)
    mk("sw-dead", [A], ev, [RUNNER], live=False)
    st = wfcommon.run_state(HOME / "workflows" / "sw-dead")
    check(st["status"] != "running" and "seat_wait" not in st["nodes"]["node_a"],
          "S4 no live runner -> no seat_wait", repr(st["nodes"]["node_a"]))

    # ---- S5: the incident's end — cancelled while waiting -> failed, no seat_wait
    ev5 = ev + [{"ts": "2026-10-08T05:44:01+00:00", "event": "node.failed", "node": "node_a", "ms": 0,
                 "error": "cancelled while waiting for an agent seat", "error_class": "cancelled"},
                {"ts": "2026-10-08T05:44:01+00:00", "event": "run.stopped"}]
    mk("sw-stopped", [A], ev5, [RUNNER])
    st = wfcommon.run_state(HOME / "workflows" / "sw-stopped")
    check("seat_wait" not in st["nodes"]["node_a"], "S5 terminal node event closes the wait",
          repr(st["nodes"]["node_a"]))

    # ---- S6: fan-out items waiting; wait buried under >20 later events still read
    F = {"id": "fan", "type": "agent", "goal": "item {{item}}", "fanout": {"items": [1, 2, 3]}}
    ev6 = [{"ts": T0, "event": "run.started"},
           {"ts": T0, "event": "node.started", "node": "fan", "skey": "wf:x:fan:1"},
           {"ts": T0, "event": "seat.wait", "node": "fan", "index": 0, "spawn": 0, "cap": 2},
           {"ts": "2026-10-08T05:35:00+00:00", "event": "seat.wait", "node": "fan", "index": 2, "spawn": 0, "cap": 2}]
    ev6 += [{"ts": "2026-10-08T05:35:01+00:00", "event": "gate.parked", "node": "other"}] * 30
    led6 = [RUNNER, {"ts": "2026-10-08T05:35:05+00:00", "pid": 9, "role": "child", "node": "fan",
                     "index": 1, "skey": "wf:x:fan:1", "purpose": "workflow-runner"}]
    mk("sw-fan", [F], ev6, led6)
    st = wfcommon.run_state(HOME / "workflows" / "sw-fan")
    sw = st["nodes"]["fan"].get("seat_wait")
    check(sw and sw.get("waiting") == [0, 2] and sw.get("since") == T0 and sw.get("cap") == 2,
          "S6 fan-out: waiting item indexes + oldest since, read past the last-20 window", repr(sw))
finally:
    for fd in LOCKS:
        try:
            os.close(fd)
        except OSError:
            pass
    shutil.rmtree(HOME, ignore_errors=True)

print(f"TOTAL {ok + fail} FAIL {fail}")
sys.exit(1 if fail else 0)
