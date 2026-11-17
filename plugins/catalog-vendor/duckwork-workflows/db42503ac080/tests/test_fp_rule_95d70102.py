"""95d7010295d70102: versioned replay integrity across the budget-rule change."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wfcommon as c
import wf


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root, nodes):
    graph = {"nodes": nodes}
    put(root / "graph.json", graph)
    put(root / "run.json", {"fp_rule_version": c.FP_RULE_VERSION})
    (root / "events.jsonl").write_text('{"event":"run.done"}\n')
    return graph, {n["id"]: n for n in nodes}


def test():
    with tempfile.TemporaryDirectory() as tmp:
        r = Path(tmp)
        a = {"id": "a", "type": "echo", "output": {"ok": True}, "max_turns": 5}
        g = {"id": "g", "type": "gate", "after": ["a"], "question": "Go?"}
        b = {"id": "b", "type": "echo", "after": ["g"], "output": "yes"}
        graph, byid = fixture(r, [a, g, b])
        old, new = c.FP_RULE_LEGACY, c.FP_RULE_VERSION
        for n, rule in ((a, old), (g, new), (b, old)):
            put(r / "nodes" / (n["id"] + ".json"),
                {"status": "done", "output": n.get("output"), "efp": c.efp(byid, n, rule=rule), "fp_rule_version": rule})
        put(r / "gates/g.json", {"answer": "yes", "_def": c.efp(byid, g, rule=new), "fp_rule_version": new})
        put(r / "runner_exit.json", {"reason": "done", "graph_fingerprint": c.graph_fingerprint(graph, rule=old), "fp_rule_version": old})
        assert c.run_state(r)["status"] == "done"
        assert c.runner_exit_read(r)["reason"] == "done"
        assert c.gate_answer_valid(r, g, byid)["answer"] == "yes"
        # A real upstream definition change invalidates both historical and current commits.
        a["output"] = {"ok": False}
        graph, byid = fixture(r, [a, g, b])
        assert c.run_state(r)["status"] == "interrupted"
        assert c.node_rec(r, a, byid)[0] == "pending"
        assert c.node_rec(r, b, byid)[0] == "pending"
        assert c.gate_answer_valid(r, g, byid) is None
        assert c.runner_exit_read(r)["reason"] == "stale"
        # Unknown versions never silently use the current reader rule.
        a["output"] = {"ok": True}
        graph, byid = fixture(r, [a, g, b])
        rec = c.jload(r / "nodes/a.json"); rec["fp_rule_version"] = 999
        put(r / "nodes/a.json", rec)
        assert c.node_rec(r, a, byid)[0] == "pending"
        rec = c.jload(r / "runner_exit.json"); rec["fp_rule_version"] = 999
        put(r / "runner_exit.json", rec)
        assert c.runner_exit_read(r)["reason"] == "stale"
        # R10 old form: a no-budget unstamped commit (pre-1.0.12) hashes identically
        # under both historical rules — two agreeing rules prove the definition is
        # unchanged and must load as done, not re-spawn (fix 2026-09-28).
        plain = {"id": "plain", "type": "echo", "output": "x"}
        _, ids = fixture(r, [plain])
        put(r / "nodes/plain.json", {"status": "done", "efp": c.efp(ids, plain)})
        assert c.node_rec(r, plain, ids)[0] == "done"
        # Fail-closed still holds: a real definition change matches zero rules.
        put(r / "nodes/plain.json", {"status": "done", "efp": "0" * 64})
        assert c.node_rec(r, plain, ids)[0] == "pending"
        # Spawn identity is rejected on a mismatch before any PID lookup.
        running = {"status": "running", "efp": c.efp(ids, plain), "fp_rule_version": 999}
        assert c._verify_spawn_rec(r, plain, ids, running) is None
        # Writer paths stamp their own commits, even in a run armed by another version.
        wf.save_node(r, plain, ids, {"status": "done", "output": "x"})
        assert c.jload(r / "nodes/plain.json")["fp_rule_version"] == new
        wf.write_spawn_record(r, plain, ids, None, 0, ["fake"], r / "log", 987654, "fake")
        spawn = c.jload(r / "nodes/plain.json")
        assert spawn["fp_rule_version"] == new
        assert c._verify_spawn_rec(r, plain, ids, spawn) is None  # dead PID is not an active child
        wf._EXIT_WRITTEN[0] = False
        wf.write_runner_exit(r, "done", graph={"nodes": [plain]})
        assert c.jload(r / "runner_exit.json")["fp_rule_version"] == new
        # A budget amendment changes old-rule fingerprints only; a tagged old
        # commit must not be blessed by the new-rule matching hash.
        budgeted = {"id": "budgeted", "type": "agent", "goal": "x", "max_turns": 5}
        _, ids = fixture(r, [budgeted])
        put(r / "nodes/budgeted.json", {"status": "done", "efp": c.efp(ids, budgeted, rule=old), "fp_rule_version": old})
        budgeted["max_turns"] = 10
        _, ids = fixture(r, [budgeted])
        assert c.node_rec(r, budgeted, ids)[0] == "pending"
        print("PASS 95d7010295d70102 versioned replay and amend")


if __name__ == "__main__":
    test()
