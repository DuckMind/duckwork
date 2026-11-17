#!/usr/bin/env python3
"""v0.7.6 Lane A contracts (Q1 + Q4 + Q8), real runner + tests/fake.

Q1  spawn-time node record (status running, spawn_cmd with the prompt path
    redacted, log_path, pid, started, skey, attempt, efp) written while the child
    is live; write-through per-spawn stdout logs under <run>/logs/ that grow
    mid-run; node_rec() treats a running record as pending (replay-skip safe by
    construction); typed error_class from runner-known facts only; verdict-only
    error lines (inherited CLI advice stripped); <run>/runner_exit.json on every
    exit path — done / blocked / stopped / held / crashed (in-process crash +
    SIGKILL 'no exit record' case).
Q4  transient retry: max 2 respawns (backoff 5s/20s default), ONLY error_class
    ∈ {transport, unknown} AND api_calls == 0 for the dead attempt (via
    wfcommon.child_metrics) AND not stopped AND per-run budget (6);
    attempts_log on the record; final = transport_exhausted; schema/timeout/
    provider_400/cancelled/spawn never retried; max_turns assignable ONLY from the
    child's core -Q turn report (typed_maxturns modes) — prose stays unpinnable.
Q8  whole schema injected into the child's prompt under '## Required answer
    shape' before CONTRACT; 4000-char cap with required+property-names fallback.

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_failures_0923.py
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util, json, os, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home9"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402
from wf_test_markers import read_pid_marker, read_json_marker   # est-jue3: one parseable-content wait family (the #267 shape, shared)

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

def exits_of(r):
    return json.loads((r / "runner_exit.json").read_text())

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

# ============ Q1a: spawn-time record while the child is LIVE ============
# FAKE_MODE=early prints one line, flushes, then keeps cooking — the record and
# the log must be observable mid-run.
r = mk("q1-live", [{"id": "live", "type": "agent", "goal": "LIVE q1-live",
                    "model": "sol", "toolsets": "web"}])
argv_log = HOME / "argv_q1.log"; pid_log = HOME / "pid_q1.log"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
           FAKE_MODE="early", FAKE_EARLY_SLEEP="4",
           FAKE_ARGV_LOG=str(argv_log), FAKE_PID_LOG=str(pid_log))
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", "q1-live"],
                        env=env, stdout=subprocess.PIPE, text=True)
live = None
deadline = time.time() + 30
while time.time() < deadline:
    p = r / "nodes" / "live.json"
    if p.exists():
        try:
            live = json.loads(p.read_text())
            if live.get("status") == "running":
                break
        except Exception:
            pass
    time.sleep(0.05)
out = proc.communicate(timeout=120)[0].strip()
check("Q1 spawn record exists while child is live (status=running)",
      live and live.get("status") == "running", json.dumps(live)[:160] if live else "never appeared")
child_pid = int(pid_log.read_text().split()[0]) if pid_log.exists() else None
check("Q1 spawn record carries the live child's pid",
      live and live.get("pid") == child_pid and child_pid is not None,
      f"rec={live and live.get('pid')} fake={child_pid}")
check("Q1 spawn record carries skey/attempt/started/efp",
      live and live.get("skey", "").startswith(f"wf:{r.name}:live:") and live.get("attempt") == 0
      and live.get("started") and len(live.get("efp", "")) == 16, json.dumps(live)[:200])
sc = (live or {}).get("spawn_cmd") or []
# 1.1: the prompt file is DURABLE (A1) — spawn_cmd names it inside <run>/logs,
# the <prompt> redaction and the tempfile are gone. The lock inverts: argv must
# carry the real prompt path and it must live in the run dir, never in tmp.
check("Q1 spawn_cmd: --query-file names the durable prompt file in the run dir",
      "--query-file" in sc and sc[sc.index("--query-file") + 1].startswith(str(r / "logs"))
      and sc[sc.index("--query-file") + 1].endswith(".prompt.md")
      and "--oneshot" in sc and "-m" in sc and sc[sc.index("-m") + 1] == "sol"
      and "-t" in sc and sc[sc.index("-t") + 1] == "web"
      and "<prompt>" not in sc and not any("/tmp" in a for a in sc), json.dumps(sc)[:220])
check("Q1 the durable prompt file exists and spawn_cmd leaks no tmp path",
      live and Path(sc[sc.index("--query-file") + 1]).exists()
      and not any("/tmp" in a for a in sc), json.dumps(sc)[:160])
lp = Path((live or {}).get("log_path", "/nonexistent"))
check("Q1 log_path lives under <run>/logs/",
      str(lp).startswith(str(r / "logs")) and lp.name == "live.a0.log", str(lp))
# mid-run log growth: the early-flushed line is readable BEFORE the child exits
mid = lp.read_text() if lp.exists() else ""
check("Q1 log grows mid-run (write-through, tail -f works)",
      "partial progress" in mid, repr(mid[:80]))
check("Q1 lifecycle unaffected (DONE after the child finishes)", "WORKFLOW_DONE q1-live" in out, out[:80])
rec = rec_of(r, "live")
check("Q1 commit wins over spawn record (merged node record is the commit)",
      rec["status"] == "done" and rec.get("error_class") is None, json.dumps(rec)[:120])
check("Q1 committed record keeps the spawn evidence (log_path/pid/spawn_cmd)",
      rec.get("log_path") == str(lp) and rec.get("pid") == child_pid and rec.get("spawn_cmd"), json.dumps(rec)[:120])
# running record is SAFE BY CONSTRUCTION: node_rec must call it pending
byid = {n["id"]: n for n in json.loads((r / "graph.json").read_text())["nodes"]}
r2 = RUNS / "q1-pending"
shutil.rmtree(r2, ignore_errors=True); (r2 / "nodes").mkdir(parents=True); (r2 / "gates").mkdir()
(r2 / "graph.json").write_text(json.dumps(byid and {"name": "q1-pending", "nodes": [byid["live"]]}))
(r2 / "nodes" / "live.json").write_text(json.dumps(dict(live, status="running")))
st, _ = wfcommon.node_rec(r2, byid["live"], {"live": byid["live"]})
check("Q1 a status=running record is pending to node_rec (never a commit)", st == "pending", st)

# ============ Q1b: typed error classes from fake modes ============
# spawn: duckwork_bin missing (runner-known OSError fact)
r = mk("q1-spawn", [{"id": "a", "type": "agent", "goal": "sp"}])
(r / "run.json").write_text(json.dumps({"duckwork_bin": "/nonexistent/duckwork-bin",
                                        "concurrency": 1, "node_timeout": 10,
                                        "retry_backoff": [0.05, 0.05]}))
out = wf("q1-spawn")
rec = rec_of(r, "a")
check("class spawn: Popen OSError", out.startswith("WORKFLOW_FAILED") and rec["error_class"] == "spawn"
      and rec.get("attempts_log") is None, json.dumps(rec)[:160])

# cancelled: stop mid-flight (runner SIGKILLs the group; negative rc + stop set)
r = mk("q1-cancel", [{"id": "a", "type": "agent", "goal": "SLEEP 30 q1-cancel"}], concurrency=1)
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"))
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", "q1-cancel"],
                        env=env, stdout=subprocess.PIPE, text=True)
# est-jue3: parseable-content waits (the #267 read_pid_marker/read_json_marker
# shape), not existence-then-parse. The spawn-time record appears via atomic
# replace but wf.pid is stamped with a plain write_text — visible at open(),
# bytes later; the old int(read_text) could land on an empty stamp.
read_json_marker((r / "nodes" / "a.json"), timeout=60)
(r / "stop.request").write_text("1")
out = proc.communicate(timeout=90)[0].strip()
rec = rec_of(r, "a")
check("class cancelled: SIGKILLed child of a stopped run is cancelled, not unknown",
      "WORKFLOW_STOPPED" in out and rec["error_class"] == "cancelled", f"{out[:60]} {rec.get('error_class')}")
check("runner_exit: stopped", json.loads((r / "runner_exit.json").read_text())["reason"] == "stopped")

# timeout: hang past node timeout — never retried
r = mk("q1-timeout", [{"id": "a", "type": "agent", "goal": "hang q1-timeout", "timeout": 2}],
       retry_backoff=[0.05, 0.05])
(HOME / "fake.log").write_text("")
out = wf("q1-timeout", {"FAKE_MODE": "hang", "FAKE_HANG_SEC": "30"})
rec = rec_of(r, "a")
n_spawns = (HOME / "fake.log").read_text().count("q1-timeout")
check("class timeout: runner-killed child, never retried (timeout excluded)",
      rec["error_class"] == "timeout" and "timeout after 2s" in rec["error"]
      and rec.get("attempts_log") is None and n_spawns == 1, f"class={rec.get('error_class')} spawns={n_spawns}")

# no_json: FAILME dies rc=0 with empty stdout
r = mk("q1-nojson", [{"id": "a", "type": "agent", "goal": "FAILME q1-nojson"}])
out = wf("q1-nojson")
rec = rec_of(r, "a")
check("class schema (was no_json): rc=0 empty output after the 1 retry", rec["error_class"] == "schema", json.dumps(rec)[:140])

# schema: valid json failing the node schema, twice
r = mk("q1-schema", [{"id": "a", "type": "agent", "goal": "sch q1-schema",
                      "schema": {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}}])
out = wf("q1-schema", {"FAKE_MODE": "bad_schema"})
rec = rec_of(r, "a")
check("class schema: validation failed twice", rec["error_class"] == "schema"
      and "schema validation" in rec["error"], json.dumps(rec)[:160])

# transport: stable marker pinned from the CLI escalation shape — retried (Q4)
r = mk("q1-transport", [{"id": "a", "type": "agent", "goal": "tr q1-transport"}],
       retry_backoff=[0.05, 0.1])
(HOME / "fake.log").write_text("")
out = wf("q1-transport", {"FAKE_MODE": "transport", "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
n_spawns = (HOME / "fake.log").read_text().count("q1-transport")
check("class transport→transport_exhausted after exactly 2 retries (3 spawns)",
      rec["error_class"] == "transport_exhausted" and n_spawns == 3, f"class={rec.get('error_class')} spawns={n_spawns}")
check("Q4 attempts_log records every failed attempt", len(rec.get("attempts_log") or []) == 2
      and rec["attempts_log"][0]["error_class"] == "transport" and rec["attempts_log"][0].get("at"),
      json.dumps(rec.get("attempts_log")))
check("Q4 retry events land in the ledger",
      any(e.get("event") == "node.retrying" for e in
          (json.loads(l) for l in (r / "events.jsonl").read_text().splitlines())), "no node.retrying")
check("retry verdict keeps the pinned marker, drops the Unknown toolsets advice",
      "APIConnectionError" in rec["error"] and "Unknown toolsets" not in rec["error"], rec["error"][:120])
check("runner_exit: blocked by failed <ids>",
      json.loads((r / "runner_exit.json").read_text())["reason"] == "blocked by failed a")

# provider_400 + advice stripped + never retried
r = mk("q1-400", [{"id": "a", "type": "agent", "goal": "p400 q1-400"}])
(HOME / "fake.log").write_text("")
out = wf("q1-400", {"FAKE_MODE": "provider400"})
rec = rec_of(r, "a")
check("class provider_400: pinned Error-code-400 marker, NOT retried",
      rec["error_class"] == "provider_400" and "Error code: 400" in rec["error"]
      and (HOME / "fake.log").read_text().count("q1-400") == 1, f"{rec.get('error_class')} {rec['error'][:80]}")
check("verdict strips inherited CLI advice (Try…//new or /model)",
      "Try re-running" not in rec["error"] and "/new or /model" not in rec["error"], rec["error"][:160])
check("raw keeps the last 2000 chars (advice survives there)",
      "Try re-running" in (rec.get("raw") or ""), (rec.get("raw") or "")[:60])

# unknown: prose-only death — missing metrics is NOT zero-call evidence; fail closed without retry
r = mk("q1-unknown", [{"id": "a", "type": "agent", "goal": "unk q1-unknown"}],
       retry_backoff=[0.05, 0.1])
(HOME / "fake.log").write_text("")
out = wf("q1-unknown", {"FAKE_MODE": "unknown"})
rec = rec_of(r, "a")
check("unknown death without API-call evidence is not retried",
      rec["error_class"] == "unknown" and not rec.get("attempts_log")
      and (HOME / "fake.log").read_text().count("q1-unknown") == 1,
      json.dumps(rec)[:180])

# max_turns NOT grepable; prose cannot establish retry safety without a DB row
r = mk("q1-maxturns", [{"id": "a", "type": "agent", "goal": "mt q1-maxturns", "max_turns": 3}])
out = wf("q1-maxturns", {"FAKE_MODE": "maxturns"})
rec = rec_of(r, "a")
check("max_turns stays unassigned and no-evidence failure is not retried",
      rec["error_class"] == "unknown" and not rec.get("attempts_log")
      and (HOME / "fake.log").read_text().count("q1-maxturns") == 1,
      f"class={rec.get('error_class')}")

# typed termination: the child's core -Q turn report (DUCKWORK_QUIET_TURN_REPORT_FILE
# contract) is the ONLY way max_turns becomes assignable — prose stays unpinnable.
r = mk("q1-typed", [{"id": "a", "type": "agent", "goal": "ty q1-typed", "max_turns": 60}])
out = wf("q1-typed", {"FAKE_MODE": "typed_maxturns"})
rec = rec_of(r, "a")
check("typed report: error_class=cap_exhausted, reason + guidance in error, single spawn, no retry",
      rec["error_class"] == "cap_exhausted" and not rec.get("attempts_log")
      and "max_iterations_reached(61/60)" in rec["error"] and "turn budget" in rec["error"]
      and (HOME / "fake.log").read_text().count("q1-typed") == 1,
      json.dumps(rec)[:220])
check("typed report consumed: per-spawn turn.json cleaned from logs/",
      not list((r / "logs").glob("*.turn.json")),
      str(list((r / "logs").iterdir())))

# report present but UNTYPED (empty turn_exit_reason) must NOT invent max_turns
r = mk("q1-typed-empty", [{"id": "a", "type": "agent", "goal": "te q1-typed-empty"}])
out = wf("q1-typed-empty", {"FAKE_MODE": "typed_empty_report"})
rec = rec_of(r, "a")
check("empty typed report stays unknown (absence of type is honest nothing)",
      rec["error_class"] == "unknown" and (HOME / "fake.log").read_text().count("q1-typed-empty") == 1,
      f"class={rec.get('error_class')}")

# typed max_turns beats the api_calls==0 retry gate: budget exhaustion is never
# transient — even a provably-zero-traffic dead attempt must not respawn.
r = mk("q1-typed-gate", [{"id": "a", "type": "agent", "goal": "tg q1-typed-gate", "max_turns": 5}])
out = wf("q1-typed-gate", {"FAKE_MODE": "typed_maxturns", "FAKE_API_CALLS": "0"})
rec = rec_of(r, "a")
check("typed cap_exhausted NOT transient-retried despite api_calls==0 evidence",
      rec["error_class"] == "cap_exhausted" and not rec.get("attempts_log")
      and (HOME / "fake.log").read_text().count("q1-typed-gate") == 1,
      json.dumps(rec)[:220])

# ============ Q4 gates ============
# api_calls > 0 for the dead attempt ⇒ NO retry (fake writes the state.db row)
if not (HOME / "state.db").exists():
    c = sqlite3.connect(HOME / "state.db")
    c.execute("create table sessions (id text primary key, title text, model text, input_tokens int, output_tokens int, "
              "cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, estimated_cost_usd real, "
              "last_activity_at real, last_activity_description text, ended_at real, started_at real)")
    c.commit(); c.close()
r = mk("q1-apicalls", [{"id": "a", "type": "agent", "goal": "ac q1-apicalls"}],
       retry_backoff=[0.05, 0.05])
(HOME / "fake.log").write_text("")
out = wf("q1-apicalls", {"FAKE_MODE": "transport", "FAKE_API_CALLS": "1"})
rec = rec_of(r, "a")
check("retry gate: api_calls > 0 for the dead attempt ⇒ single spawn, class stays transport",
      (HOME / "fake.log").read_text().count("q1-apicalls") == 1
      and rec["error_class"] == "transport" and rec.get("attempts_log") is None, json.dumps(rec)[:150])

# budget: one retry slot for the run; two nodes both unknown-dying
r = mk("q1-budget", [{"id": "a", "type": "agent", "goal": "bud-a"},
                     {"id": "b", "type": "agent", "goal": "bud-b"}],
       concurrency=1, retry_backoff=[0.05, 0.05], retry_budget=1)
(HOME / "fake.log").write_text("")
out = wf("q1-budget", {"FAKE_MODE": "unknown", "FAKE_API_CALLS": "0"})
spawns = (HOME / "fake.log").read_text()
ra, rb = rec_of(r, "a"), rec_of(r, "b")
check("per-run retry budget (6 default, 1 here): total respawns capped at the budget",
      spawns.count("bud-a") + spawns.count("bud-b") == 3,  # 2 base + exactly 1 respawn
      f"a={spawns.count('bud-a')} b={spawns.count('bud-b')}")
check("budget-exhausted finals are transport_exhausted with attempts_log",
      ra["error_class"] == "transport_exhausted" and rb["error_class"] == "transport_exhausted"
      and len(ra.get("attempts_log") or []) == 2 and len(rb.get("attempts_log") or []) == 1,
      f"a={ra.get('attempts_log')} b={rb.get('attempts_log')}")

# stop during the backoff: no respawn after stop
r = mk("q1-stopretry", [{"id": "a", "type": "agent", "goal": "SLEEP 1 q1-stopretry"}],
       concurrency=1, retry_backoff=[20.0, 20.0])
(HOME / "fake.log").write_text("")
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
           FAKE_MODE="unknown", FAKE_API_CALLS="0")
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", "q1-stopretry"],
                        env=env, stdout=subprocess.PIPE, text=True)
while not (r / "events.jsonl").exists() or "node.retrying" not in (r / "events.jsonl").read_text():
    time.sleep(0.05)
(RUNS / "q1-stopretry" / "stop.request").write_text("1")
out = proc.communicate(timeout=60)[0].strip()
check("stop during backoff: retry never launches, run exits STOPPED",
      (HOME / "fake.log").read_text().count("q1-stopretry") == 1 and "WORKFLOW_STOPPED" in out,
      f"spawns={(HOME / 'fake.log').read_text().count('q1-stopretry')} out={out[:60]}")

# schema death never retried (Q4 exclusion) — FAILME produced 2 spawns (1 schema-retry),
# the transient retry adds none:
r = mk("q1-noschemaretry", [{"id": "a", "type": "agent", "goal": "FAILME nosr"}],
       retry_backoff=[0.05, 0.05])
(HOME / "fake.log").write_text("")
out = wf("q1-noschemaretry")
rec = rec_of(r, "a")
check("schema/no_json death is NEVER transient-retried (exactly the 1 schema-retry)",
      rec["error_class"] == "schema" and (HOME / "fake.log").read_text().count("FAILME nosr") == 2,
      f"class={rec.get('error_class')} spawns={(HOME / 'fake.log').read_text().count('FAILME nosr')}")

# ============ Q1c: runner_exit on every path ============
r = mk("exit-done", [{"id": "a", "type": "agent", "goal": "ok exit-done"}])
wf("exit-done")
rec = exits_of(r)
check("runner_exit done: {reason: done, at}", rec["reason"] == "done" and rec.get("at"), json.dumps(rec))

r = mk("exit-held", [{"id": "a", "type": "agent", "goal": "ok exit-held"},
                     {"id": "g", "type": "gate", "after": ["a"], "question": "q?"}])
out = wf("exit-held")
rec = exits_of(r)
check("runner_exit held: 'held at <gate>'", rec["reason"] == "held at g" and "WORKFLOW_HELD" in out, json.dumps(rec))
g = {n["id"]: n for n in json.loads((r / "graph.json").read_text())["nodes"]}
(r / "gates" / "g.json").write_text(json.dumps({"answer": "yes", "_def": wfcommon.efp(g, g["g"]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))
out = wf("exit-held")
check("respawn clears the stale exit record and re-verdicts",
      exits_of(r)["reason"] == "done" and "WORKFLOW_DONE" in out, json.dumps(exits_of(r)))

# crashed (in-process: the runner's own finalize dies → reason 'crashed: …')
spec = importlib.util.spec_from_file_location("wf_crash", str(BUILD / "wf.py"))
wfc = importlib.util.module_from_spec(spec); spec.loader.exec_module(wfc)
r = mk("exit-crash", [{"id": "a", "type": "agent", "goal": "ok exit-crash"}])
_real_fin = wfc.finalize
wfc.finalize = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom under test"))
crashed = False
try:
    wfc.main("exit-crash")
except RuntimeError:
    crashed = True
finally:
    wfc.finalize = _real_fin
    if wfc._LOCK_FD is not None:
        os.close(wfc._LOCK_FD); wfc._LOCK_FD = None
rec = exits_of(r)
check("runner_exit crashed: exception one-liner recorded, exception re-raised",
      crashed and rec["reason"].startswith("crashed: RuntimeError: boom"), json.dumps(rec))

# SIGKILL path: dead pid + NO exit record ⇒ Lane B's reader says so
r = mk("exit-kill", [{"id": "a", "type": "agent", "goal": "SLEEP 60 exit-kill"}])
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"))
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", "exit-kill"],
                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# est-jue3: same parseable-content waits at the SIGKILL site (see the
# q1-cancel site's note above).
read_json_marker((r / "nodes" / "a.json"), timeout=60)
runner_pid = read_pid_marker((r / "wf.pid"))[0]
os.kill(runner_pid, 9)
proc.wait(timeout=30)
check("SIGKILL leaves NO exit record (honest absence)", not (r / "runner_exit.json").exists())
check("dead pid + absent record ⇒ 'crashed (no exit record)' via the reader",
      wfcommon.runner_exit_read(r) == {"reason": "crashed (no exit record)"},
      str(wfcommon.runner_exit_read(r)))

# ============ Q8: schema into the child prompt ============
small = {"type": "object", "required": ["verdict"],
         "properties": {"verdict": {"type": "string"}, "score": {"type": "number"}}}
r = mk("q8-small", [{"id": "a", "type": "agent", "goal": "shape q8-small", "schema": small}])
pl = HOME / "prompt_q8.log"
if pl.exists(): pl.unlink()
out = wf("q8-small", {"FAKE_PROMPT_LOG": str(pl)})
text = pl.read_text()
check("Q8 whole schema injected under '## Required answer shape' before CONTRACT",
      "## Required answer shape" in text and '"required":["verdict"]' in text
      and text.find("## Required answer shape") < text.find("Finish your answer with ONE")
      and text.count("## Required answer shape") >= 1, text[:120])
idx = text.find("## Required answer shape")
check("Q8 the fenced block is compact json holding the WHOLE schema",
      json.loads(text[idx:].split("```json", 1)[1].split("```", 1)[0].strip()) == small, text[idx:idx+120])

# oversized schema → required + top-level property names fallback
big = {"type": "object", "required": ["must"],
       "properties": {"must": {"type": "string"}, **{f"f{i}": {"type": "string", "description": "x" * 60} for i in range(120)}}}
r = mk("q8-big", [{"id": "a", "type": "agent", "goal": "shape q8-big", "schema": big}])
pl2 = HOME / "prompt_q8big.log"
if pl2.exists(): pl2.unlink()
out = wf("q8-big", {"FAKE_PROMPT_LOG": str(pl2)})
text = pl2.read_text()
idx = text.find("## Required answer shape")
block = text[idx:].split("```json", 1)[1].split("```", 1)[0].strip()
fb = json.loads(block)
check("Q8 cap 4000: oversized schema falls back to required + property names",
      fb.get("required") == ["must"] and "must" in (fb.get("properties") or {})
      and len(block) <= 4000, f"len={len(block)}")
check("Q8 fallback drops the deep definitions",
      "description" not in block)

# no schema ⇒ no shape section (contract unchanged for plain nodes)
r = mk("q8-none", [{"id": "a", "type": "agent", "goal": "plain q8-none"}])
pl3 = HOME / "prompt_q8none.log"
if pl3.exists(): pl3.unlink()
wf("q8-none", {"FAKE_PROMPT_LOG": str(pl3)})
check("Q8 no schema => no shape section in the prompt", "Required answer shape" not in pl3.read_text())

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
