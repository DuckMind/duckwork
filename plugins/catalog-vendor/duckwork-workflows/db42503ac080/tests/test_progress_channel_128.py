#!/usr/bin/env python3
"""#128 artifact-mtime progress channel: the write-first file is the heartbeat.

run_state's per-running-node block gains a query-time-derived `progress` =
{artifact, size, mtime_age_s, last_line} resolved from the most recently
modified regular file under the node's child work dir <run>/work/<node>[.<i>]/
(child_work_dir, wf.py — the dir WORK_DIR_NOTE already mandates). Pure read,
no writes, fail-safe: absent/unreadable artifact => the key is ABSENT, never
fabricated, and the read never raises. last_line is the last NEWLINE-TERMINATED
line — a trailing partial line is dropped, never torn. The door's act_status
node projection whitelists `progress` so status/wait/list expose it identically.

Hand-built run dir (pattern: tests/test_honest_status_jam_a3.py) + a live fake
child appending to a growing artifact; stdlib-only. The fake child identity is
injected through _active_spawns — the ONE verification law owns that concern
and is exercised by its own tests, not this read-model test.
"""
import fcntl
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import wfcommon

HOME = Path(tempfile.mkdtemp(prefix="home-prog128-", dir=str(ROOT)))
os.environ["DUCKWORK_HOME"] = str(HOME)

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg} — {detail}" if detail else msg
    ok += 1; print("PASS", msg)

SCHEMA = {"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}}
HELD_FDS = []  # keep the fake-runner flocks open for the whole process

def mk(rid, nodes):
    r = HOME / "workflows" / rid
    (r / "nodes").mkdir(parents=True)
    (r / "logs").mkdir()
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": rid, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": rid, "duckwork_bin": "/bin/true"}))
    (r / "events.jsonl").write_text("")  # a live run has an event log (keeps status out of the no-events 'pending' demotion)
    # 91b93de liveness law: HELD flock on <run>/runner.lock => live, unconditionally.
    fd = os.open(str(r / "runner.lock"), os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    HELD_FDS.append(fd)
    return r

class patch_active:
    """Inject the verified-child identity the ONE law would return; this test
    owns the artifact facts, not spawn verification. Covers BOTH wfcommon
    instances: the test's import and the door's private sibling bind."""
    def __init__(self, active, extra_mods=()):
        self.active = active
        self.mods = [wfcommon, *[m for m in extra_mods if m is not None]]
        self.orig = {}
    def __enter__(self):
        for m in self.mods:
            self.orig[id(m)] = (m, m._active_spawns)
            m._active_spawns = (lambda a: (lambda r, n, byid: [dict(x) for x in a]))(self.active)
    def __exit__(self, *exc):
        for m, fn in self.orig.values():
            m._active_spawns = fn
        return False

try:
    NODE = {"id": "lane", "type": "agent", "goal": "work", "schema": SCHEMA}
    SPAWN = {"pid": 999999, "started": "2026-10-07T00:00:00+00:00",
             "attempt": 0, "log_path": "logs/lane.a0.log", "skey": "wf:x:lane:nonce"}

    # ---- 1: no artifact visible => no `progress` key, run_state still returns ----
    r1 = mk("p128-empty", [NODE])
    with patch_active([SPAWN]):
        st1 = wfcommon.run_state(r1)
    check(st1["status"] == "running" and st1["nodes"]["lane"]["status"] == "running",
          "T1: bare run with active spawn reads running", json.dumps(st1["status"]))
    check("progress" not in st1["nodes"]["lane"],
          "T1: no artifact under work/ => progress key ABSENT (never fabricated)",
          json.dumps(st1["nodes"]["lane"]))

    # ---- 2: growing artifact, live fake child: size/mtime_age_s track growth ----
    r2 = mk("p128-grow", [NODE])
    wd = r2 / "work" / "lane"                      # child_work_dir naming
    wd.mkdir(parents=True)
    art = wd / "answer.md"
    art.write_text("line one\n")
    old = time.time() - 10.0                       # the artifact has been sitting ~10s
    os.utime(art, (old, old))
    child = os.fork()
    if child == 0:                                  # the live fake child appends
        try:
            time.sleep(1.2)
            with open(art, "a") as fh:
                fh.write("line two\nline three\n")
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            os._exit(0)
    try:
        with patch_active([SPAWN]):
            st2a = wfcommon.run_state(r2)
            p2a = st2a["nodes"]["lane"].get("progress") or {}
            deadline = time.time() + 8.0            # join the child's append, then poll
            while art.stat().st_size == len(b"line one\n") and time.time() < deadline:
                time.sleep(0.05)
            st2b = wfcommon.run_state(r2)           # second poll, after growth
            p2b = st2b["nodes"]["lane"].get("progress") or {}
    finally:
        os.waitpid(child, 0)
    check(p2a.get("artifact") == "work/lane/answer.md"
          and p2b.get("artifact") == "work/lane/answer.md",
          "T2: progress.artifact is the run-dir-relative path", str(p2a.get("artifact")))
    check(p2a.get("size") == len(b"line one\n"),
          "T2: first poll reports the committed size", str(p2a))
    check(p2b.get("size") == len(b"line one\nline two\nline three\n"),
          "T2: second poll sees the child's growth", str(p2b))
    check(p2b.get("size", 0) > p2a.get("size", 0),
          "T2: size tracks growth across the two polls", f"{p2a.get('size')}->{p2b.get('size')}")
    check(isinstance(p2a.get("mtime_age_s"), (int, float))
          and 9.0 <= p2a["mtime_age_s"] <= 60,
          "T2: first poll reports the aged artifact's mtime_age_s (~10s)", str(p2a.get("mtime_age_s")))
    check(isinstance(p2b.get("mtime_age_s"), (int, float)) and p2b["mtime_age_s"] < 5.0,
          "T2: mtime_age_s resets fresh when the child grows the artifact", str(p2b.get("mtime_age_s")))
    check(p2b.get("mtime_age_s", 1e9) < p2a.get("mtime_age_s", 0),
          "T2: mtime_age_s falls as the artifact grows", f"{p2a.get('mtime_age_s')}->{p2b.get('mtime_age_s')}")
    check(p2a.get("last_line") == "line one",
          "T2: last_line is the last newline-terminated line", str(p2a.get("last_line")))

    # ---- 3: tail-safety: a trailing PARTIAL line is dropped, last_line is whole ----
    r3 = mk("p128-torn", [NODE])
    wd3 = r3 / "work" / "lane"
    wd3.mkdir(parents=True)
    (wd3 / "answer.md").write_bytes(b"good line A\ngood line B\npar")  # cut mid-line
    with patch_active([SPAWN]):
        st3 = wfcommon.run_state(r3)
    p3 = st3["nodes"]["lane"].get("progress") or {}
    check(p3.get("last_line") == "good line B",
          "T3: file ending mid-line => previous COMPLETE line, never torn", str(p3.get("last_line")))
    check(p3.get("size") == len(b"good line A\ngood line B\npar"),
          "T3: size counts the raw bytes including the partial tail", str(p3.get("size")))

    # ---- 4: unreadable artifact => no key, no raise, run_state still returns ----
    r4 = mk("p128-unreadable", [NODE])
    wd4 = r4 / "work" / "lane"
    wd4.mkdir(parents=True)
    (wd4 / "answer.md").write_text("secret\n")
    os.chmod(wd4 / "answer.md", 0)
    try:
        with patch_active([SPAWN]):
            st4 = wfcommon.run_state(r4)
        check(st4["status"] == "running" and "progress" not in st4["nodes"]["lane"],
              "T4: unreadable artifact => progress absent, run_state never raises",
              json.dumps(st4["nodes"]["lane"]))
    finally:
        os.chmod(wd4 / "answer.md", 0o644)

    # ---- 5: the door's act_status node projection carries progress identically ----
    spec = importlib.util.spec_from_file_location("wf_door_128", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    import wf_test_isolation as _iso128; _iso128.install(door)  # #71 r5: pin settings.runs_root
    os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
    with patch_active([SPAWN], extra_mods=[door._common]):
        st5 = wfcommon.run_state(r2)                # pin the same facts the door reads
        status = door.act_status({"run_id": "p128-grow"})
    check(st5["nodes"]["lane"].get("progress", {}).get("artifact") == "work/lane/answer.md",
          "T5: (control) run_state still publishes progress", json.dumps(st5["nodes"]["lane"]))
    dp = status["nodes"]["lane"].get("progress") or {}
    rp = st5["nodes"]["lane"].get("progress") or {}
    # mtime_age_s is query-time ("now - mtime"), so the two polls cannot be
    # byte-equal on it; the identity the door must preserve is the fact set.
    check({k: dp.get(k) for k in ("artifact", "size", "last_line")}
          == {k: rp.get(k) for k in ("artifact", "size", "last_line")}
          and isinstance(dp.get("mtime_age_s"), (int, float)) and dp["mtime_age_s"] >= 0
          and set(dp) == {"artifact", "size", "mtime_age_s", "last_line"},
          "T5: door act_status node projection exposes progress IDENTICALLY",
          json.dumps(status["nodes"]["lane"]))
    check("active_spawn" in status["nodes"]["lane"],
          "T5: progress rides alongside the existing active_spawn projection",
          json.dumps(sorted(status["nodes"]["lane"])))

    print(f"RESULT {'GREEN' if ok else 'RED'} ({ok} checks)")
    sys.exit(0 if ok else 1)
except AssertionError as e:
    print(f"RED: {e}")
    sys.exit(1)
finally:
    import shutil
    for _fd in HELD_FDS:
        try:
            os.close(_fd)
        except OSError:
            pass
    shutil.rmtree(HOME, ignore_errors=True)
