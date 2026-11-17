#!/usr/bin/env python3
"""est-g255 P255-1 (zap, HIGH) — a fan-out straggler waiting on the GLOBAL seat
must honour quorum cancellation: once `quorum` items are done, an item still
blocked in _seat_acquire must NEVER spawn.

Base failure (zap quorum-control.json: cap=1, fanout_concurrency=2, quorum=1):
the winner's child exited, quorum fired, _cancel_stragglers set fo_cancel — and
the blocked straggler, whose acquire loop only checks meta['_stop'], took the
just-freed ticket and spawned AFTER the winner committed done (its subprocess
span starts after the first child's end; both items reported done).

Fix contract (wf.py):
  * the fan-out cancel Event is passed into the seat-wait/spawn seam
    (run_child seat_cancel=...): the acquire abort predicate AND the atomic
    pre-Popen guard both honour it;
  * the winner's final-seat release and the quorum cancel are ATOMIC against
    ticket creation (shared admit lock == the fan-out results lock), so no
    straggler can observe a free ticket before fo_cancel is visible.

Control: cap=1, item_concurrency=2, quorum=1, two items (one fast default
answer, one QSLEEP straggler). Exactly ONE child may ever spawn; the second
item must land as cancelled, never as a spawn.

Run: DUCKWORK_HOME=$(mktemp -d) PYTHONPATH=/opt/duckwork python3 tests/test_seat_quorum_straggler_g255.py
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-p255-1"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
RUNS = HOME / "workflows"
SEATS = HOME / "seats"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def mk(run_id):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    # cap=1 + TWO concurrent items: whichever wins the seat, the OTHER is
    # already parked inside _seat_acquire (both threads enter within ms; the
    # winner's child lives >= ~0.5 s) when the winner's completion fires
    # quorum. Base code checks neither fo_cancel inside the acquire loop nor
    # at the pre-Popen guard -> the parked item takes the freed ticket and
    # spawns; that is the violation, whichever item won.
    node = {"id": "w", "type": "agent",
            "fanout": {"goal": "{item.goal}", "quorum": 1,
                       "items": [{"goal": "QSLEEP 3 slow lane"}, {"goal": "PLAIN quick lane"}]}}
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": str(HERE / "fake"), "concurrency": 1, "item_concurrency": 2,
         "node_timeout": 60, "max_seats": 1}))
    return r

def events(r):
    p = r / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

def wait_done(r, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = r / "nodes" / "w.json"
        if p.exists():
            try:
                d = json.loads(p.read_text())
            except Exception:
                d = {}
            if d.get("status") in ("done", "failed"):
                return d
        time.sleep(0.1)
    raise AssertionError("node w never committed")

r = mk("g255-quorum-straggler")
fake_log = HOME / "fake_p255_1.log"
fake_log.write_text("")
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_SEATS_DIR=str(SEATS),
           FAKE_LOG=str(fake_log))
proc = subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
rec = wait_done(r)
proc.wait(timeout=90)

# The straggler may poll for a moment after the node commits; give the late
# spawn a full window before asserting nothing ever spawned for item 2.
time.sleep(3)
spawns = [l for l in fake_log.read_text().splitlines() if l.strip()]
check("quorum node committed done on one answer", rec.get("status") == "done",
      json.dumps({k: rec.get(k) for k in ("status", "error_class", "error")})[:200])

results = (rec.get("output") or {}).get("all_results") or []
done = [x for x in results if x.get("status") == "done"]
cancel = [x for x in results if x.get("error_class") == "cancelled"]
check("exactly one item done", len(done) == 1, json.dumps([x.get("status") for x in results]))
check("the seat-waiting straggler is cancelled (never a late spawn)",
      len(cancel) == 1, json.dumps([{k: x.get(k) for k in ("status", "error_class", "error")}
                                    for x in results])[:300])
check("NEVER any child spawns for the straggler after quorum (FAKE_LOG spawn count)",
      len(spawns) == 1, f"{len(spawns)} children spawned: {spawns}")
check("straggler cancelled, not typed seat_wait (it was cancelled, the seat existed)",
      all(x.get("error_class") != "seat_wait" for x in results),
      json.dumps([x.get("error_class") for x in results]))

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
