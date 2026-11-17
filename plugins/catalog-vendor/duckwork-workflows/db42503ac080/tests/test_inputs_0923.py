"""v0.7.3 `inputs:` node field: runner injects a `## Inputs` section (one labelled fenced
json block per ref, resolved via resolve_ref against committed outputs, capped 12000 chars
with a truncation marker), an unresolvable ref FAILS the node at spawn with the exact error,
validate_graph rejects non-list / non-ancestor-head / gate-with-inputs, and inputs are part
of the def so the efp moves when they change."""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home8"
if home.exists():
    shutil.rmtree(home)
home.mkdir()
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1; print("PASS", msg)

fake = str(HERE / "fake")

def run_graph(name, graph, seed=None):
    """Drop a run dir, optionally pre-commit nodes/<id>.json records, run wf.py to
    completion; return (run_dir, prompts, stdout+stderr). prompts = full prompts the
    fake children received (via FAKE_PROMPT_LOG), in spawn order."""
    runs = home / "workflows"; runs.mkdir(exist_ok=True)
    run = runs / name
    shutil.rmtree(run, ignore_errors=True)
    (run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"name": name, "duckwork_bin": fake,
                                              "concurrency": 4, "node_timeout": 30,
                                              "started": "2099-01-01T00:00:00+00:00"}))
    for nid, rec in (seed or {}).items():
        byid = {n["id"]: n for n in graph["nodes"]}
        (run / "nodes" / f"{nid}.json").write_text(
            json.dumps({**rec, "efp": wfcommon.efp(byid, byid[nid]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))
    plog = home / f"{name}.prompts.log"
    if plog.exists():
        plog.unlink()
    p = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", name],
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "DUCKWORK_HOME": str(home), "WF_RUNS_ROOT": str(runs),
                            "FAKE_LOG": str(home / f"{name}.fake.log"),
                            "FAKE_PROMPT_LOG": str(plog)})
    prompts = plog.read_text().split("\n=====PROMPT=====\n")[1:] if plog.exists() else []
    return run, prompts, p.stdout + p.stderr

# --- (1) injection present + labelled (whole output + dotted path) ---
g1 = {"name": "inj", "nodes": [
    {"id": "gen", "type": "agent", "goal": "LIST:"},
    {"id": "use", "type": "agent", "after": ["gen"], "goal": "USE",
     "inputs": ["gen", "gen.result.1"]}]}
run, prompts, out = run_graph("20990101-000001-inj", g1)
check(len(prompts) == 2, f"solo+use spawned ({out[-120:]})")
pr = prompts[1]
check("## Inputs" in pr, "downstream prompt carries a ## Inputs section")
check("Finish your answer" in pr and pr.find("## Inputs") < pr.find("Finish your answer"),
      "## Inputs lands before the output contract")
check("\ngen\n```json\n" in pr, "block labelled by the ref string ('gen')")
check("\ngen.result.1\n```json\n" in pr, "dotted-path ref gets its own labelled block")
check(json.loads(pr.split("gen.result.1\n```json\n")[1].split("\n```")[0]) == "b",
      "dotted path resolves to the exact committed value")
check(json.loads((run / "nodes" / "use.json").read_text())["status"] == "done",
      "node with inputs commits done")

# --- (2) truncation marker at the 12000-char cap ---
g2 = {"name": "trunc", "nodes": [
    {"id": "big", "type": "agent", "goal": "unused (seeded)"},
    {"id": "down", "type": "agent", "after": ["big"], "goal": "DOWN", "inputs": ["big"]}]}
run, prompts, out = run_graph("20990101-000002-trunc", g2,
                              seed={"big": {"status": "done", "output": {"blob": "y" * 20000}}})
pr = prompts[0]
n = len(json.dumps({"blob": "y" * 20000}, ensure_ascii=False, indent=2, default=str))
check(f"…[truncated {n - 12000} chars; full record at nodes/big.json]" in pr,
      "oversized input truncated with exact marker (chars + nodes/big.json path)")
check(11000 < pr.count("y") < 20000, "block actually capped at 12000 chars")

# --- (3) unresolvable ref => node FAILS at spawn, never a silent empty spawn ---
g3 = {"name": "unres", "nodes": [
    {"id": "gen", "type": "agent", "goal": "LIST:"},
    {"id": "down", "type": "agent", "after": ["gen"], "goal": "DOWN", "inputs": ["gen.nope"]}]}
run, prompts, out = run_graph("20990101-000003-unres", g3)
rec = json.loads((run / "nodes" / "down.json").read_text())
check(rec["status"] == "failed" and rec["error"] == "inputs: gen.nope not resolvable",
      "unresolvable ref fails the node with the exact error string")
check(not any("DOWN" in p for p in prompts), "failed-at-spawn node never launched a child")
check("WORKFLOW_FAILED" in out, "run surfaces the failure")

# --- (4) fan-out: node-level inputs, identical for every item ---
g4 = {"name": "fo", "nodes": [
    {"id": "gen", "type": "agent", "goal": "LIST:"},
    {"id": "fan", "type": "agent", "after": ["gen"],
     "fanout": {"items": ["p", "q"], "goal": "F {item}"}, "inputs": ["gen.result"]}]}
run, prompts, out = run_graph("20990101-000004-fo", g4)
with_in = [p for p in prompts if "\ngen.result\n```json\n" in p]  # header, not the seeded value
check(len(with_in) == 2, "every fan-out item carries the ## Inputs section")
check(with_in[0].split("## Inputs")[1] == with_in[1].split("## Inputs")[1],
      "inputs section is identical for every item (node-level)")

# --- (5) validate_graph: shape + ancestry rules ---
check(wfcommon.validate_graph([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "b", "type": "agent", "after": ["a"], "goal": "y", "inputs": ["a"]},
    {"id": "c", "type": "agent", "after": ["b"], "goal": "z",
     "inputs": ["a.items", "b"]}],
) is None, "validator accepts ancestor + transitive-ancestor refs")
e = wfcommon.validate_graph([{"id": "a", "type": "agent", "goal": "x"},
                             {"id": "b", "type": "agent", "after": ["a"], "goal": "y", "inputs": "a"}])
check(e and "inputs" in e and "node b" in e, f"non-list inputs rejected naming the offender: {e}")
e = wfcommon.validate_graph([{"id": "a", "type": "agent", "goal": "x"},
                             {"id": "b", "type": "agent", "after": ["a"], "goal": "y", "inputs": ["a", 7]}])
check(e and "inputs" in e, f"non-string ref rejected: {e}")
e = wfcommon.validate_graph([{"id": "a", "type": "agent", "goal": "x"},
                             {"id": "sib", "type": "agent", "goal": "x"},
                             {"id": "b", "type": "agent", "after": ["a"], "goal": "y", "inputs": ["sib"]}])
check(e and "sib" in e and "b" in e, f"non-ancestor head rejected naming offender+ref: {e}")
e = wfcommon.validate_graph([{"id": "a", "type": "agent", "goal": "x", "inputs": ["a"]}])
check(e and "inputs" in e, f"self-reference (not a strict ancestor) rejected: {e}")
e = wfcommon.validate_graph([{"id": "a", "type": "agent", "goal": "x"},
                             {"id": "g", "type": "gate", "after": ["a"], "question": "q",
                              "options": ["y"], "inputs": ["a"]}])
check(e and "gates cannot have inputs" in e, f"gate with inputs rejected: {e}")

# --- (6) efp: inputs are part of the def -> fingerprint moves (replay-skip invalidates) ---
by1 = {"a": {"id": "a", "type": "agent", "goal": "x"},
       "b": {"id": "b", "type": "agent", "after": ["a"], "goal": "y", "inputs": ["a"]}}
by2 = {k: (dict(v, inputs=["a.items"]) if k == "b" else dict(v)) for k, v in by1.items()}
check(wfcommon.efp(by1, by1["b"]) != wfcommon.efp(by2, by2["b"]),
      "efp changes when inputs change (inputs ride def_hash)")
check(wfcommon.def_hash(by1["b"]) != wfcommon.def_hash(by2["b"]),
      "def_hash itself covers the inputs field")

print(f"\nALL PASS ({ok})")
