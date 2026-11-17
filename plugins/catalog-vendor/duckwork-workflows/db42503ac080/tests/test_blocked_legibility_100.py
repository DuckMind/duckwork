#!/usr/bin/env python3
"""#100: run.blocked preserves its old verdict and adds causal context.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME PYTHONPATH=/opt/duckwork
     /opt/duckwork/.venv/bin/python tests/test_blocked_legibility_100.py
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
spec = importlib.util.spec_from_file_location("wf_door_blocked_100", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)


class BlockedLegibility100(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf100-blocked-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.runs = self.root / "runs"
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.runs),
                                      "DUCKWORK_HOME": str(self.home),
                                      "DUCKWORK_WF_DUCKWORK_BIN": str(ROOT / "tests" / "fake"),
                                      "FAKE_LOG": str(self.root / "fake.log")})
        env.start()
        self.addCleanup(env.stop)
        wf_test_isolation.install(door)  # settings.runs_root may outrank the env without this
        spawn = patch.object(door, "_spawn_runner")
        spawn.start()
        self.addCleanup(spawn.stop)
        self.assertEqual(door.runs_root(), self.runs)

    def test_failed_run_adds_context_without_changing_old_fields_or_emit(self):
        graph = {"name": "blocked100", "nodes": [
            {"id": "seed", "type": "echo", "output": {"seed": 1}},
            {"id": "bad", "type": "agent", "goal": "FAILME please"},
            {"id": "join", "type": "echo", "after": ["seed", "bad"], "output": 2},
            {"id": "later", "type": "echo", "after": ["join"], "output": 3},
            {"id": "unrelated", "type": "echo", "output": 4},
        ]}
        started = door._create_run({"graph": graph}, graph, None, {}, {}, [],
                                   concurrency_meta={})
        self.assertIn("run_id", started, started)
        run_id = started["run_id"]
        r = self.runs / run_id
        meta = json.loads((r / "run.json").read_text())
        self.assertNotIn("concurrency", meta)
        self.assertNotIn("item_concurrency", meta)
        run = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                             env=os.environ.copy(), capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), f"WORKFLOW_FAILED {run_id} (bad)")
        event = next(json.loads(line) for line in (r / "events.jsonl").read_text().splitlines()
                     if json.loads(line).get("event") == "run.blocked")
        self.assertEqual(event["failed"], ["bad"])
        self.assertEqual(event["blocked"], ["join", "later"])
        self.assertEqual(event["unconverged"], ["seed"])
        self.assertEqual(event["blocked_by"], {"join": ["bad"], "later": ["bad"]})
        # est-ij0 adds residue (cause classes + committed verdicts) and the
        # dead-letter attempt ledger; the #100 fields above stay byte-identical.
        self.assertEqual(set(event), {"ts", "event", "failed", "blocked",
                                      "unconverged", "blocked_by", "residue", "dead_letter"})
        self.assertEqual(event["residue"], {"data_dead": ["join", "later"], "order_dead": [],
                                            "verdicts": {"seed": {"status": "done", "verdict": None}}})
        self.assertEqual(set(event["dead_letter"]), {"bad"})
        self.assertEqual(json.loads((r / "nodes" / "seed.json").read_text())["status"], "done")
        self.assertFalse((r / "nodes" / "join.json").exists())

    def test_closure_handles_partial_and_two_failed_roots_without_unrelated_work(self):
        nodes = [{"id": "partial"}, {"id": "good"}, {"id": "fail1"},
                 {"id": "fail2"},
                 {"id": "branch", "after": ["partial", "good", "fail1"]},
                 {"id": "join", "after": ["branch", "fail2"]},
                 {"id": "unrelated"}]
        states = {"partial": "partial", "good": "done", "fail1": "failed",
                  "fail2": "failed", "branch": "pending", "join": "pending",
                  "unrelated": "done"}
        self.assertEqual(door._common.blocked_legibility(nodes, states, ["branch", "join"]),
                         (["partial", "good"], {"branch": ["fail1"],
                                                "join": ["fail1", "fail2"]}))
        self.assertEqual(door._common.blocked_legibility(nodes, states, []), ([], {}))


if __name__ == "__main__":
    unittest.main()
