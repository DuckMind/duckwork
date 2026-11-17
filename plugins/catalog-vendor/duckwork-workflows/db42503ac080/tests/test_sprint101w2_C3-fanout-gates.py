#!/usr/bin/env python3
"""sprint101 C3 — #12 fan-out ergonomics, #14 gate defaults.

#12  fanout.goal optional (node goal + item goal, no 'unused' placeholder); wf1.1 A5:
     without an explicit quorum the fan-out WAITS FOR ALL items (no straggler
     cancellation); the commit threshold is explicit quorum else majority (a lone
     death still commits with partial credit, failed_items reported); explicit
     quorum races — once met, stragglers are cancelled (error_class cancelled) and
     excluded from failure math; the run ends done.
#14  default_option must be one of options (door); hold_timeout + default_option auto-releases
     with gate.auto_released; hold_timeout alone logs gate.expired once and keeps holding until
     a human answer lands.
"""
import json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home-c3"
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake-c3.log"),
           FAKE_PROMPT_LOG=str(BUILD / "prompt-c3.log"))
FAKE = str(BUILD / "fake-c3")
sys.path.insert(0, str(BUILD.parent))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and cond

def mk(run_id, nodes, name="t"):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
    return r

def wf(run_id, timeout=120):
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=timeout)
    return p.stdout.strip()

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]

def answer(r, gid, val):
    g = {n["id"]: n for n in json.loads((r / "graph.json").read_text())["nodes"]}
    (r / "gates" / f"{gid}.json").write_text(json.dumps({"answer": val, "_def": wfcommon.efp(g, g[gid]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))

if HOME.exists(): shutil.rmtree(HOME)
RUNS.mkdir(parents=True)
shutil.copy(BUILD / "fake_duckwork.py", FAKE); os.chmod(FAKE, 0o755)
for f in ("fake-c3.log", "prompt-c3.log"):
    (BUILD / f).write_text("")

# ---- #12a: fanout with NO goal template validates; item prompt = node goal + item goal ----
G = [{"id": "fan", "type": "agent", "goal": "SHARED MISSION",
      "fanout": {"items": [{"id": "p", "goal": "item p work"}, {"id": "q", "goal": "item q work"}]}}]
errs = wfcommon.validate_graph_errors(G)
check("#12 fanout without goal template validates when every item has its own goal", not errs, errs)
r = mk("c3-nogoal", G, "nogoal")
out = wf("c3-nogoal")
check("#12 no-template fan-out runs to done", out.startswith("WORKFLOW_DONE c3-nogoal"), out[-200:])
prompts = (BUILD / "prompt-c3.log").read_text()
check("#12 item prompt carries node goal + item goal, no 'unused' placeholder",
      "SHARED MISSION" in prompts and "item p work" in prompts and "unused" not in prompts.lower(),
      prompts[:300])

# ---- #12b (wf1.1 A5 split): no quorum => WAIT FOR ALL, no cancellation ever; the
# commit threshold (majority) is unchanged; explicit quorum races as before. ----
G = [{"id": "fan", "type": "agent",
      "fanout": {"items": ["fast1", "fast2", "SLEEP 25 slow"], "goal": "{item}"}}]
r = mk("c3-wait-all", G, "wait-all")
t0 = time.time(); out = wf("c3-wait-all"); dt = time.time() - t0
rec = json.loads((r / "nodes/fan.json").read_text())
check("#12b no quorum: the slow item is awaited and commits (node done)",
      rec.get("status") == "done" and dt >= 20, f"{dt:.1f}s {json.dumps(rec)[:200]}")
outp = rec.get("output") or {}
check("#12b no quorum: cancelled_items carries no value (nothing was cancelled)",
      not outp.get("cancelled_items") and outp.get("failed_items") == 0,
      json.dumps(outp)[:200])
check("#12b no quorum: all 3 items committed", len(outp.get("items") or []) == 3,
      json.dumps(outp)[:200])
check("#12b no quorum: run done, no node.failed",
      out.startswith("WORKFLOW_DONE c3-wait-all")
      and not any(e["event"] == "node.failed" and e.get("node") == "fan" for e in events(r)),
      out[-200:])
# (b) no quorum, one item dies: the node still COMMITS with partial credit (majority
# threshold unchanged) and reports the failure — it is NOT cancelled and NOT a quorum failure.
G = [{"id": "fan", "type": "agent",
      "fanout": {"items": ["fast1", "FAILME dead", "fast3"], "goal": "{item}"}}]
r = mk("c3-partial", G, "partial")
out = wf("c3-partial")
rec = json.loads((r / "nodes/fan.json").read_text())
outp = rec.get("output") or {}
check("#12b no quorum + one death: node commits done with failed_items == 1",
      rec.get("status") == "done" and outp.get("failed_items") == 1
      and len(outp.get("items") or []) == 2, json.dumps(rec)[:250])
check("#12b no quorum + one death: cancelled_items carries no value, run done",
      not outp.get("cancelled_items") and out.startswith("WORKFLOW_DONE c3-partial"),
      json.dumps(outp)[:200])
# (c) explicit quorum races: straggler cancelled once met, as today.
G = [{"id": "fan", "type": "agent",
      "fanout": {"items": ["fast1", "fast2", "SLEEP 25 slow"], "goal": "{item}", "quorum": 2}}]
r = mk("c3-quorum", G, "quorum")
t0 = time.time(); out = wf("c3-quorum"); dt = time.time() - t0
rec = json.loads((r / "nodes/fan.json").read_text())
check("#12c explicit quorum=2 (of 3) closes the node done", rec.get("status") == "done", json.dumps(rec)[:200])
check("#12c straggler was cancelled, not awaited", dt < 20, f"{dt:.1f}s")
res = (rec.get("output") or {}).get("all_results") or []
cls = [x.get("error_class") for x in res if x.get("status") != "done"]
check("#12c straggler carries error_class=cancelled", cls == ["cancelled"], cls)
check("#12c cancelled excluded from failure math (failed_items=0, cancelled_items=1)",
      (rec.get("output") or {}).get("failed_items") == 0 and (rec.get("output") or {}).get("cancelled_items") == 1,
      json.dumps(rec.get("output"))[:200])
check("#12c run ends done, not failed", out.startswith("WORKFLOW_DONE c3-quorum"), out[-200:])
check("#12c no node.failed event for the node",
      not any(e["event"] == "node.failed" and e.get("node") == "fan" for e in events(r)))
G[0]["fanout"]["quorum"] = 3
r = mk("c3-quorum-all", G, "quorum-all")
t0 = time.time(); out = wf("c3-quorum-all"); dt = time.time() - t0
check("#12c explicit quorum=ALL still waits for every item", dt >= 20 and out.startswith("WORKFLOW_DONE"), f"{dt:.1f}s {out[-100:]}")

# ---- a2d7f664: the quorum cancel never fires blind. Same quorum shape, two
# stragglers: QSLEEP (silent — log 0 bytes, work dir empty) vs QFLUSH+QSLEEP
# (flushed a valid fenced answer, then kept cooking). The death reason must
# state the output-state snapshot; the flushed one also carries its harvest.
G = [{"id": "fan", "type": "agent",
      "fanout": {"items": ["fast1", "fast2", "QSLEEP 25 silent", "QFLUSH QSLEEP 25 flushed"],
                 "goal": "{item}", "quorum": 2}}]
r = mk("c3-quorum-evidence", G, "quorum-evidence")
t0 = time.time(); out = wf("c3-quorum-evidence"); dt = time.time() - t0
rec = json.loads((r / "nodes/fan.json").read_text())
res = (rec.get("output") or {}).get("all_results") or []
by_err = {x.get("item"): x for x in res if x.get("error_class") == "cancelled"}
check("a2d7f664 both stragglers cancelled, node done (quorum math untouched)",
      rec.get("status") == "done" and len(by_err) == 2 and dt < 25,
      json.dumps({"status": rec.get("status"), "n": len(by_err), "dt": round(dt, 1)}))
silent = by_err.get("QSLEEP 25 silent") or {}
flushed = by_err.get("QFLUSH QSLEEP 25 flushed") or {}
check("a2d7f664 silent straggler reason names 'no output on disk at quorum moment'",
      "no output on disk at quorum moment" in (silent.get("error") or ""),
      json.dumps(silent)[:260])
check("a2d7f664 silent straggler snapshot carries log_bytes=0/work_files=0",
      silent.get("cancel_evidence") == {"log_bytes": 0, "work_files": 0},
      json.dumps(silent.get("cancel_evidence")))
check("a2d7f664 flushed straggler reason names 'had output at quorum moment' with measurements",
      "had output at quorum moment" in (flushed.get("error") or "")
      and (flushed.get("cancel_evidence") or {}).get("log_bytes", 0) > 0,
      json.dumps(flushed)[:260])
check("a2d7f664 harvest-at-cancel: flushed straggler keeps its fenced answer as harvest output",
      isinstance((flushed.get("output") or {}).get("result"), str)
      and (flushed.get("harvest") or {}).get("declared_status") in (None, "ok", "done"),
      json.dumps({"out": flushed.get("output"), "hv": flushed.get("harvest")})[:260])
check("a2d7f664 cancelled stays excluded from failure math (failed_items=0, cancelled_items=2)",
      (rec.get("output") or {}).get("failed_items") == 0
      and (rec.get("output") or {}).get("cancelled_items") == 2,
      json.dumps(rec.get("output"))[:200])
check("a2d7f664 harvest-at-cancel event logged",
      any(e["event"] == "item.harvested_at_cancel" and e.get("node") == "fan" for e in events(r)),
      json.dumps([e["event"] for e in events(r)][-8:]))

# ---- #14a: door validation ----
bad = {"nodes": [{"id": "g", "type": "gate", "question": "q", "options": ["a", "b"],
                  "default_option": "zzz", "hold_timeout": 5}]}
errs = wfcommon.validate_graph_errors(bad["nodes"])
check("#14 default_option not in options is rejected with the field path",
      any(e.get("field") == "default_option" for e in errs), errs)
bad2 = {"nodes": [{"id": "g", "type": "gate", "question": "q", "options": ["a"], "hold_timeout": -1}]}
errs = wfcommon.validate_graph_errors(bad2["nodes"])
check("#14 hold_timeout must be positive", any(e.get("field") == "hold_timeout" for e in errs), errs)
good = {"nodes": [{"id": "g", "type": "gate", "question": "q", "options": ["a", "b"],
                   "default_option": "b", "hold_timeout": 2}]}
check("#14 valid gate defaults pass the door", not wfcommon.validate_graph_errors(good["nodes"]))

# ---- #14b: auto-release with default_option ----
G = [{"id": "a", "type": "agent", "goal": "ok"},
     {"id": "g", "type": "gate", "after": ["a"], "question": "ship?", "options": ["ship", "hold"],
      "default_option": "ship", "hold_timeout": 2},
     {"id": "b", "type": "agent", "after": ["g"], "goal": "after gate"}]
r = mk("c3-auto", G, "auto")
t0 = time.time(); out = wf("c3-auto"); dt = time.time() - t0
ev = events(r)
check("#14 gate auto-releases after hold_timeout and the run finishes",
      out.endswith("WORKFLOW_DONE c3-auto") and "WORKFLOW_HELD c3-auto g" in out and 2 <= dt < 30,
      f"{dt:.1f}s {out[-120:]}")
ar = [e for e in ev if e["event"] == "gate.auto_released"]
check("#14 gate.auto_released {node, option, held_s} logged once",
      len(ar) == 1 and ar[0].get("option") == "ship" and isinstance(ar[0].get("held_s"), int), ar)
check("#14 gate.held was emitted first (the desktop still sees the question)",
      any(e["event"] == "gate.held" and e["node"] == "g" for e in ev))
grec = json.loads((r / "nodes/g.json").read_text())
check("#14 gate record = the default option, machine-stamped",
      grec.get("status") == "done" and (grec.get("output") or {}).get("answer") == "ship"
      and (grec.get("output") or {}).get("_machine") == "auto_release", json.dumps(grec)[:200])
check("#14 downstream ran off the auto-release", (r / "nodes/b.json").exists())

# ---- #14c: expire without default_option: loud once, keeps holding, human answer wins ----
G = [{"id": "g", "type": "gate", "question": "either?", "options": ["x", "y"], "hold_timeout": 2},
     {"id": "b", "type": "agent", "after": ["g"], "goal": "after gate"}]
r = mk("c3-expire", G, "expire")
p = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "c3-expire"],
                     env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(5)
ev = events(r)
check("#14 runner still parked after expiry (not exited, not failed)", p.poll() is None, p.poll())
exp = [e for e in ev if e["event"] == "gate.expired"]
check("#14 gate.expired logged exactly once", len(exp) == 1 and exp[0].get("held_s", 0) >= 2, exp)
check("#14 no auto-release without default_option", not any(e["event"] == "gate.auto_released" for e in ev))
st = wfcommon.run_state(r)
check("#14 read model reads held while parked", st.get("status") == "held", st.get("status"))
answer(r, "g", "y")
out, _ = p.communicate(timeout=60)
check("#14 human answer after expiry releases the parked gate; run done",
      out.strip().endswith("WORKFLOW_DONE c3-expire") and (r / "nodes/b.json").exists(), out.strip()[-200:])

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
