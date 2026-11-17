#!/usr/bin/env python3
"""est-jam8 — the config death is typed config_input on EVERY read path.

Deep review of PR #162 (committee wf162a, 2026-10-03T11:41Z) reproduced two
holes that the original est-tmuu pin could not see, because the pin's capture
never carried a schema-valid fence and never went through adoption:

  FENCED DEATH (wf.py rc!=0 path). A child that dies rc!=0 inside the fast
  window with the Unknown-provider marker AND a schema-valid fenced block on
  stdout used to commit `partial` / `error_class=unknown`: harvest-on-death
  (#4) returned first and the config classifier below it never ran. The
  deterministic input error was back in the unknown bucket — precisely the
  class of outcome est-tmuu exists to forbid ("a config typo must never
  surface as unknown").

  ADOPTED DEATH (wf.py adoption path). A verified live orphan that outlived
  its spawner and died printing the config diagnostic committed `done`:
  harvest_once coerced the diagnostic PROSE into {result: ...} and, with
  rc unobservable, nothing challenged the fake success — a config death
  laundered into a passing node (also reproducible on base e18eca5cf: the
  adoption coercion hole predates this PR; est-jam8 owns its narrow repair).

The law this pin enforces: config classification is PATH-INVARIANT. Before
harvest, before the done-coercion, on both the rc!=0 and the adopted read path
— the same capture inside the fast window lands `failed` with typed
`error_class=config_input` and burns no respawn budget, no matter how the
runner came to read it. Evidence (raw capture + harvest) stays on the record.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME PYTHONPATH=/opt/duckwork \
     /opt/duckwork/.venv/bin/python3 tests/test_config_input_paths_jam8.py
"""
import json, os, shutil, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home-jam8"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ.pop("WF_RUNS_ROOT", None)   # hermetic: runs land under HOME/workflows
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir(); (r / "logs").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf_run(run_id, extra_env=None, timeout=120):
    base = {k: v for k, v in os.environ.items() if k != "WF_RUNS_ROOT"}
    env = dict(base, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
               **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]

CFG_MARK = "Unknown provider"

# ---------- T8 FENCED rc!=0 death: config_input, not harvest-laundered partial ----------
# The committee's spawn-fenced shape: marker + a schema-valid fence in ONE fast
# rc=2 death. Pre-fix this committed partial/unknown (harvest ran first).
shutil.rmtree(HOME, ignore_errors=True); HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")
SCHEMA = {"type": "object", "required": ["diagnostic"],
          "properties": {"diagnostic": {"type": "string"}}}
r = mk("jam8-fenced", [{"id": "a", "type": "agent", "goal": "cfg JAM8-FENCED",
                        "model": "turbo-a", "provider": "nope", "schema": SCHEMA}],
       retry_backoff=[0.05, 0.1])
out = wf_run("jam8-fenced", {"FAKE_MODE": "cfgtypos", "FAKE_CFG_FENCED": "1",
                             "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
n_spawns = (HOME / "fake.log").read_text().count("JAM8-FENCED")
check("T8 fenced config death: failed/config_input (never partial/unknown)",
      rec.get("status") == "failed" and rec.get("error_class") == "config_input",
      json.dumps({k: rec.get(k) for k in ("status", "error_class")}))
check("T8b ONE spawn, budget untouched (no node.retrying)",
      n_spawns == 1 and "node.retrying" not in (r / "events.jsonl").read_text(),
      f"spawns={n_spawns}")
check("T8c the death keeps its EVIDENCE: raw capture names the provider failure",
      CFG_MARK in (rec.get("raw") or "") and CFG_MARK in rec.get("error", ""),
      str(rec.get("raw"))[:80])

# ---------- T9 rc=0 + valid fence still harvests honestly (partial is for the honest dead) ----------
# The reorder must NOT touch the #4 law for deaths the config classifier does not
# claim: slow config death keeps its classification (already pinned), and a child
# that dies late rc!=0 with a valid fence stays partial (control below).
(HOME / "fake.log").write_text("")
r = mk("jam8-slow-fenced", [{"id": "a", "type": "agent", "goal": "cfg JAM8-SLOWF",
                             "model": "turbo-a", "provider": "nope", "schema": SCHEMA}],
       retry_backoff=[0.05, 0.1])
out = wf_run("jam8-slow-fenced", {"FAKE_MODE": "cfgtypos", "FAKE_CFG_FENCED": "1",
                                 "FAKE_CFG_SLOW": "1.5", "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
check("T9 OUTSIDE the window the fence still harvests as before (reorder is window-gated)",
      rec.get("error_class") != "config_input",
      json.dumps({k: rec.get(k) for k in ("status", "error_class")}))

# ---------- T10/T11 ADOPTED config death: never a laundered done ----------
# Mirror of the committee's adopt probes at unit level (deterministic, no races):
# a verified-live orphan whose capture is ONLY the config diagnostic must land
# failed/config_input — with a bare capture (T10) and with a node schema that a
# coercing harvest would otherwise satisfy (T11).
def _adopt_meta(run):
    return {"_run": run, "_stop": threading.Event(), "_procs_lock": threading.Lock(),
            "_procs": {}, "_spawn_n": {}, "_retries_left": wf.DEFAULT_RETRY_BUDGET,
            "retry_backoff": [0.05]}

CFG_CAP = ("Warning: Unknown provider 'nope'. Check 'duckwork model' for available "
           "providers, or run 'duckwork doctor' to diagnose config issues. Falling "
           "back to auto provider detection.\nError: Unknown provider 'nope'\n")

for label, schema in (("T10 adopted config death (prose capture)", None),
                      ("T11 adopted config death + coercing result schema",
                       {"type": "object", "required": ["result"],
                        "properties": {"result": {"type": "string"}}})):
    r = mk("jam8-adopt", [{"id": "fan", "type": "agent", "goal": "cfg", "provider": "nope",
                           "fanout": {"items": ["x"], "goal": "cfg"}}])
    nid, index, pid = "fan", 0, 424242  # identity is injected: this test owns the child facts
    lp = r / "logs" / "fan.0.a0.log"
    lp.write_text(CFG_CAP)
    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    child = {"pid": pid, "skey": f"wf:jam8-adopt:fan:0:t.nonce", "log_path": str(lp),
             "started": started, "attempt": 0}
    meta = _adopt_meta(r)
    # the config death is a FAST death: ms since the record's started must sit
    # inside the window for the classifier to speak (honest to the probe's 334ms)
    recd = wf._adopt_child(meta, {"id": "fan", "type": "agent", "provider": "nope",
                                  "fanout": {"items": ["x"], "goal": "cfg"}},
                           {"fan": {"id": "fan"}}, index, child, schema)
    check(label + " -> failed/config_input (rc unobservable is no license for done)",
          recd.get("status") == "failed" and recd.get("error_class") == "config_input",
          json.dumps({k: recd.get(k) for k in ("status", "error_class")}))
    check(label + ": evidence survives on the record",
          CFG_MARK in (recd.get("raw") or ""), str(recd.get("raw"))[:60])

print("RESULT " + ("GREEN" if ok else "RED"))
sys.exit(0 if ok else 1)
