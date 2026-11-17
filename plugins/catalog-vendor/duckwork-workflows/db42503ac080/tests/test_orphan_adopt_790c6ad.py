#!/usr/bin/env python3
"""790c6ad — live-orphan adoption on a respawned runner.

Forensic shape (waveA3): runner SIGKILLed mid-fanout while children (spawned
start_new_session=True) stay alive; the respawned runner re-logged every
item.started and re-spawned all items from zero, burning tokens on live work.
The fix: the fanout spawn() consults wfcommon.active_child (status=running
record + efp match + pid alive + skey-in-cmdline — the PID-reuse guard) and
ADOPTs a verified live orphan: no item.started, no Popen, deadline re-armed
from the record's original started, single harvest from the existing spawn
log, registered in meta['_procs'] so _stop_watcher's killpg still reaches it.

Repro implemented here with a stub duckwork_bin (stub_orphan_child.py):
  A) kill -9 the runner mid-fanout, respawn: assert NO duplicate item.started
     for live children, item.adopted ×N, each item harvested exactly once
     (stub spawn count stays at N), node commits done with all answers,
     per-item records retire to status=adopted.
  B) stop-path regression: respawn, let adoption happen, then stop.request:
     adopted pids actually die (killpg via the synthetic _procs handle).
  C) unit: active_child verifies a live record, returns None for a dead pid,
     and None for a live pid whose argv lacks the skey title (imposter).
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import json, os, shutil, signal, subprocess, sys, tempfile, threading, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # the lane/plugin dir
sys.path.insert(0, str(ROOT))
import wfcommon                                       # noqa: E402

HOME = Path(tempfile.mkdtemp(prefix="wf-790c6ad-"))
RUNS = HOME / "workflows"
STUB = ROOT / "tests" / "stub_orphan_child.py"
STUB.chmod(0o755)
ok = True
_child_pids = []          # every child pid the stubs ever printed, for teardown
_pids_lock = threading.Lock()

def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and bool(cond)

def env_for(fake_log):
    e = env0 = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(fake_log),
                    PYTHONDONTWRITEBYTECODE="1")
    # the generic fake_duckwork.py keys off FAKE_MODE/FAKE_* — an inherited value
    # would hijack our stub (which ignores them, but the runner env is shared):
    for k in ("FAKE_MODE", "FAKE_ATTEMPT_DIR", "FAKE_PID_LOG", "FAKE_ARGV_LOG",
              "FAKE_PROMPT_LOG", "FAKE_API_CALLS", "FAKE_POLL_SLEEP", "FAKE_EARLY_SLEEP"):
        e.pop(k, None)
    e["STUB_SLEEP"] = "12"          # children outlive the kill+respawn window with margin
    return e

def mk(run_id, items, node_timeout=30):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    graph = {"name": run_id, "nodes": [
        {"id": "fan", "type": "agent",
         "fanout": {"items": items, "goal": "do the thing for {item}"}}]}
    (r / "graph.json").write_text(json.dumps(graph))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": str(STUB),
                                            "node_timeout": node_timeout}))
    return r

def start_runner(run_id, fake_log):
    p = subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                         env=env_for(fake_log), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    return p

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []

def wait_for(pred, timeout, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.05)
    return False

def read_children(r, n):
    """All per-item spawn records with a live pid, once every item is RUNNING."""
    recs = {}
    for i in range(n):
        rec = wfcommon.jload(r / "nodes" / f"fan.{i}.json")
        if not isinstance(rec, dict) or rec.get("status") != "running":
            return None
        pid = rec.get("pid")
        if not isinstance(pid, int) or not Path(f"/proc/{pid}").exists():
            return None
        recs[i] = rec
    return recs if len(recs) == n else None

def kill_proc(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

# ---------- A) kill runner mid-fanout → respawn adopts, harvest-once ----------

run_id = "t-adopt-1"
items = ["alpha", "beta", "gamma", "delta"]
fake_log = HOME / f"{run_id}.fake.log"
r = mk(run_id, items)
runner1 = start_runner(run_id, fake_log)
check("runner1 reaches all-4 children live",
      wait_for(lambda: read_children(r, 4) is not None, 45, "children live"),
      str(events(r)[-3:]))
recs = read_children(r, 4) or {}
_child = [recs.get(i, {}).get("pid") for i in range(4)]
started1 = len([e for e in events(r) if e.get("event") == "item.started"])
check("baseline: 4 item.started before the kill", started1 == 4, str(started1))
runner_pid = int((r / "wf.pid").read_text())
runner1.kill()          # belt: the real death below is the kill -9
kill_proc(runner_pid)
runner1.wait(timeout=20)   # reap our own child: zombie != gone for /proc purposes
check("runner1 dies", not Path(f"/proc/{runner_pid}").exists())
check("children SURVIVE the runner kill -9 (start_new_session law)",
      all(pid and Path(f"/proc/{pid}").exists() for pid in _child), str(_child))

runner2 = start_runner(run_id, fake_log)     # the respawn: adoption must kick in
out2 = runner2.communicate(timeout=90)[0]
ev = events(r)
started2 = [e for e in ev if e.get("event") == "item.started"]
adopted = [e for e in ev if e.get("event") == "item.adopted"]
fin = [e for e in ev if e.get("event") == "item.finished"]
check("respawn run DONE", "WORKFLOW_DONE" in out2, out2.strip()[-300:])
check("NO duplicate item.started for live children (still exactly 4)",
      len(started2) == 4, f"got {len(started2)}")
check("all 4 items adopted (item.adopted ×4 with pid+skey)",
      len(adopted) == 4 and all(e.get("pid") and e.get("skey") for e in adopted), str(adopted))
check("adopted deadlines re-armed from the record's original started",
      all(e.get("started") == recs[e["index"]]["started"] for e in adopted
          if e.get("index") in recs), str(adopted))
check("each item harvested exactly once (4 item.finished, all done)",
      len(fin) == 4 and all(e.get("status") == "done" for e in fin), str(fin))
check("single harvest proof: the stub was invoked exactly 4 times in TOTAL",
      fake_log.exists() and len(fake_log.read_text().splitlines()) == 4,
      str(fake_log.read_text().splitlines() if fake_log.exists() else "<no fake log>"))
node = wfcommon.jload(r / "nodes" / "fan.json") or {}
merged = ((node.get("output") or {}).get("items")) or []
check("node fan committed done with all 4 adopted answers",
      node.get("status") == "done" and len(merged) == 4
      and all(any(("done:do the thing for " + it) in (x.get("result") or "") for x in merged)
              for it in items),
      json.dumps(node)[:300])
retired = [wfcommon.jload(r / "nodes" / f"fan.{i}.json") or {} for i in range(4)]
check("per-item records retired to status=adopted (no re-adoption window)",
      all(x.get("status") == "adopted" for x in retired), str([x.get("status") for x in retired]))
check("adopted children finished on their own (exited, runner never killed them)",
      all(not Path(f"/proc/{pid}").exists() for pid in _child if pid))
# adopted children were NOT killed by the runner — they wrote their own answers:
check("answers carry the children's own stdout (harvested from the live spawn log)",
      all((x.get("result") or "").startswith("done:") for x in merged), json.dumps(merged)[:300])

# ---------- B) stop-path: adopted pids must actually die ----------

run_id2 = "t-adopt-stop"
fake_log2 = HOME / f"{run_id2}.fake.log"
r2 = mk(run_id2, items, node_timeout=30)
runnerA = start_runner(run_id2, fake_log2)
check("stop-run: runnerA reaches all-4 children live",
      wait_for(lambda: read_children(r2, 4) is not None, 45, "children live"))
recs2 = read_children(r2, 4) or {}
_child2 = [recs2.get(i, {}).get("pid") for i in range(4)]
pidA = int((r2 / "wf.pid").read_text())
runnerA.kill(); kill_proc(pidA)
runnerA.wait(timeout=20)   # reap promptly: a zombie /proc entry stalls the respawn
check("stop-run: children survive runnerA death",
      all(pid and Path(f"/proc/{pid}").exists() for pid in _child2), str(_child2))
runnerB = start_runner(run_id2, fake_log2)
check("stop-run: respawn adopts the live children first",
      wait_for(lambda: len([e for e in events(r2) if e.get("event") == "item.adopted"]) == 4,
               30, "adoptions"), str(events(r2)[-3:]))
(r2 / "stop.request").write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"))
outB = runnerB.communicate(timeout=90)[0]
check("stop-run ends STOPPED", "WORKFLOW_STOPPED" in outB, outB.strip()[-300:])
check("stop-path REGRESSION GATE: killpg reaches adopted pids — all dead",
      wait_for(lambda: all(pid and not Path(f"/proc/{pid}").exists() for pid in _child2),
               15, "adopted pids reaped"),
      str([p for p in _child2 if Path(f"/proc/{p}").exists() if p]))
fin2 = [e for e in events(r2) if e.get("event") == "item.finished"]
check("stop-run: stopped items classified cancelled, no re-spawns",
      len([e for e in events(r2) if e.get("event") == "item.started"]) == 4
      and all(e.get("error_class") == "cancelled" for e in fin2), str(fin2)[:300])

# ---------- C) unit: active_child verification law ----------

from pathlib import Path as _P
graph = {"nodes": [{"id": "u", "type": "agent", "fanout": {"items": ["x"], "goal": "g"}}]}
byid = {n["id"]: n for n in graph["nodes"]}
node_u = byid["u"]
ru = RUNS / "t-unit"
(ru / "nodes").mkdir(parents=True)
(ru / "graph.json").write_text(json.dumps(graph))

# live child whose argv literally carries the skey title → verified
skey = "wf:t-unit:u:0:deadbeef.abc123"
token = f"{skey}#a0"
live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", token],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
with _pids_lock: _child_pids.append(live.pid)
def put_rec(pid, skey_, attempt=0):
    rec = {"status": "running", "pid": pid, "skey": skey_, "attempt": attempt,
           "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "log_path": str(ru / "logs" / "u.0.a0.log"),
           "spawn_cmd": [sys.executable, "chat"], "efp": wfcommon.efp(byid, node_u), "fp_rule_version": wfcommon.FP_RULE_VERSION}
    (ru / "nodes" / "u.0.json").write_text(json.dumps(rec))

put_rec(live.pid, skey)
got = wfcommon.active_child(ru, node_u, byid, 0)
check("active_child verifies a live orphan (pid alive + skey title in argv)",
      isinstance(got, dict) and got.get("pid") == live.pid and got.get("skey") == token, str(got))

put_rec(999999, skey)  # pid that cannot be ours — dead / never existed
check("active_child returns None for a dead pid", wfcommon.active_child(ru, node_u, byid, 0) is None)

put_rec(os.getpid(), "wf:t-unit:u:0:imposter.dead00")  # alive pid, skey NOT in our argv
check("PID-REUSE GUARD: live pid whose argv lacks the skey title is NEVER adopted",
      wfcommon.active_child(ru, node_u, byid, 0) is None)

kill_proc(live.pid)

# ---------- teardown ----------
with _pids_lock:
    for p in _child_pids:
        kill_proc(p)
try: shutil.rmtree(HOME, ignore_errors=True)
except Exception: pass

print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
