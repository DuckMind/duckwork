#!/usr/bin/env python3
"""est-2ek.1.158: an optional graph-level `result: <node id>` names the node whose
output IS the run verdict, so a scheduler keys on one field instead of an ad-hoc
predicate over heterogeneous node outputs.

Contracts pinned here:
  (1) `result` must name an existing, non-gate node: a missing or gate node is
      refused at run() with a typed error naming the key, before any write/spawn.
  (2) Terminal status/wait report result={node, status, output} for that node.
  (3) A graph without the key produces the pre-change status shape (no `result`).

Run (stdlib only): python3 tests/test_graph_result_158.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_158", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)

TWO_SCHEMAS = {"name": "result158", "result": "judge", "nodes": [
    {"id": "scan", "type": "echo", "output": {"files": ["a", "b"], "count": 2}},
    {"id": "judge", "type": "echo", "after": ["scan"], "output": {"verdict": "ship", "score": 0.9}}]}


class GraphResult158(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf158-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "home").mkdir()
        self.env = {"WF_RUNS_ROOT": str(self.root / "runs"), "DUCKWORK_HOME": str(self.root / "home")}
        env = patch.dict(os.environ, self.env)
        env.start()
        self.addCleanup(env.stop)
        wf_test_isolation.install(door)
        self.spawns = []
        spawn = patch.object(door, "_spawn_runner", side_effect=lambda r: self.spawns.append(r))
        spawn.start()
        self.addCleanup(spawn.stop)

    def launch_and_finish(self, graph):
        reply = door.act_run({"graph": graph})
        self.assertIn("run_id", reply, reply)
        proc = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", reply["run_id"]],
                              env={**os.environ, **self.env}, capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return reply["run_id"]

    def test_wait_returns_the_named_node_output(self):
        run_id = self.launch_and_finish(TWO_SCHEMAS)
        out = door.act_wait({"run_id": run_id})
        self.assertEqual(out["status"], "done", out)
        self.assertEqual(out["result"], {"node": "judge", "status": "done",
                                         "output": {"verdict": "ship", "score": 0.9}})
        self.assertEqual(door.act_status({"run_id": run_id})["result"], out["result"])

    def test_absent_key_leaves_status_shape_unchanged(self):
        graph = {k: v for k, v in TWO_SCHEMAS.items() if k != "result"}
        run_id = self.launch_and_finish(graph)
        out = door.act_status({"run_id": run_id})
        self.assertEqual(out["status"], "done", out)
        self.assertNotIn("result", out)

    def test_missing_node_refused_at_run_naming_the_key(self):
        reply = door.act_run({"graph": {**TWO_SCHEMAS, "result": "nope"}})
        self.assertNotIn("run_id", reply, reply)
        self.assertIn("result", json.dumps(reply))
        self.assertIn("nope", json.dumps(reply))
        self.assertEqual(self.spawns, [])
        self.assertFalse((self.root / "runs").exists() and any((self.root / "runs").iterdir()))

    def test_gate_node_refused_at_run_naming_the_key(self):
        graph = {"name": "gate158", "result": "ask", "nodes": [
            {"id": "ask", "type": "gate", "question": "ship?", "options": ["yes", "no"]}]}
        reply = door.act_run({"graph": graph})
        self.assertNotIn("run_id", reply, reply)
        self.assertIn("result", json.dumps(reply))
        self.assertIn("gate", json.dumps(reply))
        self.assertEqual(self.spawns, [])

    def test_non_string_refused(self):
        for bad in (1, None, ["judge"], {"node": "judge"}, ""):
            reply = door.act_run({"graph": {**TWO_SCHEMAS, "result": bad}})
            self.assertNotIn("run_id", reply, (bad, reply))
            self.assertIn("result", json.dumps(reply))

    def test_result_does_not_move_node_fingerprints(self):
        common = door._common
        bare = {k: v for k, v in TWO_SCHEMAS.items() if k != "result"}
        self.assertEqual(common.graph_fingerprint(TWO_SCHEMAS), common.graph_fingerprint(bare))
        self.assertEqual(common.source_digest(TWO_SCHEMAS), common.source_digest(bare))


if __name__ == "__main__":
    unittest.main()
