#!/usr/bin/env python3
"""est-g255 r2 R2 (zap CHANGES at 1233d3fd, HIGH) — ancestor lending must
require the child occupant's IDENTITY, not bare PID ancestry membership.

Failure (zap r2 probes-repo.json / contradicted-lending): a ticket whose child
pid sits in this process's ancestor chain is LENT (exempt from the cap) even
when the pinned child identity is CONTRADICTED (child_boottime disagrees with
the live occupant's start tick) — a live runner holder keeps the ticket
occupied, so the stale child pin must not buy the exemption. The crafted row
{pid: live runner, child: <live ancestor pid>, child_boottime: -1} admitted a
second seat at cap=1 while the occupied ticket remained.

Fix contract (wf.py): the lending exemption at _seat_live_tickets requires the
SAME child occupant to be proven live — _seat_holder_live(child, child_boottime)
(#80 occupant identity: pid liveness plus kernel start-tick equality). A
contradicted (recycled) child identity = no lend; the ticket counts. A legibly
proven child still lends (no over-refusal), and a legacy unpinned child row is
not disproved by this gate (same never-disprove law as the holder check).

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_lending_identity_r2_g255.py
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-r2-lend"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
os.environ["DUCKWORK_HOME"] = str(HOME)
for k in ("WF_SEATS_DIR", "WORKFLOW_MAX_SEATS", "WF_TEST_BUILD", "WF_RUNS_ROOT"):
    os.environ.pop(k, None)
_spec = importlib.util.spec_from_file_location("hw_r2_lend", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " ) + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

seats = HOME / "seats"
OWN_BT = wf._proc_boottime(os.getpid())
PARENT_PID = os.getppid()
PARENT_BT = wf._proc_boottime(PARENT_PID)   # the real live start tick of our parent

def craft(row):
    shutil.rmtree(seats, ignore_errors=True)
    seats.mkdir(parents=True)
    (seats / "occupant.json").write_text(json.dumps(row))

base_holder = {"pid": os.getpid(), "boottime": OWN_BT, "name": "runner",
               "ts": round(time.time(), 3)}

# ---------- (1) CONTRADICTED child identity: live occupying pid, child pinned
# to a live ancestor pid with a bogus boottime — the occupant is a stranger.
# No lending exemption may fire: the occupied ticket must still COUNT (cap=1
# denies admission), exactly zap's crafted control (child_boottime contradicted).
craft({**base_holder, "child": PARENT_PID, "child_boottime": -1})
t = wf._seat_acquire(seats, "LEND-CONTRA", 1, 0.4)
left = (seats / "occupant.json").exists()
check("contradicted child identity does NOT lend: cap=1 stays occupied, no "
      "second admission (zap control: live pid + contradicted boottime)",
      t is None and left,
      f"admitted on a contradicted child pin: got={t} ticket_still_there={left}")
if t is not None:
    wf._seat_release(t)

# ---------- (2) CONTROL (positive): the SAME shape with the child's REAL boot
# identity — the genuine nested-runner case — still lends, admission proceeds.
craft({**base_holder, "child": PARENT_PID, "child_boottime": PARENT_BT})
t2 = wf._seat_acquire(seats, "LEND-REAL", 1, 0.4)
check("a boottime-proven child occupant in the ancestry still LENDS "
      "(no over-refusal regression)",
      t2 is not None and (seats / "occupant.json").exists(),
      "legit nesting now refused — lending gate became a blanket no")
if t2 is not None:
    wf._seat_release(t2)

# ---------- (3) CONTROL: legacy child row with NO pinned child_boottime is not
# disproved by the identity gate (same never-disprove law as _seat_holder_live);
# the r1 nesting shape keeps lending.
craft({**base_holder, "child": PARENT_PID})
t3 = wf._seat_acquire(seats, "LEND-LEGACY", 1, 0.4)
check("a legacy child row without a pinned boottime is not disproved and still "
      "lends", t3 is not None,
      f"legacy lending broke: got={t3}")
if t3 is not None:
    wf._seat_release(t3)

# ---------- (4) a child that is verifiably GONE (pid dead) must not lend
# either — the exemption is only for a proven-live ancestor child.
kid = subprocess.Popen([sys.executable, "-c", "pass"])
kid.wait(timeout=15)
craft({**base_holder, "child": kid.pid, "child_boottime": 1})
t4 = wf._seat_acquire(seats, "LEND-DEAD", 1, 0.4)
check("a dead child pin does not lend (occupied ticket still counts)",
      t4 is None, f"admitted on a dead child pin: got={t4}")
if t4 is not None:
    wf._seat_release(t4)

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
