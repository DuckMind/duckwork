"""00e46adb (spool 5ff2806f359c16a1): a fresh verify node two hops under a go-gate
could not see the gate's committed answer — the binding release ("proceed despite C1,
owner override …") reached only the gate's DIRECT child via the auto parent-injection
loop, so the verify graded the deliberate override as 'C1 NOT met / authority
UNVERIFIED'. Law (build_inputs): every transitive ancestor gate whose answer is
COMMITTED (done via the gate_answer_valid efp law) is injected into every downstream
agent prompt, capped like any auto input; a skipped/unanswered gate has no done
record and injects NOTHING (fail-closed by construction); ids already covered by an
explicit `inputs:` ref or a direct-parent block are never duplicated. Solo graphs
with no released gate gain zero bytes (golden-solo EMPTY is the outer gate).
"""
import importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home19"
if home.exists():
    shutil.rmtree(home)
home.mkdir()
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg} — {detail}"
    ok += 1; print("PASS", msg)

fake = str(HERE / "fake")

def run_graph(name, graph, gate_answers=None, seed=None):
    """Pre-answer gates (valid efp-stamped records in gates/<id>.json), optionally
    pre-commit nodes, run wf.py to completion; return (run_dir, prompts)."""
    runs = home / "workflows"; runs.mkdir(exist_ok=True)
    run = runs / name
    shutil.rmtree(run, ignore_errors=True)
    (run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"name": name, "duckwork_bin": fake,
                                              "concurrency": 4, "node_timeout": 30,
                                              "started": "2099-01-01T00:00:00+00:00"}))
    byid = {n["id"]: n for n in graph["nodes"]}
    for gid, ans in (gate_answers or {}).items():
        rec = {"answer": ans, "_def": wfcommon.efp(byid, byid[gid]),
               "fp_rule_version": wfcommon.FP_RULE_VERSION,
               "at": "2099-01-01T00:00:00+00:00"}
        (run / "gates" / f"{gid}.json").write_text(json.dumps(rec))
    for nid, rec in (seed or {}).items():
        (run / "nodes" / f"{nid}.json").write_text(
            json.dumps({**rec, "efp": wfcommon.efp(byid, byid[nid]),
                        "fp_rule_version": wfcommon.FP_RULE_VERSION}))
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

OVERRIDE = "proceed despite C1 - owner override: ship window closes tonight"

# chain: plan -> go(gate) -> impl -> verify   (verify is TWO hops under the gate)
CHAIN = {"nodes": [
    {"id": "plan", "type": "agent", "goal": "JSON:{\"result\":\"planned\"}"},
    {"id": "go", "type": "gate", "after": ["plan"], "question": "Release?", "options": ["yes", "no"]},
    {"id": "impl", "type": "agent", "after": ["go"], "goal": "implement"},
    {"id": "verify", "type": "agent", "after": ["impl"], "goal": "verify the release decision"},
]}

# --- (1) the incident: verify sees the ancestor gate answer ----------------------
run, prompts, out = run_graph("gatechain", CHAIN, gate_answers={"go": OVERRIDE})
vpr = [p for p in prompts if "verify the release decision" in p]
check(len(vpr) == 1, "verify spawned once", str(len(vpr)))
check(OVERRIDE in vpr[0], "verify prompt carries the ancestor gate's committed answer", out[-400:])
check("(ancestor gate answer)" in vpr[0], "the block is labelled as an ancestor gate answer")

# --- (2) direct child of the gate: ONE block, never duplicated -------------------
ipr = [p for p in prompts if "implement" in p.splitlines()[0] or ("implement" in p and "## Inputs" in p)][0]
check(ipr.count(OVERRIDE) == 1, "direct child impl gets the answer exactly once (no ancestor duplication)")

# --- (3) fail-closed: an unanswered/skipped gate injects nothing ------------------
# when-false gate -> skipped (never done): the downstream agent must NOT gain a gate block.
SKIPG = {"nodes": [
    {"id": "a", "type": "agent", "goal": "JSON:{\"go\":false}"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "Continue?",
     "options": ["yes"], "when": "out.a.go == True", "on_skip": "pass"},
    {"id": "b", "type": "agent", "after": ["g"], "goal": "downstream of a skipped gate"},
]}
run2, prompts2, out2 = run_graph("gate.skip", SKIPG)
bpr = [p for p in prompts2 if "downstream of a skipped gate" in p]
check(len(bpr) == 1, "downstream of skipped gate still runs (non-prune skip)")
check("(ancestor gate answer)" not in bpr[0], "a SKIPPED gate injects no answer block", out2[-300:])

# --- (4) explicit inputs: ref covering the gate head suppresses the auto block ----
EXPL = {"nodes": [
    {"id": "a", "type": "agent", "goal": "JSON:{\"result\":\"planned\"}"},
    {"id": "go", "type": "gate", "after": ["a"], "question": "Release?", "options": ["yes", "no"]},
    {"id": "impl", "type": "agent", "after": ["go"], "goal": "implement", "inputs": ["go.answer"]},
]}
_, prompts3, _ = run_graph("gate.explicit", EXPL, gate_answers={"go": OVERRIDE})
apr = [p for p in prompts3 if "implement" in p]
check(len(apr) == 1 and apr[0].count(OVERRIDE) == 1,
      "explicit inputs:[go.answer] keeps exactly one block (covered id not re-injected)")
check("(ancestor gate answer)" not in apr[0],
      "explicit coverage means no ancestor-labelled duplicate")

# --- (5) MUTATION CONTROL: the law is present and fail-closed ---------------------
src = (BUILD / "wf.py").read_text()
check("ancestor gate answer" in src, "the injection loop ships")
check("a in injected or a not in outputs" in src,
      "skip rule: non-gates, covered ids, and UNCOMMITTED answers never inject")

print(f"ALL PASS ({ok})")
