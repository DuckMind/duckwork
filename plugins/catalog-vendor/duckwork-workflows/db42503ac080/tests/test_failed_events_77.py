#!/usr/bin/env python3
"""Item #77 (verb-roadmap/artifact-recovery): every node.failed EVENT must
carry the typed error_class + attempts the runner already knows — exit code and
prose alone forced the parent to infer. Engine-driven with the fake duckwork.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
sys.path.insert(0, str(BUILD.parent))
HOME = BUILD / "home77"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
RUNS = HOME / "workflows"
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

def mk(run_id, nodes):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps(
        {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
    return r

def wf(run_id, fake_mode=None):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake77.log"))
    if fake_mode:
        env["FAKE_MODE"] = fake_mode
    return subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=120)

def events(r):
    return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]

# --- solo typed max_turns death -> event names the class, no prose inference ---
r = mk("f77-typed", [{"id": "solo", "type": "agent", "goal": "do it"}])
wf("f77-typed", "typed_maxturns")
nf = [e for e in events(r) if e["event"] == "node.failed"]
check("solo death emits exactly one node.failed", len(nf) == 1, str(nf))
e = nf[0] if nf else {}
check("typed death event carries error_class=cap_exhausted", e.get("error_class") == "cap_exhausted", str(e))
check("typed death event carries attempts>=1", isinstance(e.get("attempts"), int) and e["attempts"] >= 1, str(e))

# --- quorum failure -> typed class on the event too ---
r = mk("f77-quorum", [{"id": "f", "type": "agent",
                       "fanout": {"goal": "template", "items": [{"goal": "CRASHME now"}, {"goal": "fine task"}]}}])
wf("f77-quorum")
nf = [e for e in events(r) if e["event"] == "node.failed" and e.get("node") == "f"]
e = nf[0] if nf else {}
check("quorum death event carries error_class=quorum", e.get("error_class") == "quorum", str(e))
check("quorum event keeps failed_detail", isinstance(e.get("failed_detail"), list), str(e)[:160])

# --- unresolvable input ref -> typed inputs class, attempts=0 (never spawned) ---
r = mk("f77-inputs", [{"id": "up", "type": "agent", "goal": 'JSON:{"items": ["a"]}'},
                      {"id": "down", "type": "agent", "after": ["up"], "goal": "use it",
                       "inputs": ["up.missing.path"]}])
wf("f77-inputs")
nf = [e for e in events(r) if e["event"] == "node.failed" and e.get("node") == "down"]
e = nf[0] if nf else {}
check("inputs death event carries error_class=inputs", e.get("error_class") == "inputs", str(e))
check("inputs death event attempts=0 (never spawned)", e.get("attempts") == 0, str(e))

# --- invariant: EVERY node.failed event in every scenario is typed + counted ---
allbad = []
for rid in ("f77-typed", "f77-quorum", "f77-inputs"):
    for e in events(RUNS / rid):
        if e["event"] == "node.failed" and ("error_class" not in e or "attempts" not in e):
            allbad.append(f"{rid}:{e.get('node')}:{e.get('error')}")
check("no untyped node.failed event anywhere", not allbad, ";".join(allbad)[:300])

print("ALL PASS" if not fails else "FAILURES PRESENT"); sys.exit(0 if not fails else 1)
