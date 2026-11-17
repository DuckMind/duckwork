#!/usr/bin/env python3
"""lease-busy (Oct-3 field shape): a child that exits rc=130 carrying the CLI's
fail-closed session-lease notice must be typed `lease_busy` — a BOUNDED transient,
never terminal — and re-driven EXACTLY ONCE as a FRESH session under the next
attempt key, never `--continue` of the busy session.

Field evidence: two Oct-3 runs where a freshly spawned review child printed
'Session ... found but has no messages. Starting fresh.' then 'Stopped waiting
for another Duckwork process on this session. Your message was not processed.'
and exited 130 after ~1800 s (the CLI's lease wait). The runner knew only
SIGKILL deaths, so 130 fell to `unknown` and the node died terminal.

Gates pinned:
  * unit: _is_lease_busy demands BOTH facts (rc==130 AND the verbatim notice);
    either fact alone keeps the existing classification untouched.
  * membership: lease_busy in ERROR_CLASSES and _BOUNDED_RETRY_CLASSES, NOT in
    the Q4 _RETRYABLE_CLASSES (one bounded re-drive, no ladder).
  * e2e: stub child exits 130 with the notice -> node.retrying
    error_class=lease_busy -> exactly one re-drive -> second attempt (whose
    prompt must carry the fresh-session harvest preamble) exits 0 with a valid
    fenced answer -> node done, exactly 2 spawns, second spawn's --continue key
    differs from the first (FRESH session), node.retry stamps fresh_session.
  * e2e control: rc=130 WITHOUT the notice stays `unknown` and terminal
    (1 spawn, no lease events).

Run: cd tests && python3 test_lease_busy_retry.py
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home_lease"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")
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

def wf_run(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / "fake.log"), **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def spawns_of(run_id):
    return len(list((RUNS / run_id / "logs").glob("*.log")))

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}
NOTICE = ("Stopped waiting for another Duckwork process on this session. "
          "Your message was not processed.")

# ---- unit: the two-fact pin ----
check("unit: rc=130 + verbatim notice classifies lease_busy",
      wf._is_lease_busy(130, "Session x found but has no messages. Starting fresh.\n" + NOTICE) == (True, NOTICE))
check("unit: rc=130 WITHOUT the notice is NOT lease_busy",
      wf._is_lease_busy(130, "plain work chatter, no lease marker") == (False, None))
check("unit: the notice at rc=1 is NOT lease_busy",
      wf._is_lease_busy(1, NOTICE) == (False, None))
check("unit: rc=130 + notice survives the CLI's exact two-line shape",
      wf._is_lease_busy(130, NOTICE)[0] is True)

# ---- membership: bounded transient, never the Q4 ladder ----
check("lease_busy is in ERROR_CLASSES", "lease_busy" in wf.ERROR_CLASSES)
check("lease_busy is in _BOUNDED_RETRY_CLASSES", "lease_busy" in wf._BOUNDED_RETRY_CLASSES)
check("lease_busy is NOT in the Q4 _RETRYABLE_CLASSES (one bounded re-drive only)",
      "lease_busy" not in wf._RETRYABLE_CLASSES)

# ---- e2e: 130-with-notice -> one FRESH-session re-drive -> done ----
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

r = mk("lease-recover", [{"id": "a", "type": "agent", "goal": "REVIEW lease-recover",
                          "schema": SCHEMA}])
argv_log = HOME / "argv_lease.log"
out = wf_run("lease-recover", {"FAKE_MODE": "lease_busy",
                               "FAKE_ATTEMPT_DIR": str(HOME / "att_lease"),
                               "FAKE_ARGV_LOG": str(argv_log)})
rec = rec_of(r, "a")
evs = events(r)
check("e2e: lease-busy death recovers to done via the re-drive",
      rec["status"] == "done" and (rec.get("output") or {}).get("result") == "lease-recovered",
      str(rec)[:300])
check("e2e: retried EXACTLY once (2 spawns, never a loop)", spawns_of("lease-recover") == 2,
      f"spawns={spawns_of('lease-recover')}")
check("e2e: node.retrying error_class=lease_busy logged",
      any(e.get("event") == "node.retrying" and e.get("error_class") == "lease_busy"
          and "backoff_s" in e for e in evs), str([e.get("event") for e in evs]))
check("e2e: node.retry event logged with the lease reason + fresh_session",
      any(e.get("event") == "node.retry" and e.get("error_class") == "lease_busy"
          and e.get("fresh_session") is True
          and "lease" in (e.get("reason") or "").lower() for e in evs))
check("e2e: attempts_log carries the lease_busy death",
      any(a.get("error_class") == "lease_busy" for a in rec.get("attempts_log") or []),
      str(rec.get("attempts_log")))
check("e2e: the lease_busy death is never renamed transport_exhausted",
      rec.get("error_class") != "transport_exhausted"
      and not any(a.get("error_class") == "transport_exhausted"
                  for a in rec.get("attempts_log") or []))
check("e2e: run closes done", out.startswith("WORKFLOW_DONE lease-recover"), out[-200:])

# fresh-session proof: the two spawns' --continue keys must DIFFER (never --continue
# the busy session; the re-drive is the NEXT attempt session key).
lines = [l for l in argv_log.read_text().splitlines() if l.strip()] if argv_log.exists() else []
def cont_key(line):
    m = re.search(r"--continue (\S+)", line)
    return m.group(1) if m else None
k1, k2 = (cont_key(lines[0]), cont_key(lines[1])) if len(lines) >= 2 else (None, None)
check("e2e: re-drive spawns under a FRESH session key (never --continue the busy one)",
      bool(k1) and bool(k2) and k1 != k2, f"attempt keys: {k1!r} vs {k2!r}")

# ---- e2e control: rc=130 WITHOUT the notice stays unknown + terminal ----
r2 = mk("lease-control", [{"id": "a", "type": "agent", "goal": "PLAIN lease-control",
                           "schema": SCHEMA}])
out2 = wf_run("lease-control", {"FAKE_MODE": "rc130_quiet",
                                "FAKE_ATTEMPT_DIR": str(HOME / "att_ctl")})
rec2 = rec_of(r2, "a")
check("control: rc=130 WITHOUT the notice stays unknown and terminal",
      rec2["status"] == "failed" and rec2.get("error_class") == "unknown",
      str(rec2)[:300])
check("control: no lease re-drive fires for the bare-130 shape (1 spawn)",
      spawns_of("lease-control") == 1, f"spawns={spawns_of('lease-control')}")
check("control: no node.retrying lease_busy event",
      not any(e.get("event") == "node.retrying" and e.get("error_class") == "lease_busy"
              for e in events(r2)))

print(f"TOTAL {'PASS' if ok else 'FAIL'}")
raise SystemExit(0 if ok else 1)
