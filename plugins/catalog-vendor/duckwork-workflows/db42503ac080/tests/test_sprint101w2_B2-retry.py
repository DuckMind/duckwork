#!/usr/bin/env python3
"""Sprint101 Lane B2-retry contracts (#5 bounded auto-retry, #4 harvest-on-death).

#5  permfail (provider_400) NEVER retried; a retryable class (transport) whose
    dead attempt made TOOL PROGRESS (state.db tool_call_count > 0) gets exactly
    ONE machine-resume re-drive; the re-drive's prompt file carries the resume
    preamble ('Do not redo finished work'); node.retry logged with reason.
#4  fake exits 1 AFTER printing a valid fenced json answer ⇒ the node commits
    status='partial' (never retried — exactly 1 spawn), downstream node runs,
    the run closes done; a child-declared terminal status ('BLOCKED') is
    honored verbatim in the record (harvest.declared_status + output).

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_sprint101w2_B2-retry.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home10"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
               **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def spawns_of(run_id):
    """Spawns for a run = child log files the runner wrote (logs/<node>.a<N>.log);
    the fake's first-prompt-line log cannot see a run id behind a resume preamble."""
    return len(list((RUNS / run_id / "logs").glob("*.log")))

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

# ---- #5a: permfail (provider_400) is NEVER retried, even with tool progress ----
r = mk("b2-permfail", [{"id": "a", "type": "agent", "goal": "PERMFAIL b2-permfail",
                        "schema": SCHEMA}])
out = wf("b2-permfail", {"FAKE_MODE": "provider400", "FAKE_API_CALLS": "1"})
rec = rec_of(r, "a")
check("#5 permfail never retried (exactly 1 spawn)", spawns_of("b2-permfail") == 1,
      f"spawns={spawns_of('b2-permfail')} out={out}")
check("#5 permfail stays failed, class provider_400",
      rec["status"] == "failed" and rec.get("error_class") == "provider_400", str(rec.get("error_class")))
check("#5 permfail emits no node.retry event",
      not any(e.get("event") == "node.retry" for e in events(r)))

# ---- #5b: transport death WITH tool progress -> exactly ONE resume re-drive ----
r = mk("b2-resume", [{"id": "a", "type": "agent", "goal": "RESUME b2-resume", "schema": SCHEMA}])
prompt_log = HOME / "prompt_resume.log"
out = wf("b2-resume", {"FAKE_MODE": "retry_progress", "FAKE_ATTEMPT_DIR": str(HOME / "att_resume"),
                       "FAKE_PROMPT_LOG": str(prompt_log)})
rec = rec_of(r, "a")
check("#5 tool-progress transport recovers to done", rec["status"] == "done"
      and (rec.get("output") or {}).get("result") == "resumed", str(rec)[:300])
check("#5 retried EXACTLY once (2 spawns, never a loop)", spawns_of("b2-resume") == 2,
      f"spawns={spawns_of('b2-resume')}")
pl = prompt_log.read_text() if prompt_log.exists() else ""
parts = pl.split("=====PROMPT=====")
check("#5 re-drive prompt carries the resume preamble",
      "Do not redo finished work; continue from the state above." in pl
      and "Prior attempt died: error_class=transport" in pl)
check("#5 FIRST attempt prompt has NO preamble", parts[1].strip()[:20] != "" and
      "machine preamble" not in parts[1], parts[1][:80] if len(parts) > 1 else "no prompts")
check("#5 attempts_log marks the resume attempt",
      any(a.get("resume") for a in rec.get("attempts_log") or []), str(rec.get("attempts_log")))
check("#5 node.retry event logged with reason",
      any(e.get("event") == "node.retry" and "bounded auto-retry" in (e.get("reason") or "")
          for e in events(r)))
check("#5 attempts counter reflects the re-drive", rec.get("attempts", 0) >= 2, str(rec.get("attempts")))

# ---- #4a: child dies rc!=0 AFTER a valid fenced answer -> partial, downstream runs ----
# e68544a37be37657 (law-tightening): the after-edge release law is now FAIL-CLOSED —
# a plain after-edge is NOT satisfied by a harvest-on-death partial. The harvest still
# flows when the descendant OPTS IN with after_partial:true, which is what #4's
# downstream-runs-off-the-partial law now pins. The block itself is locked by
# tests/test_partial_block_87.py.
r = mk("b2-harvest", [{"id": "a", "type": "agent", "goal": "DIETEST b2-harvest", "schema": SCHEMA},
                      {"id": "b", "type": "agent", "goal": "DOWNSTREAM of a", "after": ["a"],
                       "after_partial": True, "schema": SCHEMA}])
out = wf("b2-harvest", {"FAKE_MODE": "die_after_json"})
rec = rec_of(r, "a")
check("#4 rc!=0 death with valid fenced answer commits partial",
      rec["status"] == "partial" and (rec.get("output") or {}).get("result") == "harvested",
      str(rec)[:300])
check("#4 partial keeps the death cause as error_class", bool(rec.get("error_class")), str(rec))
check("#4 harvested node is NEVER retried (1 spawn for a)",
      spawns_of("b2-harvest") == 2, f"total spawns={spawns_of('b2-harvest')} (a=1, b=1)")
check("#4 downstream node runs off the partial", rec_of(r, "b")["status"] == "done",
      str(rec_of(r, "b"))[:200])
check("#4 run closes done with the harvest", out.startswith("WORKFLOW_DONE b2-harvest"), out[-200:])

# ---- #4b: child-declared terminal status honored verbatim ----
r = mk("b2-blocked", [{"id": "a", "type": "agent", "goal": "DIETEST b2-blocked",
                       "schema": {"type": "object",
                                  "properties": {"status": {"type": "string"}, "result": {"type": "string"}},
                                  "required": ["result"]}}])
out = wf("b2-blocked", {"FAKE_MODE": "die_after_json_blocked"})
rec = rec_of(r, "a")
check("#4 declared terminal status honored verbatim",
      rec["status"] == "partial" and (rec.get("output") or {}).get("status") == "BLOCKED"
      and (rec.get("harvest") or {}).get("declared_status") == "BLOCKED", str(rec)[:300])

# ---- #4c: partial is never retried even when class IS retryable (timeout shape) ----
# (die_after_json rc=1 is the retryable-shaped death: harvested BEFORE the retry decision)
check("#4 harvested partial not retried: no node.retry for it",
      not any(e.get("event") == "node.retry" for e in events(RUNS / "b2-harvest")))

# ---- read-model: wfcommon agrees the opt-in satisfies on partial ----
st = wfcommon.run_state(RUNS / "b2-harvest")
check("#4 read model: partial node counts done + run done; opt-in satisfies, plain edge strict",
      st and st["nodes"]["a"]["status"] == "partial" and st["status"] == "done"
      and wfcommon.dep_satisfied({"a": "partial"}, "a", allow_partial=True)
      and not wfcommon.dep_satisfied({"a": "partial"}, "a"))

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
