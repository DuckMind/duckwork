#!/usr/bin/env python3
"""est-2ek.1.595: EXTEND-NOT-KILL (#11) was blind to a oneshot -Q child that block-buffers
stdout. Its spawn log never advances while it works, so `_log_recent` was False at the
wall and a child with live inference and fresh artifacts died at the exact wall. The wall
extension now also accepts the child's own state.db sessions row (title = the --continue
key `<skey>#a<attempt>`) moving within the activity window.

Pinned here (engine-driven with tests/fake_duckwork.py session modes):
  (1) log silent + session row moving past the deadline -> ONE node.extended (basis
      "session"), the child survives the wall and the node commits done;
  (2) log silent + session row frozen -> killed at the wall, error_class timeout, no
      extension (all witnesses frozen);
  (3) _session_recent reads only THIS spawn's row: fresh row True, stale row False, other
      attempt's row False, no db / no key False.
Existing EXTEND-NOT-KILL coverage stays in test_sprint101w2_C1-defaults.py.

Run (stdlib only): python3 tests/test_wall_extend_session_595.py
"""
import json, os, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_595"
RUNS = HOME / "workflows"
if HOME.exists():
    shutil.rmtree(HOME)               # hermetic: never trust leftovers
RUNS.mkdir(parents=True)
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"))
FAKE = str(BUILD / "fake")
sys.path.insert(0, str(BUILD.parent))
import wf  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and bool(cond)

def mk(run_id, nodes):
    r = RUNS / run_id
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
    return r

def drive(run_id, **fake_env):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=dict(env, **fake_env), capture_output=True, text=True, timeout=120)
    return p.stdout.strip(), time.time() - t0

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]

# (1) session row keeps moving past the wall; the spawn log stays at 0 bytes
r = mk("w595-pulse", [{"id": "a", "type": "agent", "goal": "SLOW", "timeout": 3}])
out, _ = drive("w595-pulse", FAKE_MODE="session_pulse", FAKE_SESSION_SEC="4")
ev = events(r)
ext = [e for e in ev if e["event"] == "node.extended"]
rec = json.loads((r / "nodes" / "a.json").read_text())
check("quiet-log child with a moving session row survives the wall and finishes done",
      out.startswith("WORKFLOW_DONE w595-pulse") and rec.get("status") == "done", out + " " + str(rec)[:200])
check("exactly one node.extended, basis session", len(ext) == 1 and ext[0].get("basis") == "session", ext)

# (2) session row exists but is frozen; log silent -> killed at the wall
r = mk("w595-frozen", [{"id": "a", "type": "agent", "goal": "SLOW", "timeout": 2}])
out, elapsed = drive("w595-frozen", FAKE_MODE="session_frozen", FAKE_SESSION_SEC="30")
ev = events(r)
rec = json.loads((r / "nodes" / "a.json").read_text())
check("frozen witnesses -> no extension", not any(e["event"] == "node.extended" for e in ev), ev[-3:])
check("frozen child dies at the wall as timeout", rec.get("error_class") == "timeout", rec)
check("killed near the wall, not wall+50%", elapsed < 8, f"elapsed={elapsed:.1f}s")

# (3) _session_recent unit: only this spawn's own row counts
home = HOME / "unit"
home.mkdir()
db = sqlite3.connect(home / "state.db")
db.execute("create table sessions (id text primary key, title text, model text, billing_provider text, input_tokens int, "
           "output_tokens int, cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, "
           "estimated_cost_usd real, last_activity_at real, last_activity_description text, ended_at real, started_at real)")
now = time.time()
for i, (title, last) in enumerate([("wf:RUN:n:abc12345.zzzzzz#a0", now - 5),      # fresh, attempt 0
                                   ("wf:RUN:n:abc12345.zzzzzz#a1", now - 9999),   # stale, attempt 1
                                   ("wf:RUN:n:other999.zzzzzz#a0", now - 5)]):    # other node's row
    db.execute("insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (str(i), title, "m", None, 0, 0, 0, 0, 0, 0, 0.0, last, "", None, last - 100))
db.commit(); db.close()
run = RUNS / "RUN"
sr = lambda title, h=home: wf._session_recent(run, title, h)
check("fresh own row is recent", sr("wf:RUN:n:abc12345.zzzzzz#a0"))
check("stale own row is not recent", not sr("wf:RUN:n:abc12345.zzzzzz#a1"))
check("another attempt/node's fresh row never proves this spawn", not sr("wf:RUN:n:abc12345.zzzzzz#a2"))
check("no key -> honest absence", not sr(None))
check("no state.db -> honest absence", not sr("wf:RUN:n:abc12345.zzzzzz#a0", HOME / "nowhere"))

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
