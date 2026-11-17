#!/usr/bin/env python3
"""est-g255 r3 (zap CHANGES at 81826493, HIGH) — the seat-admission loop must
be bounded THROUGH admit_lock contention, not just through the .lock flock.

Failure (zap probes: stamp-queue-r3/parent-admit-lock-probes.json): the
admit_lock acquisition in _seat_acquire is a bare `with al_cm:` — a plain
Lock.acquire() with NO deadline/abort checks. A contended admit_lock (the
fan-out's results lock, held by sibling threads throughout survivor book-
keeping) makes a waiter with bounded_s=0.05 return only after the holder's
0.6504s release, and a waiter whose abort was set at 0.08s return only after
0.6500s. The bounded/cancellable contract dies at the mutex.

Fix contract (wf.py): admit_lock is taken with a TIMEOUT acquisition in a
loop that rechecks the same deadline/abort predicate between tries; on
timeout-while-out() it returns None (no ticket — the same contract as the
flock path); after acquiring, _out() is rechecked UNDER the lock before any
ticket is written, and the lock is released in a finally. The atomicity that
the mutex provides is preserved exactly: the cancel-setter synchronizes on
admit_lock BEFORE setting its Event, and the holder rechecks abort() under
the mutex.

Cases (run under empty DUCKWORK_HOME + isolated WF_RUNS_ROOT):
  A) contended admit_lock + finite bounded_s: the waiter must give up on its
     OWN deadline — elapsed << the holder's release delay, zero tickets.
  B) contended admit_lock + abort set mid-block: same — bounded return well
     before the holder releases, zero tickets.
  C) control: uncontended admit_lock still admits (a fresh ticket exists).
  D) control: cancel-under-mutex atomicity — a setter that synchronizes on
     admit_lock before setting abort must, scanning under the mutex, either
     SEE the holder's ticket or the waiter must deny the ticket; it can never
     miss a ticket that was actually created.

Run: env -u WF_RUNS_ROOT DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork \
     python3 tests/test_seat_admit_lock_r3.py
"""
import importlib.util, os, shutil, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-r3-admitlock"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("WF_RUNS_ROOT", None)
for k in ("WF_SEATS_DIR", "WORKFLOW_MAX_SEATS", "WF_TEST_BUILD", "FAKE_LOG"):
    os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location("hw_r3_admitlock", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " ) + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

HAVE_PARAM = "admit_lock" in list(__import__("inspect").signature(
    wf._seat_acquire).parameters)
check("_seat_acquire still exposes the admit-lock seam", HAVE_PARAM)

HOLDER_S = 0.65          # zap's fixture release delay
BOUND = 0.30             # a bounded return must land well before HOLDER_S

# ---------- (A) contended admit_lock + finite bounded_s.
seats_a = HOME / "seats-A"
seats_a.mkdir(parents=True)
al_a = threading.Lock()
held_a = threading.Event()
al_a.acquire()                     # the holder grabs it before the waiter starts
held_a.set()

def _holder_a():
    time.sleep(HOLDER_S)
    al_a.release()

t_h = threading.Thread(target=_holder_a, daemon=True)
t_h.start()
held_a.wait(2)
t0 = time.time()
got_a = wf._seat_acquire(seats_a, "R3A", 1, 0.05, admit_lock=al_a)
elapsed_a = time.time() - t0
t_h.join(5)
tickets_a = sorted(p.name for p in seats_a.glob("*.json"))
check("A: contended admit_lock does NOT outlive bounded_s (elapsed < holder "
      f"release delay {HOLDER_S}s)",
      elapsed_a < BOUND, f"elapsed={elapsed_a:.4f}s (zap r3 saw 0.6504s)")
check("A: no ticket created when the bounded wait expires under contention",
      got_a is None and tickets_a == [], f"got={got_a} tickets={tickets_a}")

# ---------- (B) contended admit_lock + abort set at 0.08s.
seats_b = HOME / "seats-B"
seats_b.mkdir(parents=True)
al_b = threading.Lock()
abort_ev = threading.Event()
al_b.acquire()

def _holder_b():
    time.sleep(HOLDER_S)
    al_b.release()

def _setter_b():
    time.sleep(0.08)
    abort_ev.set()

t_h = threading.Thread(target=_holder_b, daemon=True); t_h.start()
t_s = threading.Thread(target=_setter_b, daemon=True); t_s.start()
t0 = time.time()
got_b = wf._seat_acquire(seats_b, "R3B", 1, 3.0,
                         abort=lambda: abort_ev.is_set(), admit_lock=al_b)
elapsed_b = time.time() - t0
t_h.join(5); t_s.join(5)
tickets_b = sorted(p.name for p in seats_b.glob("*.json"))
check("B: abort set mid-block returns BEFORE the holder releases",
      elapsed_b < BOUND, f"elapsed={elapsed_b:.4f}s (zap r3 saw 0.6500s)")
check("B: no ticket created when the abort lands under admit_lock contention",
      got_b is None and tickets_b == [], f"got={got_b} tickets={tickets_b}")

# ---------- (C) control: uncontended admit_lock still admits.
seats_c = HOME / "seats-C"
got_c = wf._seat_acquire(seats_c, "R3C", 1, 2.0, admit_lock=threading.Lock())
check("C: uncontended admit_lock still admits a fresh ticket",
      got_c is not None and Path(got_c).exists(), f"got={got_c}")
if got_c is not None:
    wf._seat_release(got_c)

# ---------- (D) control: cancel-under-mutex atomicity preserved.
# The setter synchronizes on admit_lock BEFORE setting its Event and scans
# seats UNDER the mutex (the r2 R1 contract). Invariant: it is never the case
# that a ticket exists (the waiter was admitted) while the setter's under-
# mutex scan saw nothing — ticket creation and the cancel decision must be
# linearizable through the same mutex.
seats_d = HOME / "seats-D"
seats_d.mkdir(parents=True)
al_d = threading.Lock()
cancel_d = threading.Event()
seen_d = []
ev_in = threading.Event()
n_checks = [0]

def _abort_d():
    n_checks[0] += 1
    if n_checks[0] == 1:
        ev_in.set()                 # the waiter is entering admission...
    return cancel_d.is_set()

def _setter_d():
    ev_in.wait(5)                   # ...the cancel lands DURING its work
    with al_d:                      # setter synchronizes BEFORE setting
        cancel_d.set()
        seen_d.extend(p.name for p in seats_d.glob("*.json"))

got_d = [object()]
def _waiter_d():
    got_d[0] = wf._seat_acquire(seats_d, "R3D", 1, 3.0,
                                abort=_abort_d, admit_lock=al_d)

t_w = threading.Thread(target=_waiter_d, daemon=True); t_w.start()
t_sd = threading.Thread(target=_setter_d, daemon=True); t_sd.start()
t_w.join(10); t_sd.join(10)
got_dv = got_d[0]
atomic_ok = (not (got_dv is not None and seen_d == []))
check("D: cancel-under-mutex stays atomic — an admitted ticket is always seen "
      "by the setter's under-mutex scan (or the ticket was denied)",
      atomic_ok and n_checks[0] >= 2,
      f"got={got_dv} setter_saw={seen_d} checks={n_checks[0]}")
if got_dv is not None and hasattr(got_dv, "exists"):
    wf._seat_release(got_dv)

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
