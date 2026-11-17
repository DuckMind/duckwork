#!/usr/bin/env python3
"""#133 wall meter: run_state/status publish per-running-node wall seconds.
(duckwork-workflows#133 — elapsed-vs-wall-and-p95 on every running node.)

run_state's per-running-node block gains `wall` = {elapsed_s, wall_s, p95_s,
meter}: pure arithmetic over facts the runner already committed — the verified
active-spawn `started`, the BAKED def `timeout`, and the ONE node.extended bump
(extra_s, from events.jsonl). p95_s = SHAPE_PRESETS[shape]/timeout (the table
IS the measured p95 per shape). One word: over-p95 (beyond the wall or beyond
the shape p95) / near-wall (>80% of either bound) / on-track. Honest absence
(#128/R2 law): no parseable `started`, or no bound at all => key ABSENT, never
a fabricated number; a dead runner shows no meter (nobody is running).
The door's act_status node projection whitelists `wall` so status/wait expose
it identically, alongside `progress`.

Hand-built run dirs (pattern: tests/test_progress_channel_128.py); the fake
child identity is injected through _active_spawns — the ONE verification law
owns that concern and is exercised by its own tests, not this read-model test.
Stdlib-only.
"""
import fcntl
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import wfcommon

HOME = Path(tempfile.mkdtemp(prefix="home-wall133-", dir=os.environ.get("TMPDIR")))
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("WF_RUNS_ROOT", None)

ok = fail = 0
def check(cond, msg, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("PASS", msg)
    else:
        fail += 1; print("FAIL", msg, "—", detail)

HELD_FDS = []  # keep the fake-runner flocks open for the whole process

def iso(seconds_ago):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()

def mk(rid, nodes, events=(), live=True):
    r = HOME / "workflows" / rid
    for d in ("nodes", "logs", "gates"):
        (r / d).mkdir(parents=True, exist_ok=True)
    (r / "graph.json").write_text(json.dumps({"name": rid, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": rid, "duckwork_bin": "/bin/true"}))
    (r / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    fd = os.open(str(r / "runner.lock"), os.O_RDWR | os.O_CREAT)
    if live:   # 91b9a3de liveness law: HELD flock => live, unconditionally
        fcntl.flock(fd, fcntl.LOCK_EX)
    HELD_FDS.append(fd)
    return r

class patch_active:
    """Inject the verified-child identity the ONE law would return; this test
    owns the clock facts, not spawn verification. Covers BOTH wfcommon
    instances: the test's import and the door's private sibling bind."""
    def __init__(self, active, extra_mods=()):
        self.active = active
        self.mods = [wfcommon, *[m for m in extra_mods if m is not None]]
        self.orig = {}
    def __enter__(self):
        for m in self.mods:
            self.orig[id(m)] = (m, m._active_spawns)
            m._active_spawns = (lambda a: (lambda r, n, byid: [dict(x) for x in a]))(self.active)
        return self
    def __exit__(self, *exc):
        for m, fn in self.orig.values():
            m._active_spawns = fn
        return False

def spawn(started_iso):
    return {"pid": 999999, "started": started_iso, "attempt": 0,
            "log_path": "logs/lane.a0.log", "skey": "wf:x:lane:133"}

def NODE(**kw):
    return {"id": "lane", "type": "agent", "goal": "work", **kw}

try:
    # ---- T1 on-track: 100 s into a 900 s wall (build p95 = 1500) ----
    r1 = mk("w133-ont", [NODE(timeout=900, max_turns=65)],
            [{"ts": iso(101), "event": "run.started"}])
    with patch_active([spawn(iso(100))]):
        st1 = wfcommon.run_state(r1)
    lane1 = st1["nodes"]["lane"]
    w = lane1.get("wall")
    check(st1["status"] == "running" and lane1["status"] == "running",
          "T1 fixture reads live/running", json.dumps([st1["status"], lane1["status"]]))
    check(isinstance(w, dict), "T1 running node carries wall meter", json.dumps(lane1))
    check(w and set(w) == {"elapsed_s", "wall_s", "p95_s", "meter"},
          "T1 wall key is the closed fact set", json.dumps(w))
    check(w and 99 <= w["elapsed_s"] <= 105, "T1 elapsed_s tracks the spawn's started",
          str(w and w["elapsed_s"]))
    check(w and w["wall_s"] == 900 and w["p95_s"] == 1500,
          "T1 wall_s = baked def timeout; p95_s = build-shape measured p95", json.dumps(w))
    check(w and w["meter"] == "on-track", "T1 ~11% of the wall reads on-track",
          str(w and w["meter"]))

    # ---- T1b: not running => no key ----
    with patch_active([]):
        st1b = wfcommon.run_state(r1)
    check(st1b["nodes"]["lane"]["status"] == "pending"
          and "wall" not in st1b["nodes"]["lane"],
          "T1b: a non-running node gains no wall key", json.dumps(st1b["nodes"]["lane"]))

    # ---- T2 near-wall: 800 s into a 900 s wall (89%), still under the p95 ----
    r2 = mk("w133-near", [NODE(timeout=900)], [{"ts": iso(801), "event": "run.started"}])
    with patch_active([spawn(iso(800))]):
        st2 = wfcommon.run_state(r2)
    w2 = st2["nodes"]["lane"].get("wall") or {}
    check(w2.get("meter") == "near-wall" and w2.get("wall_s") == 900,
          "T2 >80% of the wall reads near-wall", json.dumps(w2))

    # ---- T2b over-p95 via the shape p95: wall 3600, but 2000 s > build p95 1500 ----
    r3 = mk("w133-p95", [NODE(timeout=3600, shape="build")],
            [{"ts": iso(2001), "event": "run.started"}])
    with patch_active([spawn(iso(2000))]):
        st3 = wfcommon.run_state(r3)
    w3 = st3["nodes"]["lane"].get("wall") or {}
    check(w3.get("meter") == "over-p95" and w3.get("wall_s") == 3600
          and w3.get("p95_s") == 1500,
          "T2b beyond the measured p95 (inside the wall) reads over-p95", json.dumps(w3))

    # ---- T3 the ONE node.extended bump folds into wall_s ----
    r4 = mk("w133-ext", [NODE(timeout=60)],
            [{"ts": iso(79), "event": "run.started"},
             {"ts": iso(70), "event": "node.extended", "node": "lane", "extra_s": 30}])
    with patch_active([spawn(iso(78))]):
        st4 = wfcommon.run_state(r4)
    w4 = st4["nodes"]["lane"].get("wall") or {}
    check(w4.get("wall_s") == 90 and w4.get("meter") == "near-wall",
          "T3 one 50% bump folds into wall_s (60+30) and 78/90 reads near-wall",
          json.dumps(w4))

    # ---- T3b past the (extended) wall => over-p95 ----
    r5 = mk("w133-over", [NODE(timeout=60)],
            [{"ts": iso(96), "event": "run.started"},
             {"ts": iso(90), "event": "node.extended", "node": "lane", "extra_s": 30}])
    with patch_active([spawn(iso(95))]):
        st5 = wfcommon.run_state(r5)
    w5 = st5["nodes"]["lane"].get("wall") or {}
    check(w5.get("wall_s") == 90 and w5.get("meter") == "over-p95",
          "T3b elapsed beyond the extended wall reads over-p95", json.dumps(w5))

    # ---- T4 an extension from BEFORE this spawn never counts ----
    r6 = mk("w133-old-ext", [NODE(timeout=60)],
            [{"ts": iso(500), "event": "node.extended", "node": "lane", "extra_s": 30},
             {"ts": iso(79), "event": "run.started"}])
    with patch_active([spawn(iso(78))]):
        st6 = wfcommon.run_state(r6)
    w6 = st6["nodes"]["lane"].get("wall") or {}
    check(w6.get("wall_s") == 60 and w6.get("meter") == "over-p95",
          "T4 a pre-spawn extension is not carried into this spawn's wall", json.dumps(w6))

    # ---- T5 honest absence: unparseable started => key ABSENT, never raises ----
    r7 = mk("w133-junk", [NODE(timeout=900)], [{"ts": iso(1), "event": "run.started"}])
    with patch_active([spawn("not-a-date")]):
        st7 = wfcommon.run_state(r7)
    check(st7["status"] == "running" and "wall" not in st7["nodes"]["lane"],
          "T5 unparseable started => wall ABSENT, run_state never raises",
          json.dumps(st7["nodes"]["lane"]))

    # ---- T6 dead runner => nobody is running, no meter ----
    r8 = mk("w133-dead", [NODE(timeout=900)],
            [{"ts": iso(1), "event": "run.started"}], live=False)
    with patch_active([spawn(iso(100))]):
        st8 = wfcommon.run_state(r8)
    check("wall" not in st8["nodes"]["lane"],
          "T6 dead runner shows no wall meter", json.dumps(st8["nodes"]["lane"]))

    # ---- T7 fan-out: the OLDEST active spawn drives the node meter ----
    r9 = mk("w133-fan", [NODE(timeout=900, fanout={"items": ["a", "b"]})],
            [{"ts": iso(101), "event": "run.started"}])
    with patch_active([spawn(iso(10)), spawn(iso(100))]):
        st9 = wfcommon.run_state(r9)
    w9 = st9["nodes"]["lane"].get("wall") or {}
    check(99 <= w9.get("elapsed_s", -1) <= 105 and w9.get("meter") == "on-track",
          "T7 the senior fan-out item sets the node meter", json.dumps(w9))

    # ---- T8 the door's act_status projection carries wall identically ----
    spec = importlib.util.spec_from_file_location("wf_door_133", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    import wf_test_isolation as _iso133
    _iso133.install(door)  # #71 r5: pin settings.runs_root
    os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
    with patch_active([spawn(iso(800))], extra_mods=[door._common]):
        st8c = wfcommon.run_state(r2)              # pin the same facts the door reads
        status = door.act_status({"run_id": "w133-near"})
    rw = st8c["nodes"]["lane"].get("wall") or {}
    dw = status["nodes"]["lane"].get("wall")
    check(rw.get("meter") == "near-wall",
          "T8 (control) run_state still publishes wall", json.dumps(st8c["nodes"]["lane"]))
    check(dw and dw["meter"] == rw["meter"] and dw["wall_s"] == rw["wall_s"]
          and dw["p95_s"] == rw["p95_s"]
          and isinstance(dw.get("elapsed_s"), int) and dw["elapsed_s"] >= 0,
          "T8 door act_status node projection exposes wall IDENTICALLY",
          json.dumps(status["nodes"]["lane"]))
    check("active_spawn" in status["nodes"]["lane"],
          "T8 wall rides alongside the existing active_spawn projection",
          json.dumps(sorted(status["nodes"]["lane"])))

    print(f"RESULT {'GREEN' if fail == 0 else 'RED'} ({ok} checks, {fail} failed)")
    sys.exit(0 if fail == 0 else 1)
finally:
    for _fd in HELD_FDS:
        try:
            os.close(_fd)
        except OSError:
            pass
    shutil.rmtree(HOME, ignore_errors=True)
