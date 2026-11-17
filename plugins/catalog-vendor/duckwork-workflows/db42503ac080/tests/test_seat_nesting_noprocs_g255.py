#!/usr/bin/env python3
"""est-g255 P255-5 (zap, MED) — nested-ticket lending depends entirely on
Linux /proc; on a no-procfs platform the ancestor set is silently empty and a
nested admission deadlocks to the seat_wait expiry instead of lending.

Base failure (zap independent-results.json / no_procfs_nested_admission): with
only /proc reads made absent, the same held ancestor-shaped ticket Linux
excludes (count=0) was counted by the waiter, cap=1 nested admission expired.
_proc_alive has a ps fallback; _ancestors has NONE. Native Darwin was not
available and is not claimed tested — so the contract this test pins is the
OTHER allowed answer zap accepted: prove nesting WITHOUT /proc (ps ppid
fallback), and where NO identity channel exists, REFUSE typed with a clear
error class instead of silently deadlocking.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_nesting_noprocs_g255.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-p255-5"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
os.environ["DUCKWORK_HOME"] = str(HOME)
DRIVER = HERE / "fixtures" / "seat_acquire_driver.py"

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def drive(seats, name, hold, cap, bounded=5, env_extra=None):
    argv = [sys.executable, str(DRIVER), str(seats), name, str(hold), str(cap), str(bounded)]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, DUCKWORK_HOME=str(HOME), **(env_extra or {})))
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": p.stdout[:200], "err": p.stderr[-400:]}

# ---------- (A) honest no-procfs platform: /proc ppid reads fail, ps works.
# The ancestor-shaped held ticket must still be LENT (nested admission SUCCEEDS
# within bounded), driven by a ps-backed ancestor walk — the exact shape a
# real macOS/BSD runner presents.
seats = HOME / "seats-ps"
out = drive(seats, "NESTED", 0.2, 1, env_extra={
    "SEAT_FAKE_NOPROCS": "1", "SEAT_SEED_ANCESTOR": "1"})
check("no-procfs + ps fallback: the ancestor ticket is LENT, nested admission proceeds",
      out.get("ok") is True,
      f"nesting silently deadlocked to expiry without /proc: {json.dumps(out)[:260]}")
check("the ps-backed ancestor walk saw the parent pid",
      os.getpid() in (out.get("ancestors") or []),
      f"ancestors={out.get('ancestors')} (pid {os.getpid()} not found without /proc)")

# ---------- (B) NO identity channel at all (/proc AND ps dead): the nested
# lending decision is unknowable — the runner must REFUSE typed (never admit an
# unknown-provenance seat, never silently burn the whole bounded wait as if the
# semaphore were merely full).
seats2 = HOME / "seats-none"
out2 = drive(seats2, "BLIND", 0.2, 1, bounded=3, env_extra={
    "SEAT_FAKE_NOPROCS": "full", "SEAT_SEED_ANCESTOR": "1"})
check("no process-identity channel at all: typed refusal seat_unsupported "
      "(never a silent deadlock masquerading as seat_wait)",
      out2.get("ok") is False and out2.get("error_class") == "seat_unsupported",
      json.dumps(out2)[:260])
check("the blind refusal gives up quickly (not the full bounded wait)",
      isinstance(out2.get("waited_s"), (int, float)) and out2["waited_s"] < 1.5,
      json.dumps(out2)[:200])
check("refusal leaves no ticket behind", out2.get("tickets_left") == [],
      json.dumps(out2)[:200])

# ---------- (C) normal Linux path unchanged: nested lending works with /proc.
seats3 = HOME / "seats-proc"
out3 = drive(seats3, "NEST2", 0.2, 1, env_extra={"SEAT_SEED_ANCESTOR": "1"})
check("normal /proc platform still lends the ancestor ticket",
      out3.get("ok") is True, json.dumps(out3)[:260])

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
