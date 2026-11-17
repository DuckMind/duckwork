#!/usr/bin/env python3
"""est-06xk (issue #123) — quorum drain-with-deadline.

With an explicit `quorum`, today's runner SIGKILLs every straggler the MOMENT
quorum is met. That throws away useful in-flight work: a straggler one tool-call
from a real answer dies for nothing. This pin locks the opt-in fix:

  fanout.quorum_drain_s (number >= 0, default 0) — legal ONLY alongside
  `quorum`. At the quorum moment the runner arms ONE drain window of drain_s
  seconds; a straggler that lands its answer inside the window COMMITS (the
  drain cancels nothing that arrives before the deadline), and at the deadline
  the SAME _cancel_stragglers runs (error_class 'cancelled', the a2d7f664
  quorum-moment evidence string — i.e. today's kill, just deferred).
  drain_s = 0 is byte-for-byte today's behavior (immediate cancel); the flip
  to a friendlier default later is one constant in wf.py.

Cases:
  D  validator: -1 / "5" / True rejected as fanout.quorum_drain_s; drain
     without quorum rejected; 0 / 1.5 with quorum accepted; the closed-set
     unknown-key message lists the key.
  A  drain_s absent / 0 regression twin: straggler cancelled promptly.
  B  drain_s > 0, straggler lands BEFORE the deadline -> done, zero cancels.
  C  drain_s > 0, straggler still running AT the deadline -> cancelled with
     the quorum-moment evidence, node still commits done on the winner.
  D2 drain only arms at the quorum moment: quorum=2 of 3 — no early kill.

Run: PYTHONPATH=/opt/duckwork python3 tests/test_quorum_drain_deadline_06xk.py
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home-06xk"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir()
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)

sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"[:300]))
    ok = ok and bool(cond)

# ---------------- D: validator shapes (in-process, no runner) ----------------
def verr(fo):
    return [e for e in wfcommon.validate_graph_errors(
        [{"id": "n", "type": "agent", "goal": "g",
          "fanout": {"items": ["a", "b"], "goal": "t {item}", **fo}}])]

bad = [-1, "5", True, -0.5]
for v in bad:
    errs = verr({"quorum": 1, "quorum_drain_s": v})
    check(f"D validator rejects quorum_drain_s={v!r}",
          any(e["field"] == "fanout.quorum_drain_s" for e in errs), json.dumps(errs)[:200])
errs = verr({"quorum_drain_s": 2})
check("D drain without quorum is rejected",
      any(e["field"] == "fanout.quorum_drain_s" for e in errs), json.dumps(errs)[:200])
for goodv in (0, 0.0, 1, 1.5):
    errs = verr({"quorum": 1, "quorum_drain_s": goodv})
    check(f"D validator accepts quorum_drain_s={goodv!r} with quorum", not errs, json.dumps(errs)[:200])
errs = [e for e in wfcommon.validate_graph_errors(
    [{"id": "n", "type": "agent", "goal": "g",
      "fanout": {"items": ["a"], "goal": "t", "bogus_key": 1}}])]
check("D closed-set message lists quorum_drain_s",
      any("quorum_drain_s" in e["msg"] for e in errs), json.dumps(errs)[:250])

# dialect: a quorum+drain fan-out still refuses export by name (no JS counterpart)
import wf_dialect  # noqa: E402
try:
    wf_dialect.js_export({"name": "t", "nodes": [
        {"id": "n", "type": "agent", "goal": "g",
         "fanout": {"items": ["a", "b"], "goal": "t {item}", "quorum": 1, "quorum_drain_s": 2}}]})
    check("D2 dialect refuses quorum_drain_s export by name", False, "no refusal raised")
except Exception as e:
    check("D2 dialect refuses quorum_drain_s export by name", "quorum" in str(e).lower(), str(e)[:200])

# ---------------- runner-level cases ----------------
def mk(run_id, fo_extra, items, quorum):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    node = {"id": "w", "type": "agent",
            "fanout": {"goal": "{item}", "quorum": quorum, "items": [{"goal": t} for t in items],
                       **fo_extra}}
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": str(HERE / "fake"), "concurrency": 1, "item_concurrency": 3,
         "node_timeout": 40}))
    return r

def run(r):
    t0 = time.time()
    fake_log = HOME / f"{r.name}.log"
    fake_log.write_text("")
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(fake_log))
    p = subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", r.name],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rec = None
    deadline = time.time() + 60
    while time.time() < deadline:
        np_ = r / "nodes" / "w.json"
        if np_.exists():
            try:
                d = json.loads(np_.read_text())
            except Exception:
                d = {}
            if d.get("status") in ("done", "failed"):
                rec = d
                break
        time.sleep(0.05)
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
    assert rec is not None, f"{r.name}: node never committed"
    return rec, time.time() - t0, fake_log

def results_of(rec):
    return (rec.get("output") or {}).get("all_results") or []

# ---- A: drain_s absent -> today's immediate cancel (regression twin) ----
# winner lands at ~0.3s (quorum met), QSLEEP straggler prints NOTHING and
# must be SIGKILLed within the immediate-cancel window, not after 30s.
r = mk("a-zero", {}, ["SLEEP 0.3 quick lane", "QSLEEP 30 slow lane"], 1)
rec, wall, _ = run(r)
rs = results_of(rec)
done = [x for x in rs if x.get("status") == "done"]
cancel = [x for x in rs if x.get("error_class") == "cancelled"]
check("A drain_s=0: node commits done on the winner", rec.get("status") == "done",
      json.dumps({k: rec.get(k) for k in ("status", "error_class", "error")})[:200])
check("A drain_s=0: exactly one done, straggler cancelled",
      len(done) == 1 and len(cancel) == 1,
      json.dumps([x.get("status") for x in rs]))
check("A drain_s=0: cancel is IMMEDIATE (node done well before the 30s straggler)",
      wall < 10, f"wall={wall:.1f}s")
check("A drain_s=0: cancelled straggler carries the quorum-moment evidence",
      any("quorum moment" in (x.get("error") or "") for x in cancel),
      json.dumps([x.get("error") for x in cancel])[:250])

# ---- B: drain_s > 0, straggler lands INSIDE the window -> nothing cancelled ----
# winner ~0.3s -> drain armed to ~3.8s; straggler SLEEP 1.2 lands ~1.4s.
r = mk("b-drain-lands", {"quorum_drain_s": 3.5},
       ["SLEEP 0.3 quick lane", "SLEEP 1.2 drainer lane"], 1)
rec, wall, fake_log = run(r)
rs = results_of(rec)
done = [x for x in rs if x.get("status") == "done"]
cancel = [x for x in rs if x.get("error_class") == "cancelled"]
check("B drain: BOTH items commit done — the drain cancelled nothing that landed first",
      rec.get("status") == "done" and len(done) == 2 and not cancel,
      json.dumps([{k: x.get(k) for k in ("status", "error_class", "error")} for x in rs])[:400])
check("B drain: both children really spawned (no early kill)",
      len([l for l in fake_log.read_text().splitlines() if l.strip()]) == 2,
      fake_log.read_text()[:200])

# ---- C: drain_s > 0, straggler still running AT the deadline -> cancelled ----
# winner ~0.3s -> drain armed to ~2.8s; the 30s silent straggler must die there.
r = mk("c-drain-expires", {"quorum_drain_s": 2.5},
       ["SLEEP 0.3 quick lane", "QSLEEP 30 slow lane"], 1)
rec, wall, fake_log = run(r)
rs = results_of(rec)
done = [x for x in rs if x.get("status") == "done"]
cancel = [x for x in rs if x.get("error_class") == "cancelled"]
check("C deadline: node commits done on the winner", rec.get("status") == "done",
      json.dumps({k: rec.get(k) for k in ("status", "error_class")})[:200])
check("C deadline: the straggler that never landed is cancelled at the deadline",
      len(done) == 1 and len(cancel) == 1,
      json.dumps([x.get("status") for x in rs]))
check("C deadline: cancelled at ~drain_s+winner, NOT instantly at quorum and not at 30s",
      2.0 < wall < 15, f"wall={wall:.1f}s")
check("C deadline: cancel carries the quorum-moment evidence string",
      any("quorum moment" in (x.get("error") or "") for x in cancel),
      json.dumps([x.get("error") for x in cancel])[:250])

# ---- D2: the drain arms at the QUORUM moment only (quorum=2 of 3) ----
# winner1 lands ~0.3s; if the window were (wrongly) armed there, the kill at
# ~3.8s would get the SECOND winner (lands ~5.3s) before it commits -> done==1
# (RED signature). Correct arming waits for quorum==2 (~5.3s): the third
# (30s silent) dies ~8.8s and BOTH winners are done.
r = mk("d2-arm-at-quorum", {"quorum_drain_s": 3.5},
       ["SLEEP 0.3 first lane", "SLEEP 5.0 second lane", "QSLEEP 30 silent lane"], 2)
rec, wall, _ = run(r)
rs = results_of(rec)
done = [x for x in rs if x.get("status") == "done"]
cancel = [x for x in rs if x.get("error_class") == "cancelled"]
check("D2 quorum=2: both winners commit, silent straggler cancelled",
      rec.get("status") == "done" and len(done) == 2 and len(cancel) == 1,
      json.dumps([{k: x.get(k) for k in ("status", "error_class")} for x in rs])[:300])
check("D2 arm waits for quorum (kill at second-winner + drain_s, never before it)",
      wall >= 8.0, f"wall={wall:.1f}s")

shutil.rmtree(HOME, ignore_errors=True)
print(("" if ok else "FAILURES PRESENT ") + "DONE")
sys.exit(0 if ok else 1)
