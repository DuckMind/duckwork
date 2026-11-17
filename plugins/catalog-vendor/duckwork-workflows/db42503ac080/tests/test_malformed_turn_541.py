#!/usr/bin/env python3
"""est-2ek.1.541 — a malformed turn (final reply = serialized tool-call markup)
must never commit as an answer and must re-drive.

Field shape (issue #541; its named turn-report locator was deleted by design — the
runner unlinks the per-spawn turn report on every harvest/death path — so this
pin REBUILDS the shape from the description instead of trusting the locator):
an agent child's turn ends with its FINAL REPLY being raw serialized tool-call
markup rendered as text ('<invoke name=...>'-shape), turn_exit_reason unknown,
exit_code 1.

Law pinned (the intake's demand, asserted against the REAL runner + tests/fake):
 A  exit-0 child whose final reply IS the markup (no fenced json):
    A1 never committed as done/partial, markup never lands in a committed output;
    A2 the node is re-driven exactly once (the attempt<1 correction retry);
    A3 the eventual failure is typed (class from the closed set) and its error
       carries the verbatim tool-call-as-text diagnostic.
 B  rc!=0 child (turn_exit_reason unknown — the reported shape) with the same markup:
    B1 never done/partial, no harvest, markup never a committed output;
    B2 the node IS re-driven (bounded re-drive within budget: exactly one extra
       spawn when the re-drive answers, never a loop when it doesn't);
    B3 the eventual failure carries a TYPED error_class for the malformed turn
       (closed-set member) AND the verbatim tool-call-text diagnostic (error
       names tool-call-as-text; the death record's `final` carries the markup).

Style: PASS/FAIL lines + exit code (test_failures_0923 house style). The fake's
toolcall_text_541 mode carries FAKE_RC / FAKE_TERN / FAKE_ATTEMPT_DIR / FAKE_ALWAYS
so both shapes are driven without touching product code.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home541"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
# #71 lesson, subprocess form: a lane process carries WF_RUNS_ROOT — pin the
# runner's runs root to the test home so no run can leak into the estate.
os.environ["WF_RUNS_ROOT"] = str(RUNS)
sys.path.insert(0, str(BUILD))
import wf as wfmod  # noqa: E402
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
    m = {"duckwork_bin": FAKE, "concurrency": 1, "node_timeout": 30,
         "retry_backoff": [0.05, 0.05]}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(HOME / "fake.log"),
               **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def spawns_of(run_id):
    """Spawns = per-attempt stdout logs the runner wrote (logs/<node>.a<N>.log)."""
    return len(list((RUNS / run_id / "logs").glob("*.a*.log")))

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

# The markup fixture, json-quoted (6st law: this file stays free of raw open-tag
# sequences a reply-serializer could re-parse). Same string the fake prints.
MARKUP = json.loads('"\\u003cinvoke name=\\"process_manage\\">\\n\\u003cparameter name=\\"action\\">poll\\u003c/parameter>\\n\\u003cparameter name=\\"session_id\\">lane-7\\u003c/parameter>\\n\\u003c/invoke>"')
SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}

def record_never_commits_markup(rec):
    """The markup must never ride a COMMITTED answer: no done/partial status, and
    neither rec['output'] nor any harvest carries it. The death record's evidence
    fields (raw/final/error) are diagnostics and are allowed — indeed demanded —
    to carry it verbatim."""
    if rec.get("status") in ("done", "partial"):
        return False
    if rec.get("harvest"):
        return False
    blob = json.dumps(rec.get("output")) if rec.get("output") is not None else ""
    return MARKUP not in blob

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

# ================= A: exit-0 child, final reply IS the markup =================
r = mk("m541-exit0", [{"id": "verify", "type": "agent",
                       "goal": "TOOLCALL541 m541-exit0 verify", "schema": SCHEMA}])
out = wf("m541-exit0", {"FAKE_MODE": "toolcall_text_541", "FAKE_RC": "0",
                        "FAKE_ALWAYS": "1", "FAKE_ATTEMPT_DIR": str(HOME / "att_exit0")})
rec = rec_of(r, "verify")
check("A1 exit-0: malformed reply is never committed done/partial, markup not in output",
      record_never_commits_markup(rec), json.dumps(rec)[:200])
check("A2 exit-0: node re-driven exactly once (correction retry = 2 spawns)",
      spawns_of("m541-exit0") == 2, f"spawns={spawns_of('m541-exit0')}")
check("A3 exit-0: failure typed from the closed set",
      rec["status"] == "failed" and rec.get("error_class") in wfmod.ERROR_CLASSES,
      f"class={rec.get('error_class')}")
check("A3 exit-0: error carries the verbatim tool-call-as-text diagnostic",
      "tool-call-as-text" in (rec.get("error") or ""), (rec.get("error") or "")[:160])
check("A3 exit-0: node.failed event typed (closed set)",
      any(e.get("event") == "node.failed" and e.get("error_class") in wfmod.ERROR_CLASSES
          for e in events(r)), json.dumps(events(r))[-200:])

# ================= B: rc!=0, turn_exit_reason unknown — the reported shape =================
# B-always: every spawn dies malformed — the budget + typed-diagnostic pin.
r = mk("m541-die", [{"id": "verify", "type": "agent",
                     "goal": "TOOLCALL541 m541-die verify", "schema": SCHEMA}])
out = wf("m541-die", {"FAKE_MODE": "toolcall_text_541", "FAKE_RC": "1",
                      "FAKE_TERN": "unknown", "FAKE_ALWAYS": "1",
                      "FAKE_ATTEMPT_DIR": str(HOME / "att_die")})
rec = rec_of(r, "verify")
check("B1 rc!=0: never done/partial, no harvest, markup never a committed output",
      record_never_commits_markup(rec), json.dumps(rec)[:200])
check("B2 rc!=0: node re-driven — more than the single first spawn (correction retry or bounded respawn)",
      spawns_of("m541-die") > 1, f"spawns={spawns_of('m541-die')}")
check("B2 rc!=0: re-drive bounded — exactly one extra spawn, never a loop",
      spawns_of("m541-die") == 2, f"spawns={spawns_of('m541-die')}")
check("B3 rc!=0: eventual failure carries a typed malformed-turn class (closed set)",
      rec["status"] == "failed" and rec.get("error_class") == "malformed_turn"
      and "malformed_turn" in wfmod.ERROR_CLASSES,
      f"class={rec.get('error_class')} closed={rec.get('error_class') in wfmod.ERROR_CLASSES}")
check("B3 rc!=0: error carries the verbatim tool-call-as-text diagnostic",
      "tool-call-as-text" in (rec.get("error") or ""), (rec.get("error") or "")[:160])
check("B3 rc!=0: death record's final carries the verbatim markup (diagnostic preserved)",
      MARKUP in (rec.get("final") or ""), (rec.get("final") or "")[:120])
check("B3 rc!=0: node.failed event typed (closed set)",
      any(e.get("event") == "node.failed" and e.get("error_class") in wfmod.ERROR_CLASSES
          for e in events(r)), json.dumps(events(r))[-200:])

# B-recover: first spawn dies malformed, the re-drive answers validly.
r = mk("m541-redriven", [{"id": "verify", "type": "agent",
                          "goal": "TOOLCALL541 m541-redriven verify", "schema": SCHEMA}])
out = wf("m541-redriven", {"FAKE_MODE": "toolcall_text_541", "FAKE_RC": "1",
                           "FAKE_TERN": "unknown",
                           "FAKE_ATTEMPT_DIR": str(HOME / "att_redriven")})
rec = rec_of(r, "verify")
check("B2 rc!=0: a re-drive that answers commits done with the fresh answer",
      rec["status"] == "done" and (rec.get("output") or {}).get("result") == "redriven",
      json.dumps(rec)[:200])
check("B2 rc!=0: recovered run re-drove exactly once (2 spawns)",
      spawns_of("m541-redriven") == 2, f"spawns={spawns_of('m541-redriven')}")
check("B2 rc!=0: the committed done never carries the markup",
      MARKUP not in json.dumps(rec.get("output")), json.dumps(rec.get("output"))[:160])

# Retry-class law: malformed_turn re-drives via the bounded (tool-progress)
# ladder — the shape by definition made API/tool calls, so the zero-calls Q4
# gate is the wrong evidence channel; and it must never widen beyond that.
check("class law: malformed_turn in the bounded (tool-progress) retry set",
      "malformed_turn" in wfmod._BOUNDED_RETRY_CLASSES, str(wfmod._BOUNDED_RETRY_CLASSES))
check("class law: malformed_turn not in the zero-calls transient set (no Q4 replay)",
      "malformed_turn" not in wfmod._RETRYABLE_CLASSES, str(wfmod._RETRYABLE_CLASSES))

print("RESULT", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
