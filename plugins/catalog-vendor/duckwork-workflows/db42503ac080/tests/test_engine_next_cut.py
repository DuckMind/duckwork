"""Engine branch contracts, exercised by the actual runner and fake CLI (no provider)."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon


class EngineNextCut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "tests", prefix="engine-next-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {**os.environ, "DUCKWORK_HOME": str(self.home),
                    # #71: pin the shelf too — DUCKWORK_HOME alone can lose to the
                    # context-local home override; WF_RUNS_ROOT is checked first.
                    "WF_RUNS_ROOT": str(self.home / "workflows"),
                    "FAKE_LOG": str(self.home / "fake.log")}

    def example(self, name):
        hits = sorted((ROOT / "examples").rglob(f"{name}.json"))
        assert hits, f"example {name} not found"
        return json.loads(hits[0].read_text())

    def run_graph(self, name, graph):
        run = self.home / "workflows" / name
        for folder in ("nodes", "gates"):
            (run / folder).mkdir(parents=True, exist_ok=True)
        (run / "graph.json").write_text(json.dumps(graph))
        (run / "run.json").write_text(json.dumps({"duckwork_bin": str(ROOT / "tests" / "fake"),
                                                  "concurrency": 4}))
        return run

    def step(self, run, expected):
        p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run.name],
                           env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(expected, p.stdout, p.stdout + p.stderr)

    def release(self, run, gate, answer):
        graph = json.loads((run / "graph.json").read_text())
        nodes = {n["id"]: n for n in graph["nodes"]}
        (run / "gates" / f"{gate}.json").write_text(json.dumps(
            {"answer": answer, "_def": wfcommon.efp(nodes, nodes[gate])}))

    def states(self, run):
        return {k: v["status"] for k, v in wfcommon.run_state(run)["nodes"].items()}

    def test_agent_when_is_rejected_not_silently_ignored(self):
        errors = wfcommon.validate_graph_errors([
            {"id": "a", "type": "agent", "goal": "JSON:{}", "when": "out.a.ok"}])
        self.assertEqual([e["field"] for e in errors], ["when"])
        self.assertIn("only gate", errors[0]["msg"])

    def test_submit_rejects_ignored_when_before_run_directory_creation(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("engine_next_door", ROOT / "__init__.py")
        door = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(door)
        import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
        original = os.environ.get("DUCKWORK_HOME")
        original_runs = os.environ.get("WF_RUNS_ROOT")
        os.environ["DUCKWORK_HOME"] = str(self.home)
        os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
        os.environ["WF_RUNS_ROOT"] = str(self.home / "workflows")  # #71 shelf pin
        try:
            res = door.act_run({"graph": {"name": "reject", "nodes": [
                {"id": "a", "type": "agent", "goal": "JSON:{}", "when": "true"}]}})
        finally:
            if original is None:
                os.environ.pop("DUCKWORK_HOME", None)
            else:
                os.environ["DUCKWORK_HOME"] = original
                os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
            if original_runs is None:
                os.environ.pop("WF_RUNS_ROOT", None)
            else:
                os.environ["WF_RUNS_ROOT"] = original_runs
        self.assertIn("only gate nodes take when", res["error"])
        self.assertFalse((self.home / "workflows").exists())

    def test_lowercase_bool_literals_are_bounded_and_functional(self):
        for literal, expected in (("true", True), ("false", False),
                                  ("True", True), ("False", False)):
            expr = f"out.judge.clean == {literal}"
            self.assertIsNone(wfcommon.when_expr_ok(expr), expr)
            self.assertEqual(wfcommon.when_true({"when": expr}, {"judge": {"clean": True}}),
                             expected, expr)
        self.assertIsNotNone(wfcommon.when_expr_ok("out.judge.clean == maybe"))

    def test_approve_publish_example_each_answer_runs_one_arm(self):
        for answer, live, dead in (("publish", "publish", "rewrite"),
                                   ("rewrite", "rewrite", "publish")):
            with self.subTest(answer=answer):
                graph = self.example("approve-publish")
                self.assertEqual(wfcommon.validate_graph_errors(graph["nodes"]), [])
                for n in graph["nodes"]:
                    if n["type"] == "agent":
                        n["goal"] = 'JSON:{"result":"' + n["id"] + '"}'
                run = self.run_graph("approve-" + answer, graph)
                self.step(run, "WORKFLOW_HELD")
                self.release(run, "approve", answer)
                self.step(run, "WORKFLOW_DONE")
                statuses = self.states(run)
                self.assertEqual((statuses[live], statuses[dead]), ("done", "skipped"))
                self.assertFalse((run / "nodes" / (dead + ".0.json")).exists())
                self.assertFalse(list((run / "logs").glob(dead + ".a*.log")))
                state = wfcommon.run_state(run)
                self.assertEqual((state["status"], state["done"], state["total"]),
                                 ("done", len(graph["nodes"]), len(graph["nodes"])))

    def test_branch_example_ship_hold_and_mixed_join(self):
        for verdict, live, dead in (("ship", "ship_it", "escalate"),
                                    ("hold", "escalate", "ship_it")):
            with self.subTest(verdict=verdict):
                graph = self.example("branch-on-verdict")
                self.assertEqual(wfcommon.validate_graph_errors(graph["nodes"]), [])
                for n in graph["nodes"]:
                    if n["type"] == "agent":
                        if n["id"] == "judge":
                            val = {"verdict": verdict, "why": "test"}
                        elif n["id"] == "ship_it":
                            val = {"arm": "go", "echo": "test"}
                        elif n["id"] == "join":
                            val = {"arms_seen": [live]}
                        else:
                            val = {"arm": "hold"}
                        n["goal"] = "JSON:" + json.dumps(val)
                run = self.run_graph("verdict-" + verdict, graph)
                self.step(run, "WORKFLOW_HELD" if verdict == "hold" else "WORKFLOW_DONE")
                if verdict == "hold":
                    self.release(run, "hold", "stop")
                    self.step(run, "WORKFLOW_DONE")
                states = self.states(run)
                self.assertEqual((states[live], states[dead], states["join"]),
                                 ("done", "skipped", "done"))
                self.assertEqual(wfcommon.run_state(run)["status"], "done")
                self.assertFalse(list((run / "logs").glob(dead + ".a*.log")))

    def test_amend_swaps_pruned_and_live_arms_without_stale_exit_suppression(self):
        graph = self.example("approve-publish")
        for n in graph["nodes"]:
            if n["type"] == "agent":
                n["goal"] = 'JSON:{"result":"' + n["id"] + '"}'
        run = self.run_graph("amended", graph)
        self.step(run, "WORKFLOW_HELD")
        self.release(run, "approve", "publish")
        self.step(run, "WORKFLOW_DONE")
        graph = copy.deepcopy(graph)
        graph["nodes"][0]["goal"] = 'JSON:{"result":"draft-amended"}'  # invalidate both arms
        (run / "graph.json").write_text(json.dumps(graph))
        self.step(run, "WORKFLOW_HELD")
        self.release(run, "approve", "rewrite")
        self.step(run, "WORKFLOW_DONE")
        self.assertEqual((self.states(run)["publish"], self.states(run)["rewrite"]),
                         ("skipped", "done"))
        self.assertEqual(wfcommon.run_state(run)["status"], "done")

    def test_ignored_graph_keys_are_rejected(self):
        base = {"id": "a", "type": "agent", "goal": "JSON:{}"}
        for node, field in ((dict(base, name="Friendly"), "name"),
                            ({**base, "fanout": {"items": ["x"], "goal": "JSON:{}",
                                                 "timeout": 2}}, "fanout.timeout"),
                            ({**base, "fanout": {"items": ["x"], "goal": "JSON:{}",
                                                 "max_turns": 2}}, "fanout.max_turns"),
                            ({"id": "g", "type": "gate", "question": "?", "name": "Friendly"}, "name")):
            with self.subTest(field=field):
                self.assertIn(field, [e["field"] for e in wfcommon.validate_graph_errors([node])])

    def test_unimplemented_schema_keyword_is_rejected(self):
        # #107 flipped the enum law: a well-formed enum (non-empty list of
        # non-empty strings on type:'string') is ADMITTED and ENFORCED at
        # harvest (tests/test_schema_enum_107.py). The unimplemented-keyword
        # refusal stays for everything the validator cannot enforce.
        ok_schema = {"type": "object", "properties": {"verdict": {"type": "string",
                                                                   "enum": ["ship", "hold"]}}}
        bad_schema = {"type": "object", "properties": {"verdict": {"type": "string",
                                                                    "patternProperties": {}}}}
        for field, schema, good in (("schema", ok_schema, True),
                                    ("fanout.schema", ok_schema, True),
                                    ("schema", bad_schema, False),
                                    ("fanout.schema", bad_schema, False)):
            node = {"id": "a", "type": "agent", "goal": "JSON:{}"}
            if field == "schema":
                node["schema"] = schema
            else:
                node["fanout"] = {"items": ["x"], "goal": "JSON:{}", "schema": schema}
            with self.subTest(field=field, good=good):
                errors = wfcommon.validate_graph_errors([node])
                kw = [e for e in errors if "unsupported schema keyword" in e["msg"]]
                if good:
                    self.assertEqual([], kw, errors)
                else:
                    self.assertTrue(any(e["field"] == field + ".properties.verdict.patternProperties"
                                        for e in kw), errors)

    def test_missing_upstream_input_fails_loud(self):
        graph = {"nodes": [{"id": "seed", "type": "agent", "goal": "JSON:{}"},
                            {"id": "consumer", "type": "agent", "after": ["seed"],
                             "inputs": ["seed.absent"], "goal": "JSON:{}"}]}
        run = self.run_graph("missing-input", graph)
        self.step(run, "WORKFLOW_FAILED")
        rec = json.loads((run / "nodes" / "consumer.json").read_text())
        self.assertEqual(rec["status"], "failed")
        self.assertIn("seed.absent not resolvable", rec["error"])
        self.assertFalse(list((run / "logs").glob("consumer.a*.log")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
