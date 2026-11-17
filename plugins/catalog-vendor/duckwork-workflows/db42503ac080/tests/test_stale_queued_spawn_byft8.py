#!/usr/bin/env python3
"""est-byft8 — a queued spawn must never launch a stale definition.

The incident (estate nightly run 20261008-043243-windows-protocol-*; the full
run id lives in the tracking issue): a node sat queued on
the global agent-seat semaphore while the wave was in flight; an amend baked at
05:55:25Z was STILL dispatched at 05:57:46Z after the 05:57:34Z amendment —
run_child passed _seat_acquire and Popen'd the OLD prompt. wf.py never rechecked
the graph between the queue and the launch; Run.reload only happens at wave
boundaries, hours-long waves included.

The law (this pin):
  * launch-instant staleness check: the runner compares the node's EFFECTIVE
    FINGERPRINT (wfcommon.efp — own def minus budgets + ancestor efps) at queue
    time against efp over CURRENT graph.json. The comparison is the runner's OWN
    replay-skip staleness law, so "would a reload re-drive this node?" and "is
    this queued spawn stale?" can never disagree.
  * moved/deleted -> typed error_class=stale_graph refusal, NO Popen, seat
    released (the est-g255 P255-5 finally), zero children launched.
  * budgets are not work: a timeout/max_turns/shape-only amend does NOT refuse
    (def_hash drops budget keys — same law as replay-skip).
  * the refusal is never retry-laundered (stale_graph is outside both ladders)
    and never invents a death: an unreadable/uncomputable graph.json fails
    OPEN (the guard catches DETECTED staleness).
  * the replacement work runs under the CURRENT definition: the wave boundary
    consumes restart.request (the durable amend marker act_amend already
    writes), reloads, and the efp replay-skip law re-drives the node. Released
    tickets do not leak.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_stale_queued_spawn_byft8.py
"""
import importlib.util, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home-byft8"
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("WF_RUNS_ROOT", None)   # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402  (in-process: efp law + the guard under direct test)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

if HOME.exists():
    shutil.rmtree(HOME)
HOME.mkdir(parents=True); RUNS.mkdir()
SEATS = HOME / "seats"; SEATS.mkdir()
FAKE = str(HERE / "fake")

# ---------------- unit: the guard function itself ----------------
import tempfile
def unit_case(graph_nodes, node, byid):
    d = Path(tempfile.mkdtemp(prefix="byft8-u-"))
    (d / "graph.json").write_text(json.dumps({"name": "u", "nodes": graph_nodes}))
    return wf._stale_spawn_refusal(d, node, byid)

A = {"id": "a", "type": "agent", "goal": "GO a"}
B = {"id": "b", "type": "agent", "goal": "GO b", "after": ["a"]}
byid = {A["id"]: A, B["id"]: B}

r = unit_case([A, B], B, byid)
check("U1 unchanged def -> proceed (None)", r is None, json.dumps(r))
A2 = {**A, "timeout": 999, "max_turns": 77, "shape": "build"}
r = unit_case([A2, B], B, byid)
check("U2 budgets are not work: ancestor timeout/max_turns/shape amend -> proceed",
      r is None, json.dumps(r))
B_ALT = dict(B); B_ALT["goal"] = "GO b REVISED"
r = unit_case([A, B_ALT], B, byid)
check("U3 own goal amended -> typed refusal naming the amend",
      r is not None and r.get("error_class") == "stale_graph" and "amended" in r["error"],
      json.dumps(r))
r = unit_case([A], B, byid)
check("U4 node deleted from the graph -> typed refusal naming the delete",
      r is not None and r.get("error_class") == "stale_graph" and "deleted" in r["error"],
      json.dumps(r))
# ancestor-only move: own def identical, ancestor's def changed
A3 = dict(A); A3["goal"] = "GO a CHANGED"
r = unit_case([A3, B], B, byid)
check("U5 ancestor amended (own def identical) -> refusal (efp covers ancestors)",
      r is not None and r.get("error_class") == "stale_graph", json.dumps(r))
d_bad = Path(tempfile.mkdtemp(prefix="byft8-bad-"))
(d_bad / "graph.json").write_text("{not json")
r = wf._stale_spawn_refusal(d_bad, B, byid)
check("U6 unreadable graph.json -> proceed (fail-open: never invent a death)",
      r is None, json.dumps(r))
check("stale_graph is in the closed ERROR_CLASSES set", "stale_graph" in wf.ERROR_CLASSES)
check("stale_graph is outside both retry ladders",
      "stale_graph" not in wf._RETRYABLE_CLASSES and "stale_graph" not in wf._BOUNDED_RETRY_CLASSES,
      f"{sorted(wf._RETRYABLE_CLASSES)} / {sorted(wf._BOUNDED_RETRY_CLASSES)}")

# ---------------- runner harness (fake CLI + shared global seats) ----------------
def mk(rid, nodes, **meta):
    r = RUNS / rid
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": rid, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30, "max_seats": 1}
    m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def runx(rid, tag, timeout=120):
    """Launch the runner as a subprocess; FAKE_LOG per run so spawn counts are clean."""
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_SEATS_DIR=str(SEATS),
               WF_RUNS_ROOT=str(RUNS),   # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
               FAKE_LOG=str(HOME / f"fake-{tag}.log"),
               FAKE_PROMPT_LOG=str(HOME / f"prompts-{tag}.log"))
    for f in (env["FAKE_LOG"], env["FAKE_PROMPT_LOG"]):
        Path(f).write_text("")
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", rid],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except OSError:
        return []

def wait_for(r, pred, timeout=20.0):
    t_end = time.time() + timeout
    while time.time() < t_end:
        if any(r2.get("node") and pred(r2) for r2 in events(r)):
            return True
        time.sleep(0.05)
    return False

def seats_left():
    return sorted(p.name for p in SEATS.glob("*.json"))

def amend_graph(r, nodes):
    """The durable pair act_amend leaves for a LIVE runner: whole-file atomic
    graph.json replace + restart.request (consumed by consume_markers at the wave
    boundary — same bytes, same names)."""
    tmp = r / "graph.json.tmp"
    tmp.write_text(json.dumps({"name": r.name, "nodes": nodes}))
    os.replace(tmp, r / "graph.json")
    (r / "restart.request").write_text("1")

# ---------------- E1: the incident — amend lands while the spawn queues on a seat ----------------
# The blocker run (separate run dir, SAME global seats dir, cap=1) holds the only
# seat with a live child; the main run's node then queues deterministically.
BLOCKER_GOAL = "GO byft8-blocker SLEEP 5"
OLD = "GO byft8-victim-OLD"
NEW = "GO byft8-victim-NEW"
rB = mk("byft8-blocker", [{"id": "h", "type": "agent", "goal": BLOCKER_GOAL}], timeout=None,
        node_timeout=60)
rM = mk("byft8-victim", [{"id": "b", "type": "agent", "goal": OLD, "timeout": 30}])

out_box = {}
def blocker():
    out_box["b"] = runx("byft8-blocker", "blocker", timeout=90)
t = threading.Thread(target=blocker, daemon=True)
t.start()
# deterministic queue: wait until the blocker child is LIVE (ledger child row), not a
# fixed sleep — the seat is provably occupied before the victim even asks.
t_end = time.time() + 20
while time.time() < t_end:
    led = rB / "spawn-ledger.jsonl"
    if led.exists() and '"role": "child"' in led.read_text():
        break
    time.sleep(0.05)
out_main = {}
def victim():
    out_main["v"] = runx("byft8-victim", "victim", timeout=120)
tv = threading.Thread(target=victim, daemon=True)
tv.start()
queued = wait_for(rM, lambda e: e.get("event") == "seat.wait" and e.get("node") == "b", timeout=25)
check("E1 setup: the victim spawn queued on the contended seat (seat.wait observed)", queued)
# the amend lands DURING the queue window (causally before any acquire: the blocker
# child lives ~5 s and dies only of its own sleep — no kill in the path)
amend_graph(rM, [{"id": "b", "type": "agent", "goal": NEW, "timeout": 30}])
tv.join(110); t.join(110)

evs = events(rM)
fails_stale = [e for e in evs if e.get("event") == "node.failed" and e.get("node") == "b"
               and e.get("error_class") == "stale_graph"]
fin = [e for e in evs if e.get("event") == "node.finished" and e.get("node") == "b"]
check("E1: the queued spawn refused at the launch instant — node.failed stale_graph "
      "(attempts=1, ms=0, zero children)",
      len(fails_stale) >= 1 and fails_stale[0].get("attempts") == 1,
      json.dumps(fails_stale[:1]))
check("E1: NO retry laundering (stale_graph is outside both ladders — no node.retrying for it)",
      not any(e.get("event") == "node.retrying" and e.get("error_class") == "stale_graph" for e in evs))
prompts = (HOME / "prompts-victim.log").read_text() if (HOME / "prompts-victim.log").exists() else ""
fakev = (HOME / "fake-victim.log").read_text() if (HOME / "fake-victim.log").exists() else ""
check("E1: the OLD prompt NEVER launched (no child ever saw the stale goal)",
      OLD not in prompts and OLD not in fakev,
      f"prompts={prompts[:120]!r}")
check("E1: the replacement launched under the CURRENT definition (new goal reached the child)",
      NEW in prompts and NEW in fakev, f"prompts={prompts[:120]!r}")
check("E1: exactly ONE victim child launched — the refusal cost zero spawns",
      fakev.count(NEW) == 1 and fakev.count(OLD) == 0,
      f"count_new={fakev.count(NEW)} count_old={fakev.count(OLD)}")
rec = json.loads((rM / "nodes" / "b.json").read_text())
g2 = json.loads((rM / "graph.json").read_text())
byid2 = {n["id"]: n for n in g2["nodes"]}
check("E1: the wave boundary consumed restart.request and reloaded (graph.reloaded event)",
      any(e.get("event") == "graph.reloaded" for e in evs))
check("E1: restart.request consumed (marker not left dangling)",
      not (rM / "restart.request").exists())
check("E1: replacement work committed done under the CURRENT effective fingerprint",
      rec.get("status") == "done" and rec.get("efp") == wf.efp(byid2, byid2["b"]),
      json.dumps({k: rec.get(k) for k in ("status", "efp")}))
check("E1: event order proves refusal precedes the replacement finish",
      fin and fails_stale and evs.index(fails_stale[0]) < evs.index(fin[0]))
check("E1: run completed (WORKFLOW_DONE)", "WORKFLOW_DONE" in out_main.get("v", ""),
      out_main.get("v", "")[:80])
check("E1: released tickets do not leak (global seats dir empty at the end)",
      seats_left() == [], str(seats_left()))

# ---------------- E2: control — no amend, the queued spawn proceeds unchanged ----------------
rB2 = mk("byft8-ctl-blocker", [{"id": "h", "type": "agent", "goal": "GO byft8-ctl-block SLEEP 3"}],
         node_timeout=60)
rC = mk("byft8-ctl", [{"id": "c", "type": "agent", "goal": "GO byft8-ctl", "timeout": 30}])
tc = threading.Thread(target=lambda: runx("byft8-ctl-blocker", "ctlb", timeout=90), daemon=True)
tc.start()
t_end = time.time() + 20
while time.time() < t_end:
    led = rB2 / "spawn-ledger.jsonl"
    if led.exists() and '"role": "child"' in led.read_text():
        break
    time.sleep(0.05)
out_c = {}
tv2 = threading.Thread(target=lambda: out_c.update(v=runx("byft8-ctl", "ctl", timeout=120)), daemon=True)
tv2.start(); tv2.join(110); tc.join(110)
evc = events(rC)
fakec = (HOME / "fake-ctl.log").read_text() if (HOME / "fake-ctl.log").exists() else ""
recc = json.loads((rC / "nodes" / "c.json").read_text())
check("E2: control — queued spawn launched once, done, NO stale_graph death",
      recc.get("status") == "done" and fakec.count("GO byft8-ctl") == 1
      and not any(e.get("error_class") == "stale_graph" for e in evc),
      json.dumps({"status": recc.get("status"), "count": fakec.count("GO byft8-ctl")}))
check("E2: control tickets do not leak", seats_left() == [], str(seats_left()))

# ---------------- E3: DELETE mid-queue — refused, never launched, run ends over the new graph ----------------
rB3 = mk("byft8-del-blocker", [{"id": "h", "type": "agent", "goal": "GO byft8-del-block SLEEP 4"}],
         node_timeout=60)
rD = mk("byft8-del", [{"id": "d", "type": "agent", "goal": "GO byft8-del-OLD", "timeout": 30}])
td1 = threading.Thread(target=lambda: runx("byft8-del-blocker", "delb", timeout=90), daemon=True)
td1.start()
t_end = time.time() + 20
while time.time() < t_end:
    led = rB3 / "spawn-ledger.jsonl"
    if led.exists() and '"role": "child"' in led.read_text():
        break
    time.sleep(0.05)
out_d = {}
tv3 = threading.Thread(target=lambda: out_d.update(v=runx("byft8-del", "del", timeout=120)), daemon=True)
tv3.start()
wait_for(rD, lambda e: e.get("event") == "seat.wait" and e.get("node") == "d", timeout=25)
Z = {"id": "z", "type": "agent", "goal": "GO byft8-z NEW", "timeout": 30}
amend_graph(rD, [Z])
tv3.join(110); td1.join(110)
evd = events(rD)
faked = (HOME / "fake-del.log").read_text() if (HOME / "fake-del.log").exists() else ""
stale_d = [e for e in evd if e.get("error_class") == "stale_graph"]
recd = json.loads((rD / "nodes" / "d.json").read_text())
check("E3: delete mid-queue -> refusal naming the delete; the old prompt never launched",
      len(stale_d) >= 1 and "deleted" in stale_d[0].get("error", "")
      and "GO byft8-del-OLD" not in faked,
      json.dumps(stale_d[:1]))
check("E3: run completed over the NEW graph (replacement node launched, run done)",
      "WORKFLOW_DONE" in out_d.get("v", "") and faked.count("GO byft8-z NEW") == 1
      and any(e.get("event") == "node.finished" and e.get("node") == "z" for e in evd),
      out_d.get("v", "")[:80])
check("E3: the deleted node's last record is the honest stale_graph fact",
      recd.get("status") == "failed" and recd.get("error_class") == "stale_graph",
      json.dumps({k: recd.get(k) for k in ("status", "error_class")}))
check("E3: delete-path tickets do not leak", seats_left() == [], str(seats_left()))

print("ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
