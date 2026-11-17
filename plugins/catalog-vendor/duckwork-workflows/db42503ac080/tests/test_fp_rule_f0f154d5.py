"""f0f154d5dd80220c: live-shaped unstamped replay and fail-closed boundaries.

WF_F0_READER points at a historical reader for the red/mutation proof. Hashes
are written by the current rule-2 writer, exactly like the old live run.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wfcommon as writer

reader_path = os.environ.get("WF_F0_READER")
if reader_path:
    spec = importlib.util.spec_from_file_location("historical_wfcommon", reader_path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
else:
    reader = writer


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def run(root, nodes, *, rule=writer.FP_RULE_VERSION, stamp=False):
    graph = {"name": "fingerprint-era", "nodes": nodes}
    byid = {n["id"]: n for n in nodes}
    put(root / "graph.json", graph)
    put(root / "run.json", {"name": "fingerprint-era"})
    put(root / "runner_exit.json", {
        "reason": "done", "at": "2026-09-26T03:41:02+00:00",
        "graph_fingerprint": writer.graph_fingerprint(graph, rule=rule),
        **({"fp_rule_version": rule} if stamp else {}),
    })
    for n in nodes:
        put(root / "nodes" / (n["id"] + ".json"), {
            "status": "done", "output": n.get("output"),
            "efp": writer.efp(byid, n, rule=rule),
            **({"fp_rule_version": rule} if stamp else {}),
        })
    (root / "events.jsonl").write_text('{"event":"node.done"}\n{"event":"run.done"}\n')
    return graph, byid


def test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        done = root / "done"
        nodes = [
            {"id": "author", "type": "agent", "goal": "Write", "max_turns": 70, "timeout": 3000},
            {"id": "assemble", "type": "agent", "after": ["author"], "goal": "Assemble", "max_turns": 70, "timeout": 3000},
        ]
        graph, byid = run(done, nodes)
        hashes = [writer.graph_fingerprint(graph, rule=v) for v in writer.FP_RULES]
        assert len(set(hashes)) == 2, hashes  # unique unstamped era match
        exit_rec = reader.runner_exit_read(done)
        states = [reader.node_rec(done, n, byid)[0] for n in nodes]
        assert exit_rec["reason"] == "done", f"done-shape runner reason={exit_rec['reason']} {exit_rec}"
        assert states == ["done"] * len(nodes), f"done-shape nodes={states}"
        assert reader.run_state(done)["status"] == "done"
        print("PASS budget-bearing unstamped era-2 run.done replays as done")

        # The reader before 7deffc3 recognizes only era 2. An unstamped era-1
        # budgeted run is its explicit regression mutation: stale, not done.
        legacy = root / "legacy"
        _, old_ids = run(legacy, nodes, rule=writer.FP_RULE_LEGACY)
        old_exit = reader.runner_exit_read(legacy)
        assert old_exit["reason"] == "done", f"legacy runner reason={old_exit['reason']} {old_exit}"
        assert [reader.node_rec(legacy, n, old_ids)[0] for n in nodes] == ["done"] * len(nodes)
        assert reader.run_state(legacy)["status"] == "done"
        print("PASS budget-bearing unstamped era-1 run.done replays as done")

        # Different run: no budget means both historical rules produce the SAME hash.
        # F5 (2026-09-28): two agreeing rules prove the definition is unchanged —
        # an old-form record must replay as committed, not re-spawn.
        ambiguous = root / "ambiguous"
        plain = {"id": "plain", "type": "echo", "output": "x"}
        _, ids = run(ambiguous, [plain])
        assert writer.efp(ids, plain, rule=1) == writer.efp(ids, plain, rule=2)
        assert reader.node_rec(ambiguous, plain, ids)[0] == "done"
        assert reader.runner_exit_read(ambiguous)["reason"] == "done"
        print("PASS both-rule-matching unstamped hashes replay as done")

        invalid = root / "invalid"
        _, ids = run(invalid, [nodes[0]])
        rec = writer.jload(invalid / "nodes/author.json")
        rec["efp"] = "not-a-known-rule"
        put(invalid / "nodes/author.json", rec)
        rec = writer.jload(invalid / "runner_exit.json")
        rec["graph_fingerprint"] = "not-a-known-rule"
        put(invalid / "runner_exit.json", rec)
        assert reader.node_rec(invalid, nodes[0], ids)[0] == "pending"
        assert reader.runner_exit_read(invalid)["reason"] == "stale"
        print("PASS no-rule fingerprint fails closed despite run.done")

        # A genuine budget amendment invalidates stamped legacy-era commits;
        # the downstream effective fingerprint carries that changed ancestor.
        amended = root / "amended"
        old = writer.FP_RULE_LEGACY
        _, old_ids = run(amended, nodes, rule=old, stamp=True)
        changed = json.loads(json.dumps(nodes))
        changed[0]["max_turns"] = 71
        put(amended / "graph.json", {"name": "fingerprint-era", "nodes": changed})
        new_ids = {n["id"]: n for n in changed}
        assert writer.efp(old_ids, nodes[1], rule=old) != writer.efp(new_ids, changed[1], rule=old)
        assert reader.node_rec(amended, changed[1], new_ids)[0] == "pending"
        assert reader.runner_exit_read(amended)["reason"] == "stale"
        print("PASS budget-bearing legacy amend keeps downstream pending")


if __name__ == "__main__":
    test()
