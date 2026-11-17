#!/usr/bin/env python3
"""est-g255 P255-2 (zap, HIGH) — the advertised BOUNDED seat wait is unbounded
while blocked in flock, and admits after the deadline / abort.

Base failure (zap independent-results.json / lock_contention_timeout_and_abort):
an isolated lock holder slept 1.3 s on <seats>/.lock; a waiter with bounded_s
0.15 and abort=True nevertheless ADMITTED at 1.304 s — flock LOCK_EX blocks
before either predicate is checked, so a stuck lock holder defeats the node
wall and the stop path.

Fix contract (wf.py): deadline-aware, cancellable admission — non-blocking
LOCK_EX|LOCK_NB poll loop with the deadline honoured BETWEEN attempts, plus a
deadline/abort recheck AFTER acquisition and immediately BEFORE ticket
creation; a refused acquire leaves no ticket behind.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_admission_deadline_g255.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-p255-2"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
os.environ["DUCKWORK_HOME"] = str(HOME)
DRIVER = HERE / "fixtures" / "seat_acquire_driver.py"

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def drive(seats, name, hold, cap, bounded="-", abort_after="-", hold_lock="-", env_extra=None):
    argv = [sys.executable, str(DRIVER), str(seats), name, str(hold), str(cap),
            str(bounded), str(abort_after), str(hold_lock)]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, DUCKWORK_HOME=str(HOME), **(env_extra or {})))
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": p.stdout[:200], "err": p.stderr[-400:]}

# --- control 1: an EMPTY seats dir, but .lock held by a stuck holder for 1.3 s.
# A bounded 0.15 s / abort 0.1 s waiter must refuse typed at ~0.1 s and create
# NO ticket. Base blocks in flock LOCK_EX and admits anyway after 1.3 s.
seats = HOME / "seats-lock"
out = drive(seats, "B", 0.0, 4, bounded=0.15, abort_after=0.1, hold_lock=1.3)
check("stuck .lock holder cannot defeat the bounded wait (refused, not admitted)",
      out.get("ok") is False, json.dumps(out)[:300])
check("refusal is typed seat_wait (abort honoured), not an admission",
      out.get("error_class") == "seat_wait", json.dumps(out)[:200])
check("the bounded wait stayed bounded through the blocked flock (never ~lock-hold long)",
      isinstance(out.get("waited_s"), (int, float)) and out["waited_s"] < 0.6,
      json.dumps(out)[:200])
check("a refused acquire left NO ticket behind",
      out.get("tickets_left") == [], json.dumps(out)[:200])

# --- control 2: deadline honoured while a FULL seat lives beyond it (cap 1,
# holder 6 s, waiter bounded 1 s) — the pre-fix loop's post-lock check existed
# only between iterations; assert expiry AND no stray ticket.
seats2 = HOME / "seats-full"
h = subprocess.Popen([sys.executable, str(DRIVER), str(seats2), "HOLDER", "6", "1"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=dict(os.environ, DUCKWORK_HOME=str(HOME)))
import time; time.sleep(0.5)
out2 = drive(seats2, "W", 0.0, 1, bounded=1.0)
h.wait(timeout=30)
check("full semaphore + bounded wait expiry -> typed seat_wait", out2.get("ok") is False and
      out2.get("error_class") == "seat_wait", json.dumps(out2)[:200])
check("waiter gave up near its bounded_s (not after the holder)",
      isinstance(out2.get("waited_s"), (int, float)) and 0.8 <= out2["waited_s"] <= 2.0,
      json.dumps(out2)[:200])
check("expiry left no ticket of the waiter's own (only the live holder's)",
      not [t for t in out2.get("tickets_left", ["?"]) if not t.startswith("HOLDER.")],
      json.dumps(out2)[:200])

# --- control 3: normal path still works (a held seat that frees inside the
# bounded window is acquired).
seats3 = HOME / "seats-normal"
o1 = subprocess.Popen([sys.executable, str(DRIVER), str(seats3), "A", "1.0", "1"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                      env=dict(os.environ, DUCKWORK_HOME=str(HOME)))
time.sleep(0.3)
out3 = drive(seats3, "B", 0.1, 1, bounded=5)
o1.wait(timeout=30)
check("contention that clears inside the window still admits", out3.get("ok") is True,
      json.dumps(out3)[:200])

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
