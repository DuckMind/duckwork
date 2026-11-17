#!/usr/bin/env python3
"""est-tmuu — a deterministic provider/alias config death is NOT transient transport.

Verified field report (2026-10-02T16:41Z): a node pinning a provider alias
the seat does not define makes the duckwork CLI exit rc!=0 in ~0.1s printing
`Unknown provider 'x'. Check 'duckwork model' ...`. The old classification surfaced
that death as the transient classes (unknown -> Q4 ladder), so the launcher
respawned the WHOLE recovery sequence on a deterministic input error and the run
finally landed transport_exhausted with the respawn budget burned.

The law this pin enforces: a child that dies rc!=0 inside the short window AND
whose captured output matches provider/alias config errors lands the node
`failed` with typed error_class `config_input` on ONE spawn — no respawn, and
the per-run retry budget (_retries_left) is not burned (the #24 fatal_quota law
applied to config typos). The window is the precision guard: the same capture
dying late keeps its existing classification.

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_config_input_tmuu.py
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home-tmuu"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ.pop("WF_RUNS_ROOT", None)   # hermetic: runs land under HOME/workflows
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402

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

# ---- the verified death capture (CLI arg-parse shape, main.py:2074) ----
FAST_CFG = ("Warning: Unknown provider 'nope'. Check 'duckwork model' for available "
            "providers, or run 'duckwork doctor' to diagnose config issues. Falling "
            "back to auto provider detection.\nError: Unknown provider 'nope'\n")

# ---------- (a) classifier unit: both facts, or nothing ----------
hit, marker = wf._classify_config_input(FAST_CFG, 120)
check("fast death + config marker -> config_input hit", hit and marker and "Unknown provider" in marker,
      f"{hit}/{marker}")
hit2, m2 = wf._classify_config_input(FAST_CFG, 1500)
check("same capture dying LATE is not config_input (window is the precision guard)",
      hit2 is False and m2 is None, f"{hit2}/{m2}")
hit3, _ = wf._classify_config_input("duckwork -z: agent failed: openai.APIConnectionError. Connection error.", 100)
check("fast transport death stays transport (needs the config marker, not just speed)",
      hit3 is False)
hit4, _ = wf._classify_config_input("Warning: Unknown model 'turbo-x42' vanished", 90)
check("'unknown model' is unresolved_model territory, never config_input",
      hit4 is False)
check("window constant is the ~1s reported shape", wf._CONFIG_INPUT_WINDOW_MS == 1000,
      str(wf._CONFIG_INPUT_WINDOW_MS))
check("config_input is in the closed set", "config_input" in wf.ERROR_CLASSES)
check("config_input is never retryable (neither ladder)",
      "config_input" not in wf._RETRYABLE_CLASSES
      and "config_input" not in wf._BOUNDED_RETRY_CLASSES)

# ---------- (b) run-level: fast config death lands config_input on ONE spawn ----------
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

r = mk("tmuu-fast", [{"id": "a", "type": "agent", "goal": "cfg TMUU-FAST", "model": "turbo-a", "provider": "nope"}],
       retry_backoff=[0.05, 0.1])
out = wf_run("tmuu-fast", {"FAKE_MODE": "cfgtypos", "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
n_spawns = (HOME / "fake.log").read_text().count("TMUU-FAST")
check("fast config death: run lands failed (WORKFLOW_FAILED, not a respawn loop)",
      "WORKFLOW_FAILED tmuu-fast" in out, out[:80])
check("typed error_class config_input — not transport_exhausted",
      rec.get("error_class") == "config_input", json.dumps(rec)[:200])
check("ONE spawn only: the launcher never respawns a deterministic input error",
      n_spawns == 1, f"spawns={n_spawns}")
check("no respawn ladder events", "node.retrying" not in (r / "events.jsonl").read_text(),
      "node.retrying present")
check("attempts_log absent (no ladder ran)", not rec.get("attempts_log"), json.dumps(rec.get("attempts_log")))
check("error names the fix (provider pin) and the marker survives",
      "provider" in rec["error"] and "Unknown provider" in rec["error"], rec["error"][:160])
check("failed event carries the typed class",
      any(e.get("event") == "node.failed" and e.get("error_class") == "config_input"
          for e in events(r)), "no typed node.failed")
check("fast wall actually inside the window (fake dies ~0.1s)",
      isinstance(rec.get("ms"), int) and rec["ms"] < wf._CONFIG_INPUT_WINDOW_MS, str(rec.get("ms")))

# ---------- (c) respawn budget is NOT burned ----------
# Direct probe of the two ladders (the ONLY code that decrements _retries_left):
# a config_input verdict must pass through both ladders untouched — no respawn,
# no budget decrement, r returned verbatim.
import threading
meta = {"_run": None, "_stop": threading.Event(), "_procs_lock": threading.Lock(),
        "_retries_left": wf.DEFAULT_RETRY_BUDGET, "retry_backoff": [0.05, 0.1]}
verdict = {"status": "failed", "error": "cfg", "error_class": "config_input",
           "ms": 120, "raw": FAST_CFG, "skey": None}
respawn_calls = []
out1 = wf._transient_retry(meta, dict(verdict), lambda **kw: respawn_calls.append(1), "node", {})
out2 = wf._bounded_retry(meta, out1, lambda **kw: respawn_calls.append(1), "node", {})
check("both ladders pass a config_input verdict through: zero respawns, budget intact",
      not respawn_calls and meta["_retries_left"] == wf.DEFAULT_RETRY_BUDGET
      and out2.get("error_class") == "config_input",
      f"respawns={len(respawn_calls)} left={meta['_retries_left']}")

# Run-level corroboration: a second config node in the same run also gets exactly
# one spawn (a respawn-burn would show as extra spawns / retry events / attempts_log).
(HOME / "fake.log").write_text("")
r = mk("tmuu-budget", [{"id": "cfg", "type": "agent", "goal": "cfg TMUU-BCFG", "model": "turbo-a", "provider": "nope"},
                       {"id": "cfg2", "type": "agent", "goal": "cfg TMUU-BCFG2", "model": "turbo-a", "provider": "nope"}])
out = wf_run("tmuu-budget", {"FAKE_MODE": "cfgtypos", "FAKE_API_CALLS": "0"})
recs = (rec_of(r, "cfg"), rec_of(r, "cfg2"))
ev_txt = (r / "events.jsonl").read_text()
check("two config deaths: one spawn each, typed, zero ladder events",
      recs[0]["error_class"] == "config_input" and recs[1]["error_class"] == "config_input"
      and (HOME / "fake.log").read_text().count("TMUU-BCFG\n") == 1
      and (HOME / "fake.log").read_text().count("TMUU-BCFG2") == 1
      and "retrying" not in ev_txt and "retry_skipped" not in ev_txt
      and not recs[0].get("attempts_log") and not recs[1].get("attempts_log"),
      f"classes={[x['error_class'] for x in recs]}")

# blocked descendant never spawns behind the config death
(HOME / "fake.log").write_text("")
r = mk("tmuu-budget2", [{"id": "cfg", "type": "agent", "goal": "cfg TMUU-C2", "model": "turbo-a", "provider": "nope"},
                        {"id": "tr", "type": "agent", "goal": "tr TMUU-T2", "after": ["cfg"]}])
out = wf_run("tmuu-budget2", {"FAKE_MODE": "cfgtypos", "FAKE_API_CALLS": "0"})
check("blocked descendant never spawns behind the config death",
      (HOME / "fake.log").read_text().count("TMUU-T2") == 0)

# control: the transport ladder still spends its full 2 respawns (3 spawns) —
# the fleet's retry machinery is untouched by the new class.
(HOME / "fake.log").write_text("")
r = mk("tmuu-budget3", [{"id": "a", "type": "agent", "goal": "tr TMUU-B3"}],
       retry_backoff=[0.05, 0.1])
out = wf_run("tmuu-budget3", {"FAKE_MODE": "transport", "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
n_spawns = (HOME / "fake.log").read_text().count("TMUU-B3")
check("control: transport ladder still spends its full 2 respawns (3 spawns)",
      rec["error_class"] == "transport_exhausted" and n_spawns == 3,
      f"class={rec.get('error_class')} spawns={n_spawns}")


# ---------- (d) the slow twin keeps the existing classification ----------
(HOME / "fake.log").write_text("")
r = mk("tmuu-slow", [{"id": "a", "type": "agent", "goal": "cfg TMUU-SLOW", "model": "turbo-a", "provider": "nope"}],
       retry_backoff=[0.05, 0.1])
out = wf_run("tmuu-slow", {"FAKE_MODE": "cfgtypos", "FAKE_CFG_SLOW": "1.5",
                           "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
check("same capture dying OUTSIDE the window is NOT config_input (window gate, not prose grep)",
      rec.get("error_class") != "config_input", json.dumps(rec)[:200])

print("RESULT " + ("GREEN" if ok else "RED"))
sys.exit(0 if ok else 1)
