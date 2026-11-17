#!/usr/bin/env python3
"""est-xd3b (issue #132 slice 1, runner): agent nodes honor when + on_skip.

The runner law pinned here — evaluated at the wave boundary, AFTER the
requires-unmet precondition, BEFORE Popen (same order as the gate-skip law at
the gate block):

  * false predicate + on_skip omitted/prune -> the agent commits `skipped`
    (efp-stamped node rec) + an `agent.skipped` event, and the EXISTING
    prune_states cascade arms its whole after-subtree -- zero spawns;
  * false predicate + on_skip: pass -> the node commits `done` with an
    `{agent: skipped}` rec + agent.skipped (the gate-skip pass-shape mirror);
  * a BROKEN predicate (a mid-evaluation TypeError -- `out.x.field > 3` with no
    such field on x) FAILS SAFE: the node spawns normally and `agent.when_error`
    is logged. A node must never be skipped by a failing assumption;
  * fan-out: when is a WHOLE-NODE gate -- a false predicate skips the node, not
    one item.

The door still refuses a structurally-malformed or self-referencing `when`
(validator grammar = slice est-l2ey), so this slice never invents a dialect the
door would reject: the broken-predicate leg feeds a well-formed expr whose eval
raises on real data.

Spawn counting follows tests/test_prune_0923.py: every tests/fake invocation
appends one line to $FAKE_LOG. The runner is driven in-process (exec wf.py by
path, call main(run_id)) exactly like tests/test_11_runner_requires.py, with the
est-2ek.1.762 launch-env pin helper.

Mutant discipline (blessed-engine-semantics law): deleting the runner's
agent-when branch turns LEGS 1, 2, 4 and 7 RED (the false-predicate agents spawn
instead of skipping -- FAKE_LOG gains lines, statuses flip to done); deleting
the agent.when_error fail-safe line turns LEG 6 RED (the node skips on the
broken predicate instead of spawning); deleting the agent.when_error `log(...)`
call alone turns LEG 6b RED (the spawn survives, the event does not).
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# est-2ek.1.762: shared launch-env pin helper, exec-loaded by file path (repo
# convention -- a top-level import of a tests/fixtures module would break the
# test_packaging import-closure from the unpacked package root).
_spec_iso762 = importlib.util.spec_from_file_location(
    "wf_spawn_isolation_762", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
assert _spec_iso762 and _spec_iso762.loader
_iso762 = importlib.util.module_from_spec(_spec_iso762)
_spec_iso762.loader.exec_module(_iso762)
pin_env = _iso762.pin_env

# same pattern as test_prune_0923.py: tests/fake (via tests/fake_duckwork.py),
# FAKE_LOG counts spawns; the real duckwork binary is never on this path.
FAKE = str(ROOT / "tests" / "fake")
assert os.path.exists(FAKE), "missing %s -- run from the repo checkout root" % FAKE

_spec_wf = importlib.util.spec_from_file_location("wf_when_on_agent_engine", ROOT / "wf.py")
assert _spec_wf and _spec_wf.loader
wf = importlib.util.module_from_spec(_spec_wf)
_spec_wf.loader.exec_module(wf)
WFC = wf.wfcommon

fails = 0
total = 0


def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


def fresh(name, graph, meta=None):
    root = Path(tempfile.mkdtemp(prefix="when_agent_"))
    runs = root / "workflows"
    r = runs / name
    r.mkdir(parents=True)
    (r / "graph.json").write_text(json.dumps({"nodes": graph}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4,
                                            **(meta or {})}))
    return root, runs


def drive(root, runs, rid):
    env = pin_env(dict(os.environ, DUCKWORK_HOME=str(root)), runs, home=root)
    env["FAKE_LOG"] = str(root / "fake.log")
    if wf._LOCK_FD is not None:
        os.close(wf._LOCK_FD)
        setattr(wf, "_LOCK_FD", None)
    wf._EXIT_WRITTEN[0] = False
    # The DOOR law for agent+when belongs to the validator slice (est-l2ey):
    # main tip still refuses it ("only gate nodes take when"). This slice is
    # the RUNNER leg — what it does with a `when` that survived the door — so
    # the door check is pinned open exactly like tests/test_11_runner_requires.py
    # pins it for `requires`. Leg 6c separately pins that the grammar stays the
    # door's property (a self-referencing head is refused by the validator).
    with patch.dict(os.environ, env, clear=True), \
         patch.object(wf, "validate_graph", return_value=None):
        wf.main(rid)
    if wf._LOCK_FD is not None:
        os.close(wf._LOCK_FD)
        setattr(wf, "_LOCK_FD", None)


def observe(runs, rid):
    log_p = runs.parent / "fake.log"
    spawns = len(log_p.read_text().splitlines()) if log_p.exists() else 0
    st = {k: v["status"] for k, v in WFC.run_state(runs / rid)["nodes"].items()}
    ev_p = runs / rid / "events.jsonl"
    ev = [json.loads(x) for x in ev_p.read_text().splitlines()] if ev_p.exists() else []
    return st, spawns, ev


def rec_of(runs, rid, nid):
    p = runs / rid / "nodes" / f"{nid}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def agent(id, after=(), **extra):
    n = {"id": id, "type": "agent", "goal": "JSON:{}", "after": list(after)}
    n.update(extra)
    return n


def judge(id, verdict):
    return {"id": id, "type": "agent",
            "goal": "JSON:" + json.dumps({"clean": bool(verdict), "score": 5 if verdict else 1})}


# 1. false predicate -> the agent never spawns; commits skipped + event
root, runs = fresh("when_false_prune", [judge("j", False),
                                        agent("b", ["j"], when="out.j.clean == True")])
drive(root, runs, "when_false_prune")
st, spawns, ev = observe(runs, "when_false_prune")
rec_b = rec_of(runs, "when_false_prune", "b")
check("1 false predicate spawns ZERO extra children (only the judge ran)", spawns == 1,
      f"fake.log lines={spawns}")
check("1 false predicate commits skipped", st.get("b") == "skipped", str(st))
check("1 skipped rec is efp-stamped (replay identity law)",
      rec_b.get("status") == "skipped" and bool(rec_b.get("efp")), str(rec_b)[:200])
check("1 agent.skipped event fires",
      any(e["event"] == "agent.skipped" and e.get("node") == "b" for e in ev),
      str([e["event"] for e in ev]))
check("1 zero-cost rec mirrors the gate skip (ms == 0)", rec_b.get("ms") == 0, str(rec_b)[:200])
shutil.rmtree(root, ignore_errors=True)

# 2. prune cascade arms off an AGENT skip (the existing prune_states law)
root, runs = fresh("when_cascade", [judge("j", False),
                                    agent("b", ["j"], when="out.j.clean == True"),
                                    agent("c", ["b"]), agent("d", ["c"]),
                                    agent("e", ["j"])])
drive(root, runs, "when_cascade")
st, spawns, ev = observe(runs, "when_cascade")
check("2 cascade: only j and e spawn; b/c/d never exist as processes",
      spawns == 2 and st.get("b") == "skipped" and st.get("c") == "skipped"
      and st.get("d") == "skipped" and st.get("e") == "done", f"spawns={spawns} {st}")
shutil.rmtree(root, ignore_errors=True)

# 3. true predicate: normal spawn, no skip residue
root, runs = fresh("when_true_spawn", [judge("j", True),
                                       agent("b", ["j"], when="out.j.clean == True")])
drive(root, runs, "when_true_spawn")
st, spawns, ev = observe(runs, "when_true_spawn")
check("3 true predicate spawns normally", spawns == 2 and st.get("b") == "done",
      f"spawns={spawns} {st}")
check("3 no skip residue on the true path",
      not any(e["event"] == "agent.skipped" for e in ev), str([e["event"] for e in ev]))
shutil.rmtree(root, ignore_errors=True)

# 4. on_skip: pass -- the node passes through as done, zero spawn
root, runs = fresh("when_pass", [judge("j", False),
                                 agent("b", ["j"], when="out.j.clean == True",
                                       **{"on_skip": "pass"}),
                                 agent("c", ["b"])])
drive(root, runs, "when_pass")
st, spawns, ev = observe(runs, "when_pass")
rec_b = rec_of(runs, "when_pass", "b")
check("4 on_skip pass: b done, c runs, only j+c spawned",
      spawns == 2 and st.get("b") == "done" and st.get("c") == "done", f"spawns={spawns} {st}")
check("4 pass rec carries {agent: skipped} (gate-skip mirror)",
      rec_b.get("output") == {"agent": "skipped"}, str(rec_b)[:200])
shutil.rmtree(root, ignore_errors=True)

# 5. requires-unmet still fails FIRST: a false when on a node with an unmet
#    requires commits the precondition failure, never a skip.
root, runs = fresh("when_vs_requires", [
    {"id": "fix", "type": "echo", "output": {"pr_url": None}},
    {"id": "review", "type": "agent", "after": ["fix"], "goal": "JSON:{}",
     "requires": {"fix": ["pr_url"]}, "when": "out.fix.ok == True"}])
drive(root, runs, "when_vs_requires")
rec = rec_of(runs, "when_vs_requires", "review")
check("5 unmet requires beats a false when (failed, not skipped)",
      rec.get("status") == "failed" and rec.get("error_class") == "precondition",
      str(rec)[:200])
shutil.rmtree(root, ignore_errors=True)

# 6. broken predicate FAILS SAFE: well-formed expr (door-legal), mid-eval
#    TypeError on real data -> spawn + agent.when_error, never a skip.
root, runs = fresh("when_broken", [judge("j", False), agent("b", ["j"],
                                                    when="out.j.field > 3")])
drive(root, runs, "when_broken")
st, spawns, ev = observe(runs, "when_broken")
check("6 broken predicate fails SAFE -- b spawns (j + b)",
      spawns == 2 and st.get("b") == "done", f"spawns={spawns} {st}")
check("6b agent.when_error is logged for b",
      any(e["event"] == "agent.when_error" and e.get("node") == "b" for e in ev),
      str([e["event"] for e in ev]))
check("6c the door still refuses a self-referencing head (grammar is not invented here)",
      [e["field"] for e in WFC.validate_graph_errors(
          [{"id": "a", "type": "agent", "goal": "JSON:{}", "when": "out.a.ok"}])] == ["when"],
      "validator must own the grammar")
shutil.rmtree(root, ignore_errors=True)

# 7. fan-out: when is a WHOLE-NODE gate -- false skips the node, not one item
root, runs = fresh("when_fanout", [judge("j", False),
                                   {"id": "fan", "type": "agent", "after": ["j"],
                                    "when": "out.j.clean == True",
                                    "fanout": {"items": ["alpha", "beta"], "goal": "JSON:{}"}},
                                   agent("down", ["fan"])])
drive(root, runs, "when_fanout")
st, spawns, ev = observe(runs, "when_fanout")
check("7 false predicate skips the WHOLE fan-out node (only j spawns)",
      spawns == 1 and st.get("fan") == "skipped" and st.get("down") == "skipped",
      f"spawns={spawns} {st}")
shutil.rmtree(root, ignore_errors=True)

# 8. replay stability: a second runner pass on the settled run replays every
#    record (efp valid) -- zero new spawns, the skip stays terminal.
root, runs = fresh("when_replay", [judge("j", False),
                                   agent("b", ["j"], when="out.j.clean == True")])
drive(root, runs, "when_replay")
drive(root, runs, "when_replay")
st, spawns, ev = observe(runs, "when_replay")
check("8 replay: second pass spawns nothing; the skip stays terminal",
      spawns == 1 and st.get("b") == "skipped", f"spawns={spawns} {st}")
shutil.rmtree(root, ignore_errors=True)

print("DONE when_on_agent_engine", "OK" if fails == 0 else "FAIL")
sys.exit(0 if fails == 0 else 1)
