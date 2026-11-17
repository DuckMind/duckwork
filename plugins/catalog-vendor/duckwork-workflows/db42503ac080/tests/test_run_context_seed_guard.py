#!/usr/bin/env python3
"""Door-transport guard: run_context must never silently route a map to seed.

Clean-room repro: handle(action=run, run_context=json.dumps({"symptom": ...}))
— a tool-call transport that string-encodes the map — took the seed branch,
which is append-only, so the persisted graph.json kept literal {run.KEY} refs
and seats billed on unsubstituted templates. Same failure class as the merged
#7 brace-guard work on this binding surface: reject before any run write and
name the offending node/key. A seed that leaves {run.KEY} refs dangling is
broken regardless of where the string came from, so the seed branch refuses
them outright; the map branch is unchanged.
"""
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent if BUILD.name == "tests" else BUILD
HOME = BUILD / "home_seed_guard"
shutil.rmtree(HOME, ignore_errors=True)
os.environ["DUCKWORK_HOME"] = str(HOME)
# #71 law: the runs root must be pinned beside the home sandbox — a context-local
# home override outranks DUCKWORK_HOME in get_duckwork_home(); WF_RUNS_ROOT is checked first.
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
spec = importlib.util.spec_from_file_location("guard_door", str(ROOT / "__init__.py"))
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
spawns = []
hw._spawn_runner = lambda r: spawns.append(r)   # door-side only, mirrors test_run_binding
failures = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else " " + str(detail)))
    if not ok:
        failures.append(name)
def state():
    runs = sorted(os.listdir(HOME / "workflows")) if (HOME / "workflows").exists() else []
    return (len(spawns), [r for r in runs if r != "library"])
def run(graph=None, binding=None, **extra):
    args = {"action": "run", **extra}
    if graph is not None:
        args["graph"] = graph
    if binding is not None:
        args["run_context"] = binding
    return json.loads(hw.handle(args))
def snapshot(reply):
    return json.loads((HOME / "workflows" / reply["run_id"] / "graph.json").read_text())

ref_graph = {"name": "encoded-map", "nodes": [
    {"id": "first", "type": "agent", "goal": "Symptom: {run.symptom}. Artifact: {run.artifact}."}]}

# 1. the defect: a JSON-encoded map of bindings must reject, atomically.
before = state()
r = run(graph=ref_graph, binding=json.dumps({"symptom": "S", "artifact": "A"}))
check("JSON-encoded map binding rejects with error (no silent seed)",
      "run_context" in r.get("error", ""), r)
check("rejection is atomic: no spawn, no run write", state() == before, (before, state()))

# 2. seed-shaped prose keeps working untouched (no contract break).
r = run(graph={"name": "plain-seed", "nodes": [{"id": "a", "type": "agent", "goal": "do x"}]},
        binding="context notes for the run")
check("plain string seed still launches", "run_id" in r and
      "context notes" in snapshot(r)["nodes"][0].get("context", ""), r)
if "run_id" in r:
    hw.act_stop({"run_id": r["run_id"]})

# 3. leftover {run.*} in a seed launch is broken by construction — the seed
#    branch never substitutes — so it rejects too, naming node and key.
before = state()
r = run(graph=ref_graph, binding="just a seed sentence")
check("seed leaving {run.KEY} refs rejects before write",
      "{run.symptom}" in r.get("error", "") and "first" in r.get("error", "") and
      state() == before, (r, state()))

# 4. dict binding path unchanged: still binds, literals gone.
r = run(graph=ref_graph, binding={"symptom": "S", "artifact": "A"})
check("dict binding still substitutes", "run_id" in r and
      snapshot(r)["nodes"][0]["goal"] == "Symptom: S. Artifact: A.", r)
if "run_id" in r:
    hw.act_stop({"run_id": r["run_id"]})

# 5. a graph with NO {run.*} refs takes the encoded map as literal seed text
#    only if it is not JSON at all; JSON-object strings reject on the transport
#    mistake itself (the door cannot mean a seed by a decodable map).
r = run(graph={"name": "no-refs", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]},
        binding=json.dumps({"note": "hello"}))
check("JSON-object string rejects even without refs", "run_context" in r.get("error", ""), r)

# 6. non-object JSON prose (a number-ish/`key=a1` seed) is not a map — untouched.
r = run(graph={"name": "kv-seed", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]},
        binding="key=a1")
check("non-JSON seed string still launches", "run_id" in r, r)
if "run_id" in r:
    hw.act_stop({"run_id": r["run_id"]})

print("== 0 failures" if not failures else f"== {len(failures)} failures: {failures}")
sys.exit(1 if failures else 0)
