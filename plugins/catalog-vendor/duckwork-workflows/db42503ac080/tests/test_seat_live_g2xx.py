#!/usr/bin/env python3
"""est-g2xx — heartbeat liveness past a buffered child + global agent-seat cap.

Two proven failures (run dirs: lane-shelf/*-rseat-hang-exhausted, 2026-10-06):

 (A) the child CLI block-buffers stdout to its spawn log — a WORKING child sat at
     exactly 360 B for >120 s and was false-killed as early_death. The silence law
     must trust MORE than log bytes: a child that has verifiably begun executing
     (a live tool child in its subtree, proven through the existing _tree_watch
     machinery, or a runner-stamped alive-at-spawn heartbeat) is PROVEN and must
     not be early-killed while it stays that way.

 (B) under ~13 concurrent agent seats the seat answers some requests and hangs
     others for 30+ min. The runner holds a GLOBAL cross-process agent-seat
     semaphore: WORKFLOW_MAX_SEATS (env, default 4; run.json meta max_seats
     overrides), tickets in a shared dir (WF_SEATS_DIR env >
     <runs_root>/.seats). A full semaphore BLOCKS the spawn (bounded wait == the
     node timeout, typed seat_wait failure on expiry), logs seat.wait, and
     releases on reap. Stale tickets (owner pid verifiably dead) are pruned at
     acquire.

Run: cd tests && python3 test_seat_live_g2xx.py
"""
import importlib.util
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home-g2xx"
os.environ["DUCKWORK_HOME"] = str(HOME)   # runs_root() resolves in-process

_spec = importlib.util.spec_from_file_location("hw_g2xx", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)

# ---------- unit: _proof_of_life — bytes OR a live executing child --------------
tmp = HOME / "pol"
tmp.mkdir(parents=True)

class _P:
    def __init__(self, pid): self.pid = pid

HAVE_POL = hasattr(wf, "_proof_of_life") and hasattr(wf, "_stamp_heartbeat")
check("runner exposes _proof_of_life/_stamp_heartbeat", HAVE_POL)
if HAVE_POL:
    lp0 = tmp / "zero.log"          # 0-byte spawn log: no bytes ever
    lp0.write_text("")

    # 1) 0-byte log, nobody alive, no heartbeat -> NOT proven (silence law still bites)
    check("0-byte silent child is NOT proven alive",
          wf._proof_of_life(lp0, _P(os.getpid()), tmp / "none.log.alive", set()) is False)

    # 2) 0-byte log BUT a live tool child in the spawn's tracked subtree -> proven
    kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        check("0-byte child with a live tool child IS proven alive (re-fire pattern)",
              wf._proof_of_life(lp0, _P(os.getpid()), tmp / "none2.log.alive", {kid.pid}) is True)
        # 3) heartbeat = durable memory of an OBSERVED live tool child: proof holds
        # with the subtree set emptied (the sample can miss it) while that pid lives.
        hb = tmp / "h.log.alive"
        wf._stamp_heartbeat(hb, kid.pid)
        check("0-byte child with a heartbeat on an observed-live tool child IS proven alive",
              wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is True)
        kid.kill(); kid.wait(timeout=10)
        time.sleep(0.1)
        check("bytes=0 + dead heartbeat pid + no subtree -> NOT proven",
              wf._proof_of_life(lp0, _P(os.getpid()), hb, set()) is False)
    finally:
        try: kid.kill()
        except Exception: pass

    # 4) bytes alone still prove (existing law preserved)
    lp1 = tmp / "one.log"
    lp1.write_text("some output")
    check("bytes on the log still prove life",
          wf._proof_of_life(lp1, _P(os.getpid()), tmp / "missing.alive", set()) is True)


# ---------- unit: seat semaphore — 2 processes, cap 1, serialization proven ----
seats = HOME / "seatdir"
DRIVER = ROOT / "tests" / "fixtures" / "seat_acquire_driver.py"
check("seat driver fixture exists", DRIVER.is_file())
HAVE_SEAT = hasattr(wf, "_seat_acquire") and hasattr(wf, "_seat_release")
check("runner exposes _seat_acquire/_seat_release", HAVE_SEAT)

def _seat_proc(name, hold_s, cap, bounded=None):
    argv = [sys.executable, str(DRIVER), str(seats), name, str(hold_s), str(cap)]
    if bounded is not None:
        argv.append(str(bounded))
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=dict(os.environ, DUCKWORK_HOME=str(HOME)))

if DRIVER.is_file() and HAVE_SEAT:
    p1 = _seat_proc("A", 2.0, 1)
    time.sleep(0.4)                       # A is in, holding
    t0 = time.time()
    p2 = _seat_proc("B", 0.2, 1)
    out1 = json.loads(p1.communicate(timeout=60)[0])
    out2 = json.loads(p2.communicate(timeout=60)[0])
    check("both seat holders succeeded", out1.get("ok") and out2.get("ok"),
          json.dumps([out1, out2])[:300])
    check("holder B acquired only after A released (serialization, not concurrency)",
          out2.get("acquired_after") is not None and out1.get("released_at") is not None
          and out2["acquired_after"] >= out1["released_at"],
          json.dumps([out1, out2])[:300])
    check("B's acquire was blocked ~A's remaining hold",
          out2.get("waited_s", 0) >= 0.8, json.dumps(out2)[:200])

    # seat_wait typed failure: holder at cap for longer than the bounded wait
    p3 = _seat_proc("C", 6.0, 1)
    time.sleep(0.4)
    p4 = _seat_proc("D", 0.2, 1, bounded=1.0)
    out3 = json.loads(p3.communicate(timeout=60)[0])
    out4 = json.loads(p4.communicate(timeout=60)[0])
    check("full semaphore + bounded wait expiry -> typed seat_wait",
          out4.get("ok") is False and out4.get("error_class") == "seat_wait",
          json.dumps(out4)[:200])

    # stale-ticket prune: a ticket whose owner pid is dead does not block forever
    seats.mkdir(parents=True, exist_ok=True)
    dead = seats / "dead.json"    # pid almost certainly nonexistent
    dead.write_text(json.dumps({"pid": 10**9 + 7, "ts": time.time()}))
    p5 = _seat_proc("E", 0.1, 1)
    out5 = json.loads(p5.communicate(timeout=30)[0])
    check("stale ticket (owner pid dead) is pruned, seat acquired",
          out5.get("ok") is True, json.dumps(out5)[:200])

# ---------- engine: buffered child (0-byte log + live tool child) survives -------
RUNS = HOME / "workflows"
def mk(run_id, meta_extra=None):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(
        {"name": run_id, "nodes": [{"id": "w", "type": "agent", "goal": "work"}]}))
    m = {"duckwork_bin": str(BUILD / "fake"), "concurrency": 1, "node_timeout": 90}
    m.update(meta_extra or {})
    (r / "run.json").write_text(json.dumps(m))
    return r

def _scrubbed_env(extra=None):
    """Hermetic child env (the test_wake_hermetic_env.py law): an inherited
    WF_* (e.g. WF_RUNS_ROOT from a bot seat env) OUTRANKS DUCKWORK_HOME in the
    runs-root resolver, so the child runner resolves elsewhere and the
    buffered-child case dies "node w never committed within 120s". Build from
    a scrubbed copy: pop every WF_* key, then pin our own home + runs root."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("WF_")}
    env["DUCKWORK_HOME"] = str(HOME)
    env["WF_RUNS_ROOT"] = str(RUNS)
    env.update(extra or {})
    return env

def launch(r, env_extra=None):
    return subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                            env=_scrubbed_env(env_extra),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_node(r, nid="w", timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = r / "nodes" / f"{nid}.json"
        if p.exists():
            try: d = json.loads(p.read_text())
            except Exception: d = {}
            if d.get("status") in ("done", "failed"):
                return d
        time.sleep(0.1)
    raise AssertionError(f"node {nid} never committed within {timeout}s")

def events(r):
    p = r / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

# (A) engine: silent-stdout child that spawns a live tool child and answers LATE
# must NOT die early_death (the buffered re-fire pattern).
rA = mk("g2xx-buffered", {"first_message_s": 2, "node_timeout": 90})
procA = launch(rA, {"FAKE_MODE": "buffered_child", "FAKE_BUFFERED_SLEEP": "5"})
procA.wait(timeout=120)
recA = wait_node(rA)
check("buffered child (0-byte log + live tool child) is NOT false-killed as early_death",
      recA.get("status") == "done",
      json.dumps({k: recA.get(k) for k in ("status", "error_class", "error")})[:250])

# (A-negative) a truly silent child with NO tool child still dies early_death.
rB = mk("g2xx-silent", {"first_message_s": 2, "node_timeout": 30})
procB = launch(rB, {"FAKE_MODE": "hang", "FAKE_HANG_SEC": "30"})
procB.wait(timeout=90)
recB = wait_node(rB, timeout=30)
check("truly silent child (no bytes, no tool child) still dies early_death",
      recB.get("error_class") == "early_death",
      json.dumps({k: recB.get(k) for k in ("status", "error_class")})[:200])

# (B) engine: two runners, cap 1 — children never run concurrently, and the
# blocked runner logs seat.wait.
rC = mk("g2xx-seat-1", {"max_seats": 1})
rD = mk("g2xx-seat-2", {"max_seats": 1})
marker = HOME / "seat_overlap.log"
common = {"FAKE_MODE": "seat_timing", "SEAT_MARK": str(marker)}
procC = launch(rC, common); procD = launch(rD, common)
procC.wait(timeout=120); procD.wait(timeout=120)
recC = wait_node(rC, timeout=30); recD = wait_node(rD, timeout=30)
spans = []
if marker.exists():
    for line in marker.read_text().splitlines():
        try:
            row = json.loads(line); spans.append((row["start"], row["end"]))
        except Exception: pass
overlap = any((a_s, a_e) != (b_s, b_e) and a_s < b_e and b_s < a_e
              for a_s, a_e in spans for b_s, b_e in spans)
check("both seat-capped runs finished done",
      recC.get("status") == "done" and recD.get("status") == "done",
      json.dumps([recC.get("status"), recD.get("status")]))
check("seat cap serialized the two children (no span overlap)",
      len(spans) == 2 and not overlap, json.dumps(spans))
check("the blocked runner logged a seat.wait event",
      any(e.get("event") == "seat.wait" for e in events(rC) + events(rD)),
      "no seat.wait in either run")

print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
