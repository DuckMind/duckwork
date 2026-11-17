"""P4 + P1 (blind-jury form, 2026-09-23): machine-answered gates and blocked_by.

gate.wait = {wait_s?, until_argv?, every_s?, timeout_s?} parks the run at zero tokens;
timer = wait_s alone; check = until_argv re-run every every_s until exit 0; timeout fails
the gate with its last stdout/stderr tail as output (usable via inputs downstream).
A human `release` pre-empts a park. status shows pending nodes' blocked_by (nearest
unfinished ancestors + state) and a parked gate's parked{kind, attempt, last_exit,...}.
Real runner + fake duckwork; nothing mocked inside the engine."""
import json, os, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home8"
if home.exists():
    import shutil; shutil.rmtree(home)
home.mkdir()
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
(home / "config.yaml").write_text("model:\n  default: seat-default\n")
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402
sys.modules.pop("duckwork_cli.config", None)
import importlib.util
spec = importlib.util.spec_from_file_location("door8", BUILD / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1; print("PASS", msg)

fake = str(HERE / "fake")
runs = home / "workflows"; runs.mkdir()
ENV = {**os.environ, "DUCKWORK_HOME": str(home), "WF_RUNS_ROOT": str(runs), "FAKE_LOG": str(home / "fake.log"), "FAKE_PROMPT_LOG": str(home / "prompts.log")}

def mkrun(name, graph):
    run = runs / f"20990101-0000{len(list(runs.iterdir())):02d}-{name}"
    (run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"name": name, "duckwork_bin": fake, "concurrency": 4,
                                              "node_timeout": 30, "started": "2099-01-01T00:00:00+00:00"}))
    return run

def runner(run, timeout=120):
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run.name],
                          capture_output=True, text=True, timeout=timeout, env=ENV)

def events(run):
    return [json.loads(l) for l in (run / "events.jsonl").read_text().splitlines()]

# --- (1) validator: grammar is closed ---
V = lambda nodes: wfcommon.validate_graph(nodes)
base = [{"id": "a", "type": "agent", "goal": "OK"}]
check(V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"wait_s": 1}}]) is None, "timer gate validates")
check(V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"until_argv": ["true"], "every_s": 1}}]) is None, "check gate validates")
check("only gate nodes take wait" in (V([{"id": "a", "type": "agent", "goal": "OK", "wait": {"wait_s": 1}}]) or ""), "agent node cannot take wait")
check("needs wait_s and/or until_argv" in (V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"every_s": 5}}]) or ""), "wait needs a timer or a check")
check("unknown key 'cmd'" in (V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"cmd": "ls"}}]) or ""), "unknown wait key rejected (no shell strings)")
check("until_argv must be a non-empty list" in (V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"until_argv": "pg_isready -h db"}}]) or ""), "until_argv string form rejected (argv only)")
check("timeout_s must be a number" in (V(base + [{"id": "g", "type": "gate", "after": ["a"], "wait": {"wait_s": 1, "timeout_s": 0}}]) or ""), "timeout_s bounded")

# --- (2) timer gate: parks, releases by itself, downstream runs ---
g = {"name": "timer", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "bake", "type": "gate", "after": ["a"], "wait": {"wait_s": 2}},
    {"id": "b", "type": "agent", "after": ["bake"], "goal": "OK"}]}
run = mkrun("timer", g)
t0 = time.time(); p = runner(run); dt = time.time() - t0
ev = events(run)
names = [e["event"] for e in ev]
check("gate.parked" in names and "gate.released" in names, "timer gate parked then released")
rel = next(e for e in ev if e["event"] == "gate.released" and e.get("by"))
check(rel["by"] == "timer", "released by timer, not a human")
st = wfcommon.run_state(run)
check(st["status"] == "done" and st["nodes"]["b"]["status"] == "done", "downstream node ran after the timer")
check(dt >= 2.0, f"actually waited (took {dt:.1f}s)")
ans = json.load(open(run / "gates" / "bake.json"))
check(ans.get("_machine") is True and ans["answer"] == "timer" and ans["_def"] == wfcommon.efp({n["id"]: n for n in g["nodes"]}, g["nodes"][1]), "answer file is efp-stamped and marked machine")
argv_log = (home / "fake.log").read_text() if (home / "fake.log").exists() else ""
check("bake" not in argv_log, "no child session was spawned for the gate (zero tokens)")

# --- (3) check gate: passes on attempt 3; last tail becomes the gate's output ---
counter = home / "counter"
script = home / "check.sh"
script.write_text(f"#!/bin/sh\nn=$(cat {counter} 2>/dev/null || echo 0); n=$((n+1)); echo $n > {counter}\necho \"attempt $n\" >&2\n[ $n -ge 3 ]\n")
script.chmod(0o755)
g = {"name": "check", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "ready", "type": "gate", "after": ["a"], "wait": {"until_argv": [str(script)], "every_s": 0.5, "timeout_s": 30}},
    {"id": "b", "type": "agent", "after": ["ready"], "goal": "OK", "inputs": ["ready"]}]}
run = mkrun("check", g)
p = runner(run)
ev = events(run)
rel = next((e for e in ev if e["event"] == "gate.released" and e.get("by") == "check"), None)
check(rel is not None and rel["attempt"] == 3, f"check gate released on attempt 3 (got {rel})")
st = wfcommon.run_state(run)
check(st["status"] == "done", "run completed after the check passed")
gate_rec = json.load(open(run / "nodes" / "ready.json"))
check(gate_rec["output"]["last_exit"] == 0 and "attempt 3" in gate_rec["output"]["stderr_tail"], "gate output carries last exit + stderr tail")
prompt = (home / "prompts.log").read_text()
check("## Inputs" in prompt and "attempt 3" in prompt, "downstream node received the gate's tail via inputs")

# --- (4) check gate that never passes: times out, fails the gate, run fails ---
g = {"name": "tmo", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "never", "type": "gate", "after": ["a"], "wait": {"until_argv": ["false"], "every_s": 0.3, "timeout_s": 1.5}},
    {"id": "b", "type": "agent", "after": ["never"], "goal": "OK"}]}
run = mkrun("tmo", g)
p = runner(run)
st = wfcommon.run_state(run)
check(st["status"] == "failed" and st["nodes"]["never"]["status"] == "failed", "timed-out check fails the gate and the run")
rec = json.load(open(run / "nodes" / "never.json"))
check("timed out" in rec["error"] and rec["output"]["attempt"] >= 3 and rec["output"]["last_exit"] == 1, f"failure record: {rec['error']} / attempts={rec['output']['attempt']}")
check(st["nodes"]["b"]["status"] == "pending" and st["nodes"]["b"]["blocked_by"] == ["never: failed"], "P1: downstream blocked_by names the failed gate")
check("WORKFLOW_FAILED" in p.stdout, "runner emitted the failed marker")

# --- (5) blocked_by vocabulary + parked self-explanation while a park is live ---
g = {"name": "live", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "hold", "type": "gate", "after": ["a"], "wait": {"until_argv": ["false"], "every_s": 0.3, "timeout_s": 20}},
    {"id": "b", "type": "agent", "after": ["hold"], "goal": "OK"},
    {"id": "c", "type": "agent", "after": ["b"], "goal": "OK"}]}
run = mkrun("live", g)
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", run.name], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
deadline = time.time() + 20
while time.time() < deadline:
    st = wfcommon.run_state(run)
    if st["nodes"]["hold"].get("parked", {}).get("attempt", 0) >= 2:
        break
    time.sleep(0.2)
pk = st["nodes"]["hold"]["parked"]
check(pk["kind"] == "check" and pk["attempt"] >= 2 and pk["last_exit"] == 1, f"parked gate self-explains: {pk}")
check(st["status"] == "running" and st["held_gate"] is None, "a parked machine gate is 'running', never 'held' (no popup)")
check(st["nodes"]["b"]["blocked_by"] == [f"hold: parked (check, attempt {pk['attempt']})"] or st["nodes"]["b"]["blocked_by"][0].startswith("hold: parked (check, attempt"), f"blocked_by shows the park: {st['nodes']['b']['blocked_by']}")
check(st["nodes"]["c"]["blocked_by"] == ["b: pending"], "blocked_by is NEAREST ancestors only (c sees b, not hold)")
out = door.act_status({"run_id": run.name})
check(out["nodes"]["b"]["blocked_by"] and out["nodes"]["hold"]["parked"]["attempt"] >= 2, "act_status surfaces blocked_by + parked")
# human pre-empts the park
res = door._release_core(run, "hold", "go")
check(res.get("ok") is True, "human release accepted while parked")
proc.wait(timeout=30)
st = wfcommon.run_state(run)
check(st["status"] == "done", "human answer pre-empted the park; run finished")
ev = events(run)
check(not any(e["event"] == "gate.wait_timeout" for e in ev), "no timeout fired after pre-empt")

# --- (6) stop while parked ---
g = {"name": "stopme", "nodes": [
    {"id": "a", "type": "agent", "goal": "OK"},
    {"id": "hold", "type": "gate", "after": ["a"], "wait": {"wait_s": 30}},
    {"id": "b", "type": "agent", "after": ["hold"], "goal": "OK"}]}
run = mkrun("stopme", g)
proc = subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", run.name], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
deadline = time.time() + 15
while time.time() < deadline and not (run / "gates" / "hold.parked.json").exists():
    time.sleep(0.2)
t0 = time.time()
(run / "stop.request").write_text("")
proc.wait(timeout=15)
check(time.time() - t0 < 6, f"stop honoured within the park loop ({time.time()-t0:.1f}s, not 30s)")
check(wfcommon.run_state(run)["nodes"]["b"]["status"] == "pending", "downstream did not run after stop")

# --- (7) false `when` on a wait gate prunes by default; explicit pass opts out ---
for policy in (None, "pass"):
    gate = {"id": "hold", "type": "gate", "after": ["a"], "when": "out.a.missing == 'x'", "wait": {"wait_s": 30}}
    if policy is not None:
        gate["on_skip"] = policy
    g = {"name": "whenskip", "nodes": [
        {"id": "a", "type": "agent", "goal": "OK"}, gate,
        {"id": "b", "type": "agent", "after": ["hold"], "goal": "OK"}]}
    run = mkrun(f"whenskip-{policy or 'default'}", g)
    t0 = time.time(); runner(run); dt = time.time() - t0
    expected = policy or "prune"
    statuses = {k: v["status"] for k, v in wfcommon.run_state(run)["nodes"].items()}
    check(any(e["event"] == "gate.skipped" and e.get("on_skip") == expected for e in events(run))
          and statuses["hold"] == ("skipped" if expected == "prune" else "done")
          and statuses["b"] == ("skipped" if expected == "prune" else "done")
          and ((run / "logs" / "b.a0.log").exists() == (expected == "pass")) and dt < 10,
          f"false when on wait gate {expected} saves and emits consistent policy, without parking ({dt:.1f}s)")

print(f"ALL PASS ({ok})")
