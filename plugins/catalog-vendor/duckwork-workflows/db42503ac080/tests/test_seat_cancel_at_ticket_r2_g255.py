#!/usr/bin/env python3
"""est-g255 r2 R1 (zap CHANGES at 1233d3fd, HIGH) — a quorum cancel that lands
DURING pre-spawn survivor work must still prevent Popen.

Failure (zap r2 probes-repo.json / quorum-during-sidecar): fo_cancel can be set
AFTER the atomic pre-Popen _cancelled() check — e.g. during the survivor
inspection/reaping window — yet Popen still launches a real child. The cancel
setter is not coordinated with the admission/spawn critical section, so the
"never spawn under cancellation" contract has a window between check and launch.

Fix contract (wf.py): the fan-out wires its results lock (which the quorum
setter _cancel_stragglers already holds BEFORE fo_cancel.set()) into
_seat_acquire as admit_lock; _seat_acquire takes admit_lock -> .lock flock and
RECHECKS the abort predicate under both, ATOMICALLY with ticket creation. A
cancel landing before that recheck can never yield a ticket, hence never a
Popen.

Controls (run under empty DUCKWORK_HOME + isolated WF_RUNS_ROOT):
  A) the admission seam: a cancel that becomes visible after the FIRST abort
     check must deny the ticket at the creation instant — zero tickets written.
  B) the spawn seam end-to-end: a cancel landing between the cancel-check
     round-trip and the launch must prevent the spawn — zero children.
  C) control: with NO cancel, admission proceeds (the gate is not a blanket no).

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_cancel_at_ticket_r2_g255.py
"""
import importlib.util, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-r2-cancel"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)
for k in ("WF_SEATS_DIR", "WORKFLOW_MAX_SEATS", "WF_TEST_BUILD", "FAKE_LOG"):
    os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location("hw_r2_cancel", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " ) + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

HAVE_PARAM = "admit_lock" in list(__import__("inspect").signature(
    wf._seat_acquire).parameters)
check("_seat_acquire exposes an admit-lock seam for the cancel coordinator",
      HAVE_PARAM, "no admit_lock parameter — the cancel setter has nothing to "
      "coordinate with at the ticket-creation instant")

# ---------- (A) cancel lands AFTER the first abort check, BEFORE ticket write.
# A concurrent setter flips abort() True right after the waiter's first
# pre-lock check has passed. With the fix, the under-admit_lock RECHECK at the
# ticket-creation instant sees it: the waiter never writes a ticket.
seats = HOME / "seats-A"
seats.mkdir(parents=True)
ev_first_check = threading.Event()
ev_set_soon = threading.Event()
ev_set_done = threading.Event()
n_checks = [0]
real_aborts = [0]

def _abort_a():
    n_checks[0] += 1
    if n_checks[0] == 1:
        return False                    # first check passes (pre-lock poll)
    if not ev_first_check.is_set():
        ev_first_check.set()            # the waiter is past its first check...
        ev_set_soon.wait(5)             # ...the cancel lands DURING its work
        return True
    return True

def _setter():
    ev_first_check.wait(5)
    ev_set_done.clear()
    real_aborts[0] = 1
    ev_set_soon.set()
    ev_set_done.set()

t_set = threading.Thread(target=_setter, daemon=True)
t_set.start()
al = threading.Lock() if HAVE_PARAM else None
t0 = time.time()
try:
    got = wf._seat_acquire(seats, "R2A", 1, 3.0, abort=_abort_a,
                           **({"admit_lock": al} if HAVE_PARAM else {}))
except TypeError:
    got = wf._seat_acquire(seats, "R2A", 1, 3.0, abort=_abort_a)
waited = time.time() - t0
t_set.join(5)
tickets = sorted(p.name for p in seats.glob("*.json")) if seats.exists() else []
check("A: a cancel landing after the first check DENIES the ticket (never a "
      "ticket + spawn with cancellation already set)",
      got is None, f"admitted after cancel: {got}")
check("A: no ticket file was ever created under cancellation",
      tickets == [], f"ticket written despite cancel: {tickets}")
check("A: the cancel really landed before the denial (setter observed, abort "
      "polled at least twice — the seam was exercised, not short-circuited)",
      ev_set_done.is_set() and n_checks[0] >= 2,
      f"checks={n_checks[0]} setter_done={ev_set_done.is_set()}")

# ---------- (B) spawn seam: a cancel landing around the survivor work must
# prevent Popen end-to-end. run_child is driven directly with seat_cancel;
# fo_cancel is set from a side thread the instant the product's own survivor
# inspection runs (the exact zap schedule: set DURING pre-spawn work).
seats_b = HOME / "seats-B"
run = RUNS / "r2-cancel-spawn"
(run / "nodes").mkdir(parents=True)
node = {"id": "cx", "type": "agent", "goal": "ok"}
(run / "graph.json").write_text(json.dumps({"name": "r", "nodes": [node]}))
fake_log = HOME / "fake_r2_cancel.log"
fake_log.write_text("")
real_live = wf._sidecar_live_registered
cancel = threading.Event()

def _live_then_cancel(run_, tokens, meta_=None):
    out = real_live(run_, tokens, meta_)
    cancel.set()                       # quorum lands DURING survivor work
    return out

wf._sidecar_live_registered = _live_then_cancel
meta = {"_run": run, "duckwork_bin": str(HERE / "fake"), "_spawn_n": {},
        "_procs_lock": threading.Lock(), "_procs": {}, "_stop": threading.Event(),
        "node_timeout": 30}
os.environ["WF_SEATS_DIR"] = str(seats_b)
os.environ["FAKE_LOG"] = str(fake_log)
try:
    res = wf.run_child(meta, node, {"cx": node}, "ok", "", None, skey="wf:r:cx",
                       seat_cancel=cancel)
finally:
    wf._sidecar_live_registered = real_live

time.sleep(0.4)
spawns = [l for l in fake_log.read_text().splitlines() if l.strip()]
leftover = sorted(p.name for p in seats_b.glob("*.json")) if seats_b.exists() else []
check("B: cancel landing during survivor work PREVENTS the spawn (control: the "
      "same schedule at base launches a real child)",
      spawns == [], f"{len(spawns)} children launched despite cancel: {spawns}")
check("B: the spawn is denied as cancelled (typed), not seat_wait",
      res.get("error_class") == "cancelled",
      json.dumps({k: res.get(k) for k in ("status", "error_class", "error")})[:220])
check("B: no ticket retained after the denied spawn", leftover == [],
      f"leaked tickets: {leftover}")
ps = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                    text=True).stdout
ours = [l for l in ps.splitlines() if "fake_duckwork.py" in l and str(HOME) in l]
check("B: no orphan fake child survives", ours == [], f"survivors: {ours}")

# ---------- (C) control: no cancel at all — admission still works (the R1
# gate is a cancel gate, never a blanket denial).
seats_c = HOME / "seats-C"
al = threading.Lock() if HAVE_PARAM else None
try:
    got_c = wf._seat_acquire(seats_c, "R2C", 1, 2.0,
                             **({"admit_lock": al} if HAVE_PARAM else {}))
except TypeError:
    got_c = wf._seat_acquire(seats_c, "R2C", 1, 2.0)
check("C: without any cancellation, admission still proceeds",
      got_c is not None and Path(got_c).exists(),
      f"admission broken: {got_c}")
if got_c is not None and not hasattr(got_c, "name"):
    pass
if got_c is not None:
    wf._seat_release(got_c)

for k in ("WF_SEATS_DIR", "FAKE_LOG"):
    os.environ.pop(k, None)
shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
