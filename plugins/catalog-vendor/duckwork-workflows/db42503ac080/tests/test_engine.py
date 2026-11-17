#!/usr/bin/env python3
"""Engine test: sequential, fanout, gate hold/release/resume, replay-skip, steering, amend, failure, stop."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home"
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake.log"))
FAKE = str(BUILD / "fake")
ok = True

def sh(*cmd):
    return subprocess.run(cmd, env=env, capture_output=True, text=True)

def mk(run_id, nodes, name="t"):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
    return r

def answer(r, gid, val):
    """Stamp the gate answer with the CURRENT gate efp, like the door's release does."""
    import sys; sys.path.insert(0, str(BUILD.parent))
    import wfcommon
    g = {n["id"]: n for n in json.loads((r / "graph.json").read_text())["nodes"]}
    (r / "gates" / f"{gid}.json").write_text(json.dumps({"answer": val, "_def": wfcommon.efp(g, g[gid]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))

def wf(run_id):
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=120)
    return p.stdout.strip()

def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and cond

(BUILD / "fake.log").write_text("")

# ---- 1. linear: plan -> fanout -> synth ----
nodes = [
    {"id": "plan", "type": "agent", "goal": "LIST: make a list"},
    {"id": "fan", "type": "agent", "after": ["plan"], "fanout": {"items_from": "plan.result", "goal": "process {item}"}},
    {"id": "gate1", "type": "gate", "after": ["fan"], "question": "proceed?", "options": ["yes", "no"]},
    {"id": "synth", "type": "agent", "after": ["gate1"], "goal": "combine"},
]
r = mk("t1", nodes, "linear+gate")
out = wf("t1")
check("holds at gate", out.startswith("WORKFLOW_HELD t1 gate1"), out)
check("plan+fan done, not synth", (r / "nodes/plan.json").exists() and (r / "nodes/fan.json").exists()
      and not (r / "nodes/synth.json").exists())
n_before = len((BUILD / "fake.log").read_text().splitlines())
# release gate, resume
answer(r, "gate1", "yes")
out = wf("t1")
n_after = len((BUILD / "fake.log").read_text().splitlines())
check("done after gate release", out.startswith("WORKFLOW_DONE t1"), out)
check("replay-skip: only synth spawned on resume (1 spawn)", n_after - n_before == 1, f"delta={n_after-n_before}")
check("summary.md exists w/ synth", (r / "summary.md").exists() and "synth" in (r / "summary.md").read_text())
check("gate passthrough in synth ctx not required; gate node done",
      json.loads((r / "nodes/gate1.json").read_text())["output"]["answer"] == "yes")

# ---- 2. steering into a pending node ----
r = mk("t2", nodes, "steer")
(r / "inbox.jsonl").write_text(json.dumps({"node": "synth", "text": "STEER-alpha"}) + "\n")
wf("t2")                                  # holds at gate
answer(r, "gate1", "yes")
out = wf("t2")
check("steering reached late node", "DONE" in out and
      json.loads((r / "nodes/synth.json").read_text())["output"].get("steered") == "alpha", out)

# ---- 3. graph amendment invalidates downstream done-results ----
r = mk("t3", nodes, "amend")
wf("t3")
answer(r, "gate1", "yes")
wf("t3")                                  # done
g = json.loads((r / "graph.json").read_text())
g["nodes"][3]["goal"] = "combine DIFFERENTLY"   # amend synth
g["nodes"][2]["options"] = ["yes"]              # touch gate def -> def_hash changes
(r / "graph.json").write_text(json.dumps(g))
(r / "gates/gate1.json").unlink()
n_before = len((BUILD / "fake.log").read_text().splitlines())
out = wf("t3")
n_after = len((BUILD / "fake.log").read_text().splitlines())
check("amended graph re-holds at changed gate", "HELD t3 gate1" in out, out)
check("plan/fan NOT re-spawned (0 spawns to reach gate)", n_after - n_before == 0, f"delta={n_after-n_before}")
answer(r, "gate1", "yes")
out = wf("t3")
outp = json.loads((r / "nodes/synth.json").read_text())["output"]
check("amended synth re-ran (goal reflects new def)",
      "DIFFERENTLY" in json.dumps(outp), json.dumps(outp))

# ---- 4. failure -> retry(1) -> failed -> resume after amendment ----
r = mk("t4", [{"id": "a", "type": "agent", "goal": "FAILME please"},
              {"id": "b", "type": "agent", "after": ["a"], "goal": "after a"}], "fail")
out = wf("t4")
rec = json.loads((r / "nodes/a.json").read_text())
spawns_a = sum(1 for l in (BUILD / "fake.log").read_text().splitlines() if "FAILME" in l)
check("failed node fails run", out.startswith("WORKFLOW_FAILED t4 (a)"), out)
check("exactly 1 retry for a", spawns_a == 2, f"spawns={spawns_a}")
check("downstream b never spawned", not (r / "nodes/b.json").exists())
g = json.loads((r / "graph.json").read_text()); g["nodes"][0]["goal"] = "fixed goal"
(r / "graph.json").write_text(json.dumps(g))
out = wf("t4")
check("amend + resume recovers past failure", out.startswith("WORKFLOW_DONE t4"), out)

# ---- 5. conditional gate skip ----
r = mk("t5", [{"id": "a", "type": "agent", "goal": "ok"},
              {"id": "g", "type": "gate", "after": ["a"], "question": "q", "when": "out.a.flag == True"},
              {"id": "b", "type": "agent", "after": ["g"], "goal": "after g"}], "cond-gate")
out = wf("t5")
check("gate with false 'when' auto-skips to done", out.startswith("WORKFLOW_DONE t5")
      and json.loads((r / "nodes/g.json").read_text())["output"]["gate"] == "skipped", out)

# ---- 6. stop ----
r = mk("t6", nodes, "stop")
(r / "stop.request").write_text("1")
out = wf("t6")
check("stop.request honored", out.startswith("WORKFLOW_STOPPED t6"), out)

# ---- 7. fanout over dict items with field refs ----
r = mk("t7", [{"id": "seed", "type": "agent", "goal": "count to 3"},
              {"id": "f", "type": "agent", "after": ["seed"],
               "fanout": {"items": [{"name": "x"}, {"name": "y"}], "goal": "handle {name} of {item}"}}], "fan-fields")
out = wf("t7")
check("dict item field substitution", out.startswith("WORKFLOW_DONE t7")
      and sum(1 for l in (BUILD / "fake.log").read_text().splitlines() if "handle x" in l or "handle y" in l) == 2, out)

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
