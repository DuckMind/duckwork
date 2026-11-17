#!/usr/bin/env python3
"""est-t0vz / issue #54 — credential-window 429s get their own `ratelimit` class
and a bounded park, NOT the transport ladder.

The banner under test is the VERBATIM AuthError the stock CLI raises at
/opt/duckwork/duckwork_cli/runtime_provider.py:358
  "Anthropic credentials are rate-limited for <model>; other Claude models remain
   available (see `duckwork auth list`)."
reaching the runner's merged capture only as the oneshot escalation line
(oneshot.py:322 `duckwork -z: agent failed: {failure}`, rc=1). Pinned here:
  (1) the classifier returns `ratelimit` for the banner and NOTHING else changes
      (plain 429 stays transport; quota-horizon stays fatal_quota; the banner wins
      even when a quota phrase rides the same marker);
  (2) each park emits node.retrying with error_class=ratelimit and backoff_s inside
      the jittered interval;
  (3) the park count is bounded by the node's remaining budget (per-run retry
      budget AND wall clock — an interval that cannot fit fires ZERO parks);
  (4) give-up fails the node with the verbatim 'credential rate-limited for <model>'
      as the error text, and the run reads WORKFLOW_FAILED.

Run: cd tests && /opt/duckwork/.venv/bin/python3 test_ratelimit_54.py
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
HOME = HERE / "home-rl54"
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ.pop("WF_RUNS_ROOT", None)   # hermetic: runs live under HOME/workflows
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

# ---------- (1) classifier: the banner is its own class; every other pin holds ----------
BANNER = ("Warning: Unknown toolsets: bogus\n"
          "duckwork -z: agent failed: Anthropic credentials are rate-limited for "
          "claude-fable-5-1; other Claude models remain available (see `duckwork auth list`).\n")
ec, marker = wf._classify_rc_output(BANNER)
check("banner -> ratelimit (not transport, not unknown)", ec == "ratelimit", f"{ec}/{marker}")
check("marker is the escalation line", marker and marker.startswith("duckwork -z: agent failed:")
      and "rate-limited for claude-fable-5-1" in marker, str(marker))

PLAIN_429 = "duckwork -z: agent failed: Error code: 429 - {'error': 'slow down'}"
ec2, _ = wf._classify_rc_output(PLAIN_429)
check("plain 429 stays transport (pin unchanged)", ec2 == "transport", ec2)

QUOTA_MARK = ('Provider said: HTTP 429: {"error": {"message": "ChatGPT or Codex '
              'Subscription usage limit reached, resets in ~109 hours"}}')
ec3, _ = wf._classify_rc_output(QUOTA_MARK)
check("quota phrase + horizon stays fatal_quota (pin unchanged)", ec3 == "fatal_quota", ec3)

CONN = "duckwork -z: agent failed: openai.APIConnectionError. Connection error."
ec4, _ = wf._classify_rc_output(CONN)
check("connection error stays transport (pin unchanged)", ec4 == "transport", ec4)

BANNER_PLUS_QUOTA = ("duckwork -z: agent failed: Anthropic credentials are rate-limited for "
                     "claude-fable-5-1 (429 usage limit reached, resets in ~109 hours)")
ec5, _ = wf._classify_rc_output(BANNER_PLUS_QUOTA)
check("banner wins over a quota phrase on the same marker", ec5 == "ratelimit", ec5)

check("ratelimit is in the closed set", "ratelimit" in wf.ERROR_CLASSES)
check("ratelimit rides neither legacy ladder",
      "ratelimit" not in wf._RETRYABLE_CLASSES and "ratelimit" not in wf._BOUNDED_RETRY_CLASSES)

# ---------- harness (same shape as test_failures_0923) ----------
if HOME.exists(): shutil.rmtree(HOME)
HOME.mkdir(parents=True); RUNS.mkdir()
FAKE = str(HERE / "fake")

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def run_rl(run_id, extra_env=None, timeout=120):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
               FAKE_MODE="ratelimit")
    env.update(extra_env or {})
    env.pop("WF_RUNS_ROOT", None)
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines() if l.strip()]

def spawns(tag):
    return (HOME / "fake.log").read_text().count(tag)

# ---------- (2) bounded park then recovery: two 429 windows, then the answer ----------
(HOME / "fake.log").write_text("")
att = HOME / "rl-attempts-recover"; shutil.rmtree(att, ignore_errors=True)
r = mk("rl-recover", [{"id": "a", "type": "agent", "goal": "GO rl-recover"}],
       ratelimit_interval=0.3, ratelimit_jitter=0.2, retry_budget=6)
out = run_rl("rl-recover", {"FAKE_RL_FAILS": "2", "FAKE_ATTEMPT_DIR": str(att)})
rec = json.loads((r / "nodes" / "a.json").read_text())
rl_ev = [e for e in events(r) if e.get("event") == "node.retrying"
         and e.get("error_class") == "ratelimit"]
check("recover: node completes after the window", rec["status"] == "done"
      and (rec.get("output") or {}).get("result") == "answered-after-window",
      json.dumps(rec)[:160])
check("recover: exactly 2 parks (2 banner deaths, 3 spawns)", spawns("rl-recover") == 3
      and len(rl_ev) == 2, f"spawns={spawns('rl-recover')} parks={len(rl_ev)}")
check("recover: every park event carries backoff_s inside the jittered interval",
      all(0.3 * 0.8 - 0.05 <= e.get("backoff_s", -1) <= 0.3 * 1.2 + 0.05 for e in rl_ev),
      json.dumps([e.get("backoff_s") for e in rl_ev]))
check("recover: park attempts ride attempts_log with the ratelimit class",
      [a.get("error_class") for a in (rec.get("attempts_log") or [])] == ["ratelimit", "ratelimit"],
      json.dumps(rec.get("attempts_log")))
check("recover: WORKFLOW_DONE", out.startswith("WORKFLOW_DONE") or "WORKFLOW_DONE" in out, out[:80])

# ---------- (3a) bounded by the per-run retry budget: exactly N parks, honest give-up ----------
(HOME / "fake.log").write_text("")
r = mk("rl-giveup", [{"id": "a", "type": "agent", "goal": "GO rl-giveup"}],
       ratelimit_interval=0.2, ratelimit_jitter=0.0, retry_budget=2)
t0 = time.time()
out = run_rl("rl-giveup", {"FAKE_MODE": "ratelimit_always"})
dt = time.time() - t0
rec = json.loads((r / "nodes" / "a.json").read_text())
rl_ev = [e for e in events(r) if e.get("event") == "node.retrying"
         and e.get("error_class") == "ratelimit"]
check("give-up: WORKFLOW_FAILED", "WORKFLOW_FAILED" in out, out[:80])
check("give-up: class is ratelimit (terminal, never transport_exhausted)",
      rec["status"] == "failed" and rec.get("error_class") == "ratelimit",
      json.dumps(rec)[:160])
check("give-up: VERBATIM banner as the error text",
      rec.get("error") == "credential rate-limited for claude-fable-5-1", str(rec.get("error"))[:140])
check("give-up: park count honors the retry budget (2 parks => 3 spawns)",
      spawns("rl-giveup") == 3 and len(rl_ev) == 2, f"spawns={spawns('rl-giveup')} parks={len(rl_ev)}")
check("give-up: jittered backoff_s is exact at jitter=0 (0.2s parks)",
      all(e.get("backoff_s") == 0.2 for e in rl_ev), json.dumps([e.get("backoff_s") for e in rl_ev]))
check("give-up: the park is a WAIT, not a respawn storm (>= 2 parked intervals)",
      dt >= 0.4, f"wall={dt:.2f}s")
check("give-up: node.failed event carries the class + verbatim error",
      any(e.get("event") == "node.failed" and e.get("error_class") == "ratelimit"
          and e.get("error") == "credential rate-limited for claude-fable-5-1"
          for e in events(r)))
skipped = [e for e in events(r) if e.get("event") == "node.retry_skipped"]
check("give-up: budget exhaustion is logged once as retry_skipped",
      len(skipped) == 1 and skipped[0].get("error_class") == "ratelimit", json.dumps(skipped)[:160])

# ---------- (3b) bounded by the node's remaining wall budget: an interval that ----------
# ---------- cannot fit fires ZERO parks — give up at once, no respawn storm      ----------
(HOME / "fake.log").write_text("")
r = mk("rl-tight", [{"id": "a", "type": "agent", "goal": "GO rl-tight", "timeout": 2}],
       ratelimit_interval=60.0, retry_budget=6)   # a 60 s park can never fit a 2 s budget
t0 = time.time()
out = run_rl("rl-tight", {"FAKE_MODE": "ratelimit_always"})
dt = time.time() - t0
rec = json.loads((r / "nodes" / "a.json").read_text())
check("tight budget: ZERO parks, ONE spawn, no 60 s wait",
      spawns("rl-tight") == 1 and dt < 5 and not any(
          e.get("event") == "node.retrying" for e in events(r)),
      f"spawns={spawns('rl-tight')} wall={dt:.2f}s")
check("tight budget: verbatim give-up anyway (honest error either way)",
      rec.get("error") == "credential rate-limited for claude-fable-5-1"
      and rec.get("error_class") == "ratelimit", str(rec.get("error"))[:140])

# ---------- (4) transport stays untouched next to the new class ----------
# transport pin under the SAME code path: banner-free deaths still exhaust the 5s/20s ladder
(HOME / "fake.log").write_text("")
r = mk("rl-transport", [{"id": "a", "type": "agent", "goal": "GO rl-transport"}],
       retry_backoff=[0.05, 0.05], retry_budget=6)
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
           FAKE_MODE="transport", FAKE_API_CALLS="0")
env.pop("WF_RUNS_ROOT", None)
subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", "rl-transport"],
               env=env, capture_output=True, text=True, timeout=120)
rec = json.loads((r / "nodes" / "a.json").read_text())
check("transport pin: unchanged ladder -> transport_exhausted after 3 spawns (no ratelimit)",
      rec.get("error_class") == "transport_exhausted" and spawns("rl-transport") == 3,
      f"class={rec.get('error_class')} spawns={spawns('rl-transport')}")
check("transport pin: never a ratelimit event on a banner-free death",
      not any(e.get("error_class") == "ratelimit" for e in events(r)))

print("ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
