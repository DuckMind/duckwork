"""on_skip:'prune' (2026-09-23): a false `when` on a prune gate commits `skipped`; nodes
whose deps are ALL skipped are skipped (terminal, non-failure); a join with a live dep
runs; run ends `done`. Omitted on_skip defaults to prune; explicit pass lets the arm run. Also:
validator grammar, read-model counts, blocked_by vocabulary, amend preview, and the
door's version-skew guard (runner_exit.reason == 'done' is terminal even if the door's
read model predates a status).

Real runner + tests/fake. Proof-of-behaviour run: 20260923-035502-prune-proof."""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN))
import wfcommon  # noqa: E402

HOME = HERE / "home10"
RUNS = HOME / "workflows"
FAKE = HERE / "fake"
ENV = {**os.environ, "DUCKWORK_HOME": str(HOME), "WF_RUNS_ROOT": str(RUNS), "WF_DUCKWORK_BIN": str(FAKE),
       "PATH": f"{FAKE.parent}:{os.environ.get('PATH', '')}"}
PY = sys.executable
FAILS = []

def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)

def fresh(run_id, nodes):
    r = RUNS / run_id
    if r.exists():
        import shutil; shutil.rmtree(r)
    for d in ("nodes", "gates", "logs"):
        (r / d).mkdir(parents=True)
    (r / "graph.json").write_text(json.dumps({"name": "t", "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": "t", "duckwork_bin": str(FAKE), "concurrency": 4,
                                            "started": "2026-09-23T00:00:00+00:00", "owner": "test"}))
    return r

def run_runner(r, timeout=120):
    p = subprocess.run([PY, str(PLUGIN / "wf.py"), "run", r.name], env=ENV,
                       capture_output=True, text=True, timeout=timeout)
    return p

# fake child: goal text 'JSON:{...}' makes the fake emit that block (see fake_duckwork.py)
def agent(id, after=(), verdict=None, inputs=None):
    n = {"id": id, "type": "agent", "after": list(after), "timeout": 30,
         "goal": f'JSON:{json.dumps({"verdict": verdict} if verdict else {"ok": True})}'}
    if inputs: n["inputs"] = inputs
    return n

# ---- 1. validator grammar ----
V = wfcommon.validate_graph
check("on_skip on agent rejected (closed key set)",
      "unknown key" in (V([dict(agent("a"), on_skip="prune")]) or ""))
check("on_skip bad enum rejected",
      "allowed: ['pass', 'prune']" in (V([agent("a"), {"id": "g", "type": "gate", "after": ["a"], "when": "out.a.ok", "on_skip": "nope", "question": "?"}]) or ""))
check("on_skip without when rejected",
      "needs a `when`" in (V([agent("a"), {"id": "g", "type": "gate", "after": ["a"], "on_skip": "prune", "question": "?"}]) or ""))
check("on_skip prune + when accepted",
      V([agent("a"), {"id": "g", "type": "gate", "after": ["a"], "when": "out.a.ok", "on_skip": "prune", "question": "?"}]) is None)

# ---- 2. prune_states derivation (pure) ----
nodes = [agent("j"), {"id": "g", "type": "gate", "after": ["j"], "when": "x", "on_skip": "prune", "question": "?"},
         agent("arm", ["g"]), agent("deep", ["arm"]), agent("live", ["j"]), agent("join", ["deep", "live"])]
states = {"j": "done", "g": "skipped", "arm": "pending", "deep": "pending", "live": "done", "join": "pending"}
derived = wfcommon.prune_states(nodes, states)
check("prune propagates through the arm", derived == {"arm", "deep"}, str(derived))
check("join with a live dep is NOT pruned", states["join"] == "pending")
check("dep_satisfied treats skipped as satisfied", wfcommon.dep_satisfied(states, "deep") and wfcommon.dep_satisfied(states, "live"))

# ---- 3. real runner: two-arm branch, verdict 'ship' -> hold arm pruned, join runs ----
graph = [agent("judge", verdict="ship"),
         {"id": "go", "type": "gate", "after": ["judge"], "when": "out.judge.verdict == 'ship'", "on_skip": "prune", "wait": {"wait_s": 1}},
         {"id": "hold", "type": "gate", "after": ["judge"], "when": "out.judge.verdict != 'ship'", "on_skip": "prune", "question": "override?", "options": ["yes", "no"]},
         agent("ship_it", ["go"]), agent("escalate", ["hold"]), agent("join", ["ship_it", "escalate"])]
r = fresh("20990101-000000-prune", graph)
p = run_runner(r)
byid = {n["id"]: n for n in graph}
st = wfcommon.run_state(r)
S = {k: v["status"] for k, v in st["nodes"].items()}
check("runner exits done", "WORKFLOW_DONE" in p.stdout or (st["runner_exit"] or {}).get("reason") == "done", p.stdout[-300:] + p.stderr[-300:])
check("hold gate committed skipped", S.get("hold") == "skipped", str(S))
check("escalate pruned (never spawned)", S.get("escalate") == "skipped" and not any(x.name.startswith("escalate") for x in (r / "logs").iterdir()), str(S))
check("ship_it ran", S.get("ship_it") == "done")
check("join ran with one live dep", S.get("join") == "done")
check("run status done, counts include skipped", st["status"] == "done" and st["done"] == 6 and st["skipped"] == 2 and st["total"] == 6, f"{st['status']} {st['done']}/{st['total']} skipped={st['skipped']}")
ev = [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
check("events: gate.skipped carries on_skip=prune", any(e.get("event") == "gate.skipped" and e.get("node") == "hold" and e.get("on_skip") == "prune" for e in ev))
check("events: node.skipped for escalate", any(e.get("event") == "node.skipped" and e.get("node") == "escalate" for e in ev))
rec = json.loads((r / "nodes" / "escalate.json").read_text())
check("pruned record is efp-stamped (replay-skip law)", rec.get("efp") == wfcommon.efp(byid, byid["escalate"]))
check("runner_exit.json reason done", (st["runner_exit"] or {}).get("reason") == "done")

# ---- 4. omitted on_skip prunes; explicit pass keeps the opt-in arm ----
for policy in (None, "pass"):
    graph2 = [dict(n) for n in graph]
    for n in graph2:
        if n["type"] == "gate":
            if policy is None:
                n.pop("on_skip", None)
            else:
                n["on_skip"] = policy
    r2 = fresh(f"20990101-000001-{policy or 'default'}", graph2)
    run_runner(r2)
    S2 = {k: v["status"] for k, v in wfcommon.run_state(r2)["nodes"].items()}
    ev2 = [json.loads(l) for l in (r2 / "events.jsonl").read_text().splitlines()]
    expected = policy or "prune"
    check(f"human false when {expected}: saved status, event, arm and mixed join",
          S2.get("hold") == ("skipped" if expected == "prune" else "done")
          and S2.get("escalate") == ("skipped" if expected == "prune" else "done")
          and S2.get("join") == "done"
          and any(e.get("event") == "gate.skipped" and e.get("node") == "hold"
                  and e.get("on_skip") == expected for e in ev2)
          and ((r2 / "logs" / "escalate.a0.log").exists() == (expected == "pass")), str(S2))

# ---- 5. amend preview + blocked_by know 'skipped' ----
pv = wfcommon.amend_preview(r, graph)
check("amend preview: unchanged includes skipped nodes", "escalate" in pv["unchanged"] and "hold" in pv["unchanged"] and pv["changed"] == [], str(pv))
bb = wfcommon.blocked_by(byid["join"], {"ship_it": "done", "escalate": "skipped"}, {})
check("blocked_by: skipped dep is not a blocker", bb == [], str(bb))

# ---- 6. door version-skew guard: runner_exit done + dead runner => wait returns, no respawn ----
sys.path.insert(0, str(PLUGIN))
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
import importlib.util
spec = importlib.util.spec_from_file_location("door", PLUGIN / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
spawned = []
door._spawn_runner = lambda rr: spawned.append(rr.name)
out = door.act_wait({"run_id": r.name, "timeout": 5})
check("wait on a done run with dead runner does not respawn", spawned == [] and out.get("status") == "done", f"spawned={spawned} status={out.get('status')}")

print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)} ({22 - len(FAILS)}/22)")
sys.exit(1 if FAILS else 0)
