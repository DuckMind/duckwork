#!/usr/bin/env python3
"""est-g255 P255-3 (zap, HIGH) — ticket and heartbeat identity must be more
than a bare PID, and an unreadable registry must never silently undercount.

Base failures (zap independent-results.json):
  * a corrupt busy.json was RETAINED but a new cap=1 seat was admitted —
    malformed ticket rows are silently omitted from the live count
    (_seat_live_tickets `continue`s past them), so a torn/unreadable registry
    undercounts capacity instead of preserving it;
  * a ticket carrying a real local child PID plus a contradictory synthetic
    starttime=-1 counted as live, and a heartbeat naming an unrelated PID with
    ts=0 and an empty observed subtree PROVED life — PID-only identity lets a
    stale/reused pid or a synthetic row keep a seat or a silence kill alive.

Fix contract (wf.py):
  * tickets record process boot identity at acquire/bind (pid + /proc starttime
    via the existing identity-primitive shape, _proc_alive-adjacent);
    liveness must match BOTH pid and boot identity — a contradictory starttime
    is disproved, never trusted;
  * a ticket row that cannot be parsed (corrupt/unreadable) preserves
    UNCERTAIN capacity: it counts as live (never pruned, never admitted past
    cap);
  * a heartbeat proves life only with a real positive stamp (ts > 0) — an
    unproven ts=0 row proves nothing.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_ticket_identity_g255.py
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-p255-3"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
os.environ["DUCKWORK_HOME"] = str(HOME)
_spec = importlib.util.spec_from_file_location("hw_g255_id", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

class _P:
    def __init__(self, pid): self.pid = pid

seats = HOME / "seats"

# ---------- (1) corrupt ticket preserves capacity, never silently undercounts.
shutil.rmtree(seats, ignore_errors=True)
seats.mkdir(parents=True)
(seats / "corrupt.json").write_text("{not json at all")     # torn write shape
t = wf._seat_acquire(seats, "X", 1, 0.5)
check("cap=1 with a CORRUPT ticket present: NOT admitted (uncertain capacity preserved)",
      t is None, "admitted through an unreadable registry — silent undercount")

# ---------- (2) contradictory boot identity disproves the seat holder.
shutil.rmtree(seats, ignore_errors=True)
seats.mkdir(parents=True)
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
try:
    # (2a) a healthy ticket bound to a LIVE child still counts.
    (seats / "live.json").write_text(json.dumps(
        {"pid": kid.pid, "child": kid.pid, "name": "n", "ts": round(time.time(), 3)}))
    t = wf._seat_acquire(seats, "X", 1, 0.3)
    check("a healthy ticket on a live child still counts (no over-refusal regression)",
          t is None, "live seat lost capacity")
    if t is None:
        pass
    else:
        wf._seat_release(t)

    # (2b) a ticket written by the product records the holder's boot identity
    # (pid + process start time) — a fresh acquire must stamp it.
    shutil.rmtree(seats, ignore_errors=True)
    seats.mkdir(parents=True)
    own = wf._seat_acquire(seats, "OWN", 4, 0.3)
    row = json.loads(own.read_text()) if own else {}
    check("an acquired ticket records the holder's boot identity (pid + start time)",
          isinstance(row.get("boottime"), int) and row["boottime"] > 0, json.dumps(row))
    if own:
        wf._seat_bind(own, kid.pid)
        row = json.loads(own.read_text())
        check("binding the child records the child's boot identity too",
              isinstance(row.get("child_boottime"), int) and row["child_boottime"] > 0,
              json.dumps(row))
        wf._seat_release(own)

    # (2c) PID REUSE shape: the pids are live, but the recorded boot identity
    # CONTRADICTS the live processes' — the recorded holders are gone and the
    # pids were recycled. The identity primitive disproves the seat: pruned,
    # capacity freed (a reused pid must never hold a seat forever).
    (seats / "reused.json").write_text(json.dumps(
        {"pid": kid.pid, "child": kid.pid, "boottime": 1, "child_boottime": 1,
         "name": "n", "ts": round(time.time(), 3)}))
    t = wf._seat_acquire(seats, "X", 1, 0.5)
    check("a ticket whose recorded boot identity contradicts the live pid (reuse) is "
          "disproved and pruned — the seat admits",
          t is not None and not (seats / "reused.json").exists(),
          "a recycled pid kept holding the seat")
    if t is not None:
        wf._seat_release(t)

    # ---------- (3) heartbeat: an UNPROVEN stamp (ts=0) proves nothing.
    tmp = HOME / "pol"; tmp.mkdir(exist_ok=True)
    lp0 = tmp / "zero.log"; lp0.write_text("")
    hb = tmp / "h.log.alive"
    hb.write_text(json.dumps({"pid": kid.pid, "ts": 0}))
    check("heartbeat ts=0 (never stamped by a real observation) does NOT prove life",
          wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is False,
          "ts=0 synthetic heartbeat proved life")
    hb.write_text(json.dumps({"pid": kid.pid, "ts": round(time.time(), 3), "boottime": 1}))
    check("heartbeat whose recorded boot identity contradicts the live pid (reuse) "
          "does NOT prove life", wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is False,
          "recycled-pid heartbeat proved life")
    hb.write_text(json.dumps({"pid": kid.pid, "ts": round(time.time(), 3)}))
    check("heartbeat with NO recorded boot identity (unproven row) does NOT prove life",
          wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is False,
          "identity-less heartbeat proved life")
    hb.unlink()
    wf._stamp_heartbeat(hb, kid.pid)
    check("a runner-stamped heartbeat on a live observed child still proves life",
          wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is True,
          "regression: honest heartbeat no longer proves")
finally:
    try: kid.kill(); kid.wait(timeout=10)
    except Exception: pass

# ---------- (4) the dead-side stays honest: all-pids-dead ticket is still pruned.
shutil.rmtree(seats, ignore_errors=True)
seats.mkdir(parents=True)
(seats / "dead.json").write_text(json.dumps(
    {"pid": 10**9 + 7, "name": "d", "ts": round(time.time(), 3)}))
t = wf._seat_acquire(seats, "Y", 1, 1.0)
check("a verifiably dead ticket is still pruned and the seat admits", t is not None,
      "dead ticket blocks forever (regression)")
if t is not None:
    wf._seat_release(t)

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
