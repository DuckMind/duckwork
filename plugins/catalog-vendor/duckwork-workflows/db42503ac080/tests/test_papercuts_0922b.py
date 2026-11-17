#!/usr/bin/env python3
"""Papercuts 2026-09-22 round 2 (owner feedback drain, sibling seat):
  3. item.finished carried status only — no reason, no tail, no log path (blind babysitting).
  4. wait timeout=1700 died client-side at the harness's 420s tool deadline — wait must
     self-yield a clean status+note before it.
  5. quorum failure committed nothing recoverable — survivors + per-index reasons now saved.
Engine-driven with the fake duckwork, plus source guards.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
sys.path.insert(0, str(BUILD.parent))
HOME = BUILD / "home6"
os.environ["DUCKWORK_HOME"] = str(HOME)  # door's run_dir()/act_wait() resolve home in-process
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake6.log"))
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

def mk(run_id, nodes, extra=None):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    cfg = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}
    cfg.update(extra or {})
    (r / "run.json").write_text(json.dumps(cfg))
    return r

def wf(run_id):
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=120)
    return p.stdout.strip()

# ---- 3+5: mixed fan-out (1 crash, 1 ok) — events and node rec must carry the truth ----
r = mk("pc2-mixed", [{"id": "f", "type": "agent",
                      "fanout": {"goal": "template", "items": [{"goal": "CRASHME now"}, {"goal": "fine task"}]}}])
out = wf("pc2-mixed")
evs = [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
itm = [e for e in evs if e["event"] == "item.finished"]
check("item.finished x2", len(itm) == 2, str(itm))
bad = next((e for e in itm if e["status"] == "failed"), {})
check("failed item carries error reason", "rc=2" in (bad.get("error") or ""), str(bad))
check("failed item carries output tail", "segfault" in (bad.get("tail") or ""), str(bad))
check("item carries log_path", (bad.get("log_path") or "").endswith("runner.log"), str(bad))
nf = next((e for e in evs if e["event"] == "node.failed"), {})
check("node.failed carries failed_detail", isinstance(nf.get("failed_detail"), list) and nf["failed_detail"][0]["index"] == 0, str(nf))

rec = json.loads((r / "nodes" / "f.json").read_text())
check("failed node names each failure by index", rec["error"].startswith("1/2 items failed: [0]"), rec["error"][:80])
check("survivor output committed on FAILED node (partial credit)",
      len(rec["output"]["items"]) == 1 and rec["output"]["items"][0]["result"] == "ok",
      str(rec["output"]["items"]))
check("all_results kept for postmortem", len(rec["output"]["all_results"]) == 2)

# ---- 5b: quorum slack commits the node with survivors ----
r = mk("pc2-quorum", [{"id": "f", "type": "agent",
                       "fanout": {"goal": "template", "quorum": 1, "items": [{"goal": "CRASHME now"}, {"goal": "fine task"}]}}])
wf("pc2-quorum")
rec = json.loads((r / "nodes" / "f.json").read_text())
check("quorum:1 commits node despite 1 crash", rec["status"] == "done" and rec["output"]["failed_items"] == 1,
      str(rec["status"]))
check("quorum:1 keeps all_results too", len(rec["output"]["all_results"]) == 2)

# ---- 4: wait self-yields under the harness deadline ----
src = (BUILD.parent / "__init__.py").read_text()
check("wait self-yields at a segment below the harness deadline", "seg = min(cap, 330)" in src and "self-yield" in src)
sch = json.loads(json.dumps(__import__("importlib").import_module("__init__").WORKFLOW_SCHEMA))
check("schema documents the self-yield contract", "self-yield" in sch["parameters"]["properties"]["timeout"]["description"].lower())

# functional: REAL wf runner (wf.py subprocess) with a slow child (fake SLEEP) ->
# wait must block to its cap and return a clean status + "wait again" note.
r = mk("pc2-wait", [{"id": "a", "type": "agent", "goal": "SLEEP 30 slow task"}])
runner = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "pc2-wait"],
                          env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)  # let it claim the node and spawn the child
door = __import__("importlib").import_module("__init__")
t0 = time.time()
res = door.act_wait({"run_id": "pc2-wait", "timeout": 3})
dt = time.time() - t0
runner.kill()
check("wait blocks while the real runner is live", isinstance(res, dict) and "status" in res and dt >= 2.5, str(res)[:120] + f" dt={dt:.1f}")
check("wait note tells the parent to call again", "wait again" in (res.get("note") or ""), str(res)[:160])

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
