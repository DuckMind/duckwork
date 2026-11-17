#!/usr/bin/env python3
"""est-2ek.1.165: a harvested `partial` node's DECLARED unfinished steps surface
as a structured `remaining` list — never prose the scheduler must re-parse.

Shape (spool key 2120bb829090ebf7): a close node hit max_turns mid-tail, the
#4 harvest committed status 'partial' (good) — but the unfinished tail step had
no owner afterwards because it lived only in prose. Law here: the harvest seam
parses the child's declared `## Remaining` block (markdown heading, one step per
bullet, up to the next heading/fence) into record["remaining"]; status/wait pass
it through VERBATIM. Honest absence: no declared block -> [] (empty list is the
fact, absence of the node is not).

RED with canned partial output (FAKE_MODE=partial_remaining / partial_noremaining:
a valid fenced answer rode stdout while the child died rc!=0 — the harvest shape).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))

def _load_iso762():
    # est-2ek.1.762: shared launch-env pin helper, exec-loaded by file path
    # (repo convention — a top-level import of a tests/fixtures module would
    # break the test_packaging import-closure from the unpacked package root).
    spec = importlib.util.spec_from_file_location(
        "wf_spawn_isolation_762", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
pin_env = _load_iso762().pin_env

HOME = BUILD / "home_165"
env = pin_env(dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake_165.log")),
              HOME / "workflows", home=HOME)
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

def mk(run_id, nodes, extra=None):
    r = RUNS / run_id
    if r.exists():
        shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    cfg = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 60}
    cfg.update(extra or {})
    (r / "run.json").write_text(json.dumps(cfg))
    return r

def wf(run_id, extra_env=None):
    e = dict(env)
    e.update(extra_env or {})
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=e, capture_output=True, text=True, timeout=180)
    return p.stdout.strip()

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
RUNS = HOME / "workflows"
RUNS.mkdir()
# #71 harness law (same as asks166): the in-process door resolves runs through the
# ONE resolver — pin WF_RUNS_ROOT to the scratch root so act_status reads the very
# dir the runner wrote (assertions unchanged; 166 arms through the same door).
os.environ["WF_RUNS_ROOT"] = str(RUNS)

# ---- (1) RED: harvested partial with a declared Remaining block ----
r = mk("asks165-rem", [{"id": "close", "type": "agent",
                        "goal": "PARTIALTEST roll the tail close asks165-rem"}])
out = wf("asks165-rem", {"FAKE_MODE": "partial_remaining"})
rec = json.loads((r / "nodes" / "close.json").read_text())
check("(1) harvest committed status partial", rec.get("status") == "partial",
      json.dumps({k: rec.get(k) for k in ("status", "error_class")}))
check("(1) record carries structured remaining (declared steps, in order)",
      rec.get("remaining") == ["roll seat plugin", "CLI bake"],
      json.dumps(rec.get("remaining")))

# door status must pass the structured list through (wait shares act_status)
spec = importlib.util.spec_from_file_location("asks165_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)
st = door.act_status({"run_id": "asks165-rem"})
node_st = (st.get("nodes") or {}).get("close") or {}
check("(1) status surfaces structured remaining",
      node_st.get("remaining") == ["roll seat plugin", "CLI bake"],
      json.dumps({k: node_st.get(k) for k in ("status", "remaining")}))

# ---- (2) honest absence: harvested partial with NO declared block -> [] ----
r2 = mk("asks165-none", [{"id": "close", "type": "agent",
                          "goal": "PARTIALTEST asks165-none no declared block"}])
out2 = wf("asks165-none", {"FAKE_MODE": "partial_noremaining"})
rec2 = json.loads((r2 / "nodes" / "close.json").read_text())
check("(2) no declared block -> remaining == [] (the empty fact, not absence)",
      rec2.get("status") == "partial" and rec2.get("remaining") == [],
      json.dumps({k: rec2.get(k) for k in ("status", "remaining")}))
st2 = door.act_status({"run_id": "asks165-none"})
check("(2) status passes [] through",
      (st2.get("nodes") or {}).get("close", {}).get("remaining") == [],
      json.dumps((st2.get("nodes") or {}).get("close")))

# ---- (3) a DONE node's remaining is not fabricated: no key on healthy commits ----
r3 = mk("asks165-done", [{"id": "a", "type": "agent", "goal": "GO asks165-done"}])
out3 = wf("asks165-done")
rec3 = json.loads((r3 / "nodes" / "a.json").read_text())
check("(3) healthy done commit carries no remaining key (derive-only)",
      rec3.get("status") == "done" and "remaining" not in rec3,
      json.dumps({k: rec3.get(k) for k in ("status", "remaining")}))

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
