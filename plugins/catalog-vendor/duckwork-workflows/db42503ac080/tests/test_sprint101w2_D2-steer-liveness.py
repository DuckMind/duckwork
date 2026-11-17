#!/usr/bin/env python3
"""Sprint-101 w2 lane D2 — #17 steer honesty + #18 child liveness.

 1. steer queue->bake->consume produces steer.queued / steer.baked /
    steer.consumed in events.jsonl and status shows {queued, baked, consumed}.
 2. early_death fires: a fake child that writes NOTHING to stdout within
    first_message_s (small run-level meta value) is killed, error_class
    'early_death'; it is NOT retried.
 3. A child that prints within the window is NOT killed (FAKE_MODE=early).
 4. A verified live node carries idle_s in status metrics.
 5. The steer response says exactly what will happen (baked into the next
    spawn of <node> / live pull with no delivery guarantee), no hedging.

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_sprint101w2_D2-steer-liveness.py
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
HOME = ROOT / "tests" / "home-d2"
RUNS = HOME / "workflows"
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

_spec = importlib.util.spec_from_file_location("hw_d2", ROOT / "__init__.py")
door = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(door)

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

def mk(run_id, meta_extra=None):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(
        {"name": run_id, "nodes": [{"id": "w", "type": "agent", "goal": "work"}]}))
    m = {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 60}
    m.update(meta_extra or {})
    (r / "run.json").write_text(json.dumps(m))
    return r

def launch(r, env_extra=None):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), **(env_extra or {}))
    return subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_node(r, nid="w", timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = r / "nodes" / f"{nid}.json"
        if p.exists():
            try:
                d = json.loads(p.read_text())
            except Exception:
                d = {}
            if d.get("status") in ("done", "failed"):
                return d
        time.sleep(0.1)
    raise AssertionError(f"node {nid} never committed within {timeout}s")

def events(r):
    p = r / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

# ---- 1: steer queue -> bake -> consume produces the three events -------------
r = mk("d2-events")
ans = door.act_steer({"run_id": r.name, "node": "w", "text": "nudge one"})
check("steer accepted (pending node, dead runner)", ans.get("ok") is True, json.dumps(ans))
evs = events(r)
check("steer.queued event logged at the door",
      any(e.get("event") == "steer.queued" and e.get("node") == "w" for e in evs),
      json.dumps(evs)[:200])
proc = launch(r, {"FAKE_MODE": "poll_steer"})
proc.wait(timeout=120)
rec = wait_node(r)
evs = events(r)
check("steer.baked event logged at spawn (node, spawn_no, n_lines)",
      any(e.get("event") == "steer.baked" and e.get("node") == "w"
          and e.get("spawn_no") == 0 and e.get("n_lines") == 1 for e in evs),
      json.dumps(evs)[:300])
check("steer.consumed event logged where the inbox action drains",
      any(e.get("event") == "steer.consumed" and e.get("node") == "w"
          and e.get("pulled") == 1 for e in evs),
      json.dumps(evs)[:300])
check("fake child actually pulled the line",
      (rec.get("output") or {}).get("pulled") == ["nudge one"], json.dumps(rec)[:200])
st = door.act_status({"run_id": r.name})
sm = (st.get("nodes", {}).get("w") or {}).get("steer")
check("status per-node steer shows {queued, baked, consumed}",
      sm == {"queued": 1, "baked": 1, "consumed": 1}, json.dumps(sm))

# ---- 2: early_death fires on a silent child -----------------------------------
r2 = mk("d2-early-death", {"first_message_s": 2, "node_timeout": 30})
t0 = time.time()
proc2 = launch(r2, {"FAKE_MODE": "hang", "FAKE_HANG_SEC": "30"})
proc2.wait(timeout=90)
rec2 = wait_node(r2, timeout=30)
killed_in = time.time() - t0
check("silent child killed as early_death within the window",
      rec2.get("error_class") == "early_death" and killed_in < 15,
      json.dumps({k: rec2.get(k) for k in ("error_class", "error")})[:250])
check("early_death child never ran to its hang wall", killed_in < 20, f"{killed_in:.1f}s")
check("node.failed event carries error_class early_death",
      any(e.get("event") == "node.failed" and e.get("error_class") == "early_death"
          for e in events(r2)), json.dumps(events(r2))[:300])
check("early_death is not transient-retried (one spawn)",
      len((HOME / "fake.log").read_text().splitlines()) == 0 or
      (r2 / "steer").exists() and len(list((r2 / "steer").glob("w.a*.jsonl"))) == 1,
      json.dumps([p.name for p in (r2 / "steer").glob("w.a*.jsonl")]))

# ---- 3: a child that prints within the window is NOT killed -------------------
r3 = mk("d2-early-alive", {"first_message_s": 3, "node_timeout": 60})
proc3 = launch(r3, {"FAKE_MODE": "early", "FAKE_EARLY_SLEEP": "5"})
proc3.wait(timeout=120)
rec3 = wait_node(r3, timeout=30)
check("child that printed within first_message_s is NOT killed",
      rec3.get("status") == "done", json.dumps(rec3)[:200])

# ---- 4: idle_s present for a verified live node -------------------------------
r4 = mk("d2-idle", {"first_message_s": 0})
proc4 = launch(r4, {"FAKE_MODE": "early", "FAKE_EARLY_SLEEP": "8", "FAKE_API_CALLS": "1"})
live_metrics = None
deadline = time.time() + 20
while time.time() < deadline:
    rec4 = jload = None
    p = r4 / "nodes" / "w.json"
    if p.exists():
        try:
            rec4 = json.loads(p.read_text())
        except Exception:
            rec4 = None
        if rec4 and rec4.get("status") == "running" and rec4.get("pid"):
            st4 = door.act_status({"run_id": r4.name})
            live_metrics = (st4.get("nodes", {}).get("w") or {}).get("metrics")
            if live_metrics and live_metrics.get("live"):
                break
    time.sleep(0.15)
check("live node status carries idle_s",
      bool(live_metrics) and "idle_s" in (live_metrics or {}),
      json.dumps(live_metrics)[:200])
try:
    proc4.wait(timeout=120)
except Exception:
    proc4.kill(); proc4.wait()

# ---- 5: the steer response says exactly what will happen ----------------------
NODE = lambda i, **kw: dict({"id": i, "type": "agent", "goal": "x"}, **kw)
r5 = RUNS / "d2-wording"
shutil.rmtree(r5, ignore_errors=True)
(r5 / "nodes").mkdir(parents=True); (r5 / "gates").mkdir()
(r5 / "graph.json").write_text(json.dumps(
    {"name": "d2-wording", "nodes": [NODE("a"), NODE("b", after=["a"])]}))
(r5 / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "node_timeout": 60}))

with patch.object(door, "runner_alive", lambda *a, **k: True):
    ans = door.act_steer({"run_id": r5.name, "node": "b", "text": "x"})
check("pending-node delivery names the exact mechanism: baked into the next spawn of <node>",
      ans.get("ok") is True and f"baked into the next spawn of b" in ans.get("delivery", ""),
      json.dumps(ans))
d = ans.get("delivery", "").lower()
check("delivery uses no hedging words",
      not any(w in d for w in ("may ", "might ", "could ", "possibly", "otherwise")),
      ans.get("delivery", ""))

node_a = NODE("a")
fake_spawn = {"pid": os.getpid(), "skey": f"wf:{r5.name}:a:live", "attempt": 0,
              "efp": wfcommon.efp({"a": node_a}, node_a)}
with patch.object(door, "runner_alive", lambda *a, **k: True), \
     patch.object(door._common, "runner_alive", lambda *a, **k: True), \
     patch.object(door._common, "_active_spawns", lambda r_, n_, b_: [dict(fake_spawn)]):
    ans = door.act_steer({"run_id": r5.name, "node": "a", "text": "mid"})
check("live-child delivery: live pull + no delivery guarantee + next-spawn fallback",
      ans.get("ok") is True and "running child will pull" in ans.get("delivery", "")
      and "no delivery guarantee" in ans.get("delivery", "")
      and "next spawn of a" in ans.get("delivery", ""),
      json.dumps(ans))

print("\n" + ("ALL PASS" if ok else "FAILURES PRESENT"))
sys.exit(0 if ok else 1)
