#!/usr/bin/env python3
"""#24 — subscription-quota 429s are NOT transient transport.

(a) a marker carrying a reset horizon (or a quota-exhaustion phrase) classifies
    fatal_quota: fails on the FIRST attempt (no retry ladder), error names the model;
(b) the runner remembers an exhausted resolved model (seat-local cache);
(c) the door refuses to launch a node whose explicit model is cache-exhausted
    (advisory: a liveness ping that answers recovers the model).
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home-fq24"
RUNS = HOME / "workflows"
sys.path.insert(0, str(BUILD.parent))
import wf, wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + (f"  {detail}" if detail else "")))
    if not cond: ok = False

# ---------- (a) classifier ----------
QUOTA_MARK = ("Warning: x\n"
              "Provider said: HTTP 429: {\"error\": {\"message\": \"ChatGPT or Codex "
              "Subscription usage limit reached, resets in ~109 hours\"}}\n")
ec, marker = wf._classify_rc_output(QUOTA_MARK)
check("quota phrase + horizon -> fatal_quota", ec == "fatal_quota", f"{ec}/{marker}")
check("marker preserved", marker and "resets in" in marker, str(marker))

PLAIN_429 = "duckwork -z: agent failed: Error code: 429 - {'error': 'slow down'}"
ec2, _ = wf._classify_rc_output(PLAIN_429)
check("plain 429 stays transport (transient rate limit)", ec2 == "transport", ec2)

RATE_LIMIT_LONG = ("Provider said: HTTP 429: Too Many Requests. "
                   "Please retry later to avoid rate limiting")
ec3, _ = wf._classify_rc_output(RATE_LIMIT_LONG)
check("'rate limiting' prose alone is NOT quota", ec3 == "transport", ec3)

check("fatal_quota is in the closed set", "fatal_quota" in wf.ERROR_CLASSES)
check("fatal_quota is never retryable", "fatal_quota" not in wf._RETRYABLE_CLASSES
      and "fatal_quota" not in wf._BOUNDED_RETRY_CLASSES)

# ---------- (a) end-to-end: one attempt only, error names the model ----------
if HOME.exists(): shutil.rmtree(HOME)
RUNS.mkdir(parents=True)
FAKE = str(BUILD / "fake-fq24"); shutil.copy(BUILD / "fake_duckwork.py", FAKE); os.chmod(FAKE, 0o755)
LOG = HOME / "fake.log"

def mk(run_id, nodes):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": "fq", "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 2, "node_timeout": 30}))
    return r

env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(LOG),
           FAKE_MODE="quota", WF_QUOTA_CACHE=str(HOME / "quota-cache.json"))
node = [{"id": "a", "type": "agent", "goal": "GO", "model": "sol"}]
r = mk("fq-e2e", node)
for line in open(FAKE): pass  # noop; fake reads env at spawn
subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", str(r)],
               env=env, capture_output=True, timeout=120)
rec = json.loads((r / "nodes" / "a.json").read_text())
check("e2e: node failed", rec.get("status") == "failed", str(rec.get("status")))
check("e2e: class fatal_quota", rec.get("error_class") == "fatal_quota", str(rec.get("error_class")))
check("e2e: ONE attempt (no ladder)", (rec.get("attempts_log") or [0]) and len(rec.get("attempts_log") or []) <= 1
      and rec.get("attempts", 1) <= 1, f"attempts={rec.get('attempts')} log={len(rec.get('attempts_log') or [])}")
spawns = LOG.read_text().count("GO") if LOG.exists() else 0
check("e2e: exactly 1 spawn", spawns == 1, f"spawned {spawns}x")
check("e2e: error names the model", "sol" in (rec.get("error") or ""), str(rec.get("error"))[:120])

# ---------- (b) the seat-local cache got written ----------
qc = HOME / "quota-cache.json"
check("cache written", qc.exists())
if qc.exists():
    cache = json.loads(qc.read_text())
    hit = [k for k in cache if "sol" in k]
    check("cache keys the resolved model", bool(hit), str(list(cache)))
    if hit:
        reset = cache[hit[0]].get("resets_epoch", 0)
        check("cache carries the reset horizon (≈109h out)",
              reset > time.time() + 100 * 3600, f"reset={reset}")

# ---------- (c) the door refuses a launch on a cache-exhausted model ----------
sys.path.insert(0, str(BUILD.parent.parent))          # plugin dir parent for __init__ import
import importlib.util
spec = importlib.util.spec_from_file_location("wfdoor", BUILD.parent / "__init__.py")
assert spec is not None and spec.loader is not None
door = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(door)
except SystemExit:
    pass  # module-level guards; handler is what we need
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
# TEST-SEATED: the A5 recovery ping must NEVER hit the real core from a test (an
# answering default seat would "recover" the stamp and the refusal would vanish —
# exactly the silent fallback-billing class this test exists to forbid). Recovery
# itself is exercised with stubbed cores in (f).
_real_ping_route_once = door._ping_route_once
_real_ping_reachable = door._ping_reachable
door._ping_route_once = lambda p, m: {"liveness": "unknown"}
door._ping_reachable = lambda m: False
graph = {"name": "fq-refuse", "nodes": [{"id": "x", "type": "agent", "goal": "GO", "model": "sol"}]}
res = door._quota_refusal(graph, cache_path=qc)
check("door refuses exhausted model before any write", res and "sol" in str(res), str(res))
res2 = door._quota_refusal({"name": "n", "nodes": [{"id": "x", "type": "agent", "goal": "GO"}]},
                           cache_path=qc)
check("door never refuses an unpinned node", res2 is None, str(res2))
# A1 (deep review): a DONE node replay-skips and never spawns — its quota-marked
# pin must not refuse the whole submit (the amend path passes the frozen set).
graph_a1 = {"name": "fq-a1", "nodes": [
    {"id": "done1", "type": "agent", "goal": "DONE", "model": "sol"},
    {"id": "live1", "type": "agent", "goal": "GO", "model": "m-live"}]}
res_a1 = door._quota_refusal(graph_a1, cache_path=qc, skip={"done1"})
check("A1: frozen done node on a quota-marked model does not refuse the submit",
      res_a1 is None, str(res_a1))
res_a1b = door._quota_refusal(graph_a1, cache_path=qc)   # no skip = still refuses
check("A1 control: unskipped refusal intact", bool(res_a1b) and "sol" in str(res_a1b), str(res_a1b))

# ---------- (d) A2: _seat_alias_map honours a FOREIGN home ----------
import wf as wfmod2
fh = HOME / "foreign-seat"
fh.mkdir(exist_ok=True)
(fh / "config.yaml").write_text(
    "model:\n  default: qwen38-next\n  aliases:\n    zeta: anthropic/zeta-1\n")
amap = wfmod2._seat_alias_map(fh)
check("A2: a foreign home reads ITS config.yaml (target owns the aliases)",
      amap.get("zeta") == "anthropic/zeta-1", str(amap))
# A2 (runner seat must NOT leak into a foreign read): the runner seat's own alias is
# only visible when home == duckwork_home(); a foreign home never sees it. Both read
# paths (duckwork_cli and the YAML-lite fallback) follow DUCKWORK_HOME live, so stamping
# HOME's config.yaml + env makes HOME the runner seat for this probe.
(HOME / "config.yaml").write_text(
    "model:\n  default: qwen38-next\n  aliases:\n    runneronly: openai/runner-1\n"
    "    sol: openai-codex/gpt-6-sol\n")   # the (c)/(d2) quota model must resolve
os.environ["DUCKWORK_HOME"] = str(HOME)      # duckwork_home() now == HOME
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")  # #71 shelf pin
own = wfmod2._seat_alias_map(HOME)
foreign = wfmod2._seat_alias_map(fh)
check("A2: foreign home never inherits the runner seat's aliases",
      own.get("runneronly") == "openai/runner-1" and "runneronly" not in foreign,
      f"own={own} foreign={foreign}")

# ---------- (d2) A1 end-to-end through act_amend (the review's repro) ----------
# DONE node pins the quota-marked model + a NEW downstream node on a live model:
# the done node replay-skips and never spawns, so the amend must be ACCEPTED.
# (Before the fix act_amend called _quota_refusal without skip=_frozen -> the whole
# amend was refused `route_unavailable at submit — done_node pins ...`.)
os.environ.pop("WF_QUOTA_CACHE", None)     # real cache path under HOME
qc_src = qc if qc.exists() else None       # the (a)-(c) run stamped 'sol' there
real_cache = HOME / "cache" / "workflow-quota-cache.json"
real_cache.parent.mkdir(parents=True, exist_ok=True)
if qc_src is not None:
    real_cache.write_text(qc_src.read_text())
door._ping_route_once = lambda p, m: {"liveness": "unknown"}   # no network
import wfcommon as _wc
rid = "amend-a1-probe"
rd = HOME / "workflows" / rid
(rd / "nodes").mkdir(parents=True, exist_ok=True)
done_node = {"id": "done_node", "type": "agent", "goal": "DONE", "model": "sol"}
old_graph = {"name": "a1", "nodes": [dict(done_node)]}
(rd / "graph.json").write_text(json.dumps(old_graph))
(rd / "nodes" / "done_node.json").write_text(json.dumps(
    {"status": "done", "efp": _wc.efp({done_node["id"]: done_node}, done_node)}))
new_graph = {"name": "a1", "nodes": [dict(done_node),
                                      {"id": "fresh", "type": "agent", "goal": "GO",
                                       "model": "openai/m-live", "after": ["done_node"]}]}
out_a1 = door.act_amend({"run_id": rid, "graph": new_graph, "dry_run": True})
check("A1 e2e: amend with DONE node on quota-marked model + live new node is accepted",
      out_a1.get("error") is None and "route_unavailable" not in json.dumps(out_a1),
      str(out_a1)[:200])
# control: the same submit where done_node is NOT frozen (edit its goal -> it reruns)
# must still refuse — the gate is intact for nodes that actually spawn.
edited = json.loads(json.dumps(new_graph))
edited["nodes"][0]["goal"] = "DONE EDITED"
out_a1c = door.act_amend({"run_id": rid, "graph": edited, "dry_run": True})
check("A1 e2e control: edited (re-running) done node on quota-marked model still refused",
      out_a1c.get("error") and "route_unavailable" in str(out_a1c.get("error"))
      and "sol" in str(out_a1c.get("error")), str(out_a1c)[:200])

# ---------- (e) minute horizons are minutes, not the 6h default ----------
qc2 = HOME / "quota-cache-min.json"
if qc2.exists(): qc2.unlink()
os.environ["WF_QUOTA_CACHE"] = str(qc2)
wfmod2._quota_note("m-min", "Provider said: HTTP 429: usage limit reached, resets in ~30 minutes")
stamp = json.loads(qc2.read_text())["m-min"]
check("minute horizon lands ~30min out (not the 6h default)",
      20 * 60 < stamp["resets_epoch"] - time.time() < 45 * 60,
      f"{stamp['resets_epoch'] - time.time():.0f}s")

# ---------- (f) A5: provider-less recovery ping clears the stamp ----------
# (f) exercises the REAL _ping_route_once/_ping_reachable against a stubbed
# call_llm — undo the test-seating stubs from (c).
door._ping_route_once = _real_ping_route_once
door._ping_reachable = _real_ping_reachable
qc3 = HOME / "quota-cache-restore.json"
qc3.write_text(json.dumps({"m-recover": {"resets_epoch": time.time() + 3600,
                                          "at": time.time(), "marker": "x"}}))
os.environ.pop("WF_QUOTA_CACHE", None)     # non-offline seat -> the ping path runs
graph_a5 = {"name": "a5", "nodes": [{"id": "y", "type": "agent", "goal": "GO",
                                      "model": "m-recover"}]}
_real_import = door._import_call_llm
door._import_call_llm = lambda: (_ for _ in ()).throw(ImportError("no core"))
try:
    res_ref = door._quota_refusal(graph_a5, cache_path=qc3)      # core unimportable
    check("A5 control: unimportable core keeps the refusal (missing evidence)",
          bool(res_ref) and "m-recover" in str(res_ref), str(res_ref))
finally:
    door._import_call_llm = _real_import
# answered ping whose RECORDED MODEL is the stamped one = reachability -> recovery
class _OK:
    def __call__(self, task=None, provider=None, model=None, messages=None,
                 max_tokens=None, timeout=None, route_info=None, **kw):
        if route_info is not None:
            route_info.update({"provider": "seat-lane", "model": str(model)})
        return "pong"
door._import_call_llm = lambda: _OK()
try:
    res_ok = door._quota_refusal(graph_a5, cache_path=qc3)
    check("A5: provider-less stamp RECOVERS on an answered same-model ping",
          res_ok is None and "m-recover" not in json.loads(qc3.read_text()),
          f"{res_ok} cache={qc3.read_text() if qc3.exists() else None}")
    # fallback-ladder answer (recorded model != stamped) proves nothing -> still refused
    qc3.write_text(json.dumps({"m-recover": {"resets_epoch": time.time() + 3600,
                                             "at": time.time(), "marker": "x"}}))
    class _LADDER(_OK):
        def __call__(self, *a, route_info=None, **kw):
            if route_info is not None:
                route_info.update({"provider": "fallback_chain[0](other)",
                                   "model": "seat-fallback"})
            return "pong"
    door._import_call_llm = lambda: _LADDER()
    res_bad = door._quota_refusal(graph_a5, cache_path=qc3)
    check("A5: a fallback-ladder answer never recovers (wrong_route proves nothing)",
          bool(res_bad) and "m-recover" in str(res_bad), str(res_bad))
finally:
    door._import_call_llm = _real_import

print("ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
