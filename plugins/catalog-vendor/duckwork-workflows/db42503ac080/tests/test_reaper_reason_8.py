#!/usr/bin/env python3
"""#8 (P0, remaining half): the silent-death reaper's `runner.reaped` event must
carry the OBSERVED gw-restart-window reason when the death window matches a
gateway restart.

The incident shape (issue #8): the gateway is SIGTERMed for a restart; the
enclosing unit sweep takes the runner (and its children) down with it. No exit
record exists, so the reaper says `crashed (no exit record)` — and the operator
has to correlate the death against the gateway log by hand. The fix law: the
reaper does that correlation itself, from FILES ONLY — a `Received SIGTERM`
line in <duckwork_home>/logs/gateway.log whose stamp falls within +/-120 s of the
death anchor (the last event ts in events.jsonl, else the wf.pid mtime) upgrades
the reason to `crashed (no exit record); gw-restart window match`.

Never-fatal law: an absent or unreadable gateway log keeps today's bare reason,
byte-identical, and the reap still happens — visibility is diagnostics, never a
reason to skip the resume.

RED on origin/main: the match branch does not exist — S1 fails with the bare
reason. S2/S3/S4 are the no-regression pins (byte-identical bare reason).
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iso(dt):
    return dt.isoformat(timespec="seconds")


def run_frozen_case(runs, run_id, anchor_dt):
    """A frozen dead-runner scene written by hand (no live process to race):
    dead pid, no exit record, one anchored event line, a falsely-claimed node."""
    r = runs / run_id
    if r.exists():
        shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [
        {"id": "work", "type": "agent", "goal": "hang a while"}]}))
    (r / "run.json").write_text(json.dumps({"concurrency": 1, "node_timeout": 60}))
    (r / "wf.pid").write_text("999998")          # never exists -> dead pid
    (r / "events.jsonl").write_text(json.dumps(
        {"ts": iso(anchor_dt), "event": "run.started"}) + "\n")
    frozen = {"status": "running", "pid": 999999,
              "skey": f"wf:{run_id}:work:deadbeef.000001",
              "attempt": 1, "started": iso(anchor_dt)}
    (r / "nodes" / "work.json").write_text(json.dumps(frozen))
    return r


def reaped_reason(door, r):
    door._reap_silent_death(r)
    evs = [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()
           if l.strip()]
    reaped = [e for e in evs if e.get("event") == "runner.reaped"]
    return (reaped[0]["reason"] if len(reaped) == 1 else
            f"__expected_exactly_one_runner_reaped_got_{len(reaped)}__")


with tempfile.TemporaryDirectory(prefix="reaperreason8-", dir=HERE,
                                 ignore_cleanup_errors=True) as td:
    home = Path(td) / "home"
    runs = home / "workflows"
    runs.mkdir(parents=True)
    gw_dir = home / "logs"
    gw_dir.mkdir(parents=True)
    gw_log = gw_dir / "gateway.log"
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["WF_RUNS_ROOT"] = str(runs)  # #71 r5 env pin
    wfcommon = load("reason8_wfcommon", ROOT / "wfcommon.py")
    door = load("reason8_door", ROOT / "__init__.py")
    import wf_test_isolation as _iso71_reason8
    _iso71_reason8.install(door)             # #71 r5: pin settings.runs_root too

    BARE = "crashed (no exit record)"
    now_dt = datetime.now(timezone.utc)

    # ---- S1: SIGTERM inside the death window -> reason carries the match ----
    anchor = now_dt - timedelta(seconds=40)
    gw_log.write_text(
        "[2026-01-01 00:00:00] boot chatter\n"
        f"[{iso(anchor + timedelta(seconds=10))}] Received SIGTERM, shutting down\n")
    r1 = run_frozen_case(runs, "r8-gwmatch", anchor)
    reason1 = reaped_reason(door, r1)
    check("S1: gw-restart window match rides the runner.reaped reason",
          reason1 == BARE + "; gw-restart window match", reason1)

    # ---- S2a: SIGTERM far outside the window -> byte-identical bare reason ----
    gw_log.write_text(
        f"[{iso(anchor - timedelta(seconds=600))}] Received SIGTERM, shutting down\n")
    r2 = run_frozen_case(runs, "r8-gwfar", anchor)
    reason2 = reaped_reason(door, r2)
    check("S2a: an out-of-window SIGTERM keeps today's bare reason byte-identical",
          reason2 == BARE, reason2)

    # ---- S2b: a gateway log with no SIGTERM line at all -> bare reason ----
    gw_log.write_text("[2026-01-01 00:00:00] INFO heartbeat tick\n")
    r2b = run_frozen_case(runs, "r8-gwnosig", anchor)
    reason2b = reaped_reason(door, r2b)
    check("S2b: a SIGTERM-free gateway log keeps today's bare reason byte-identical",
          reason2b == BARE, reason2b)

    # ---- S3: gateway log unreadable -> bare reason, no crash ----
    gw_log.unlink()
    gw_log.mkdir()  # a directory where the file must be: every read raises
    r3 = run_frozen_case(runs, "r8-gwunreadable", anchor)
    crashed = None
    try:
        reason3 = reaped_reason(door, r3)
    except Exception as exc:  # never-fatal law
        crashed, reason3 = exc, "__raised__"
    check("S3: an unreadable gateway.log never crashes the reaper",
          crashed is None, repr(crashed))
    check("S3: an unreadable gateway.log keeps today's bare reason byte-identical",
          reason3 == BARE, reason3)

    # ---- S4: absent gateway log entirely -> bare reason, no crash ----
    shutil.rmtree(gw_dir, ignore_errors=True)
    r4 = run_frozen_case(runs, "r8-gwabsent", anchor)
    crashed = None
    try:
        reason4 = reaped_reason(door, r4)
    except Exception as exc:
        crashed, reason4 = exc, "__raised__"
    check("S4: an absent gateway.log never crashes the reaper and keeps the bare reason",
          crashed is None and reason4 == BARE, f"{crashed!r} {reason4}")

print(f"\n{checks - failures}/{checks} checks passed")
sys.exit(0 if failures == 0 else 1)
