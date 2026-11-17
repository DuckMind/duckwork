"""Regression for the roll-last post-exit handoff module (est-w4qa).

est-xwvu9 (upstream duckwork-agent PR #133387, review 5467148429): the runner no
longer dispatches this mechanism and the module is NOT shipped — it lives at
scripts/post_exit_hook.py (outside pack's INCLUDE) for our own distribution
path only. The runner-side dispatch test was removed with the dispatch; what
remains proves the preserved module's own safety contract (registration
validation, never-installing-on-failure, launch-attempt receipts). Source-only
like every other test that executes a scripts/ file (see pack SOURCE_ONLY_TESTS).
"""
import importlib.util
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "post_exit_hook_sourceonly", REPO / "scripts" / "post_exit_hook.py")
assert _spec is not None and _spec.loader is not None
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

# All fixture writes stay on durable work ground, never the platform scratch dir.
FIXTURES = Path(os.environ.get("WF_HOOK_TEST_ROOT",
                               str(Path.home() / ".duckwork" / "work" / "post-exit-hook-fixtures")))


class PostExitHookTest(unittest.TestCase):
    def setUp(self):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=FIXTURES)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_dir = self.root / "workflows" / "roll-last-test"
        self.run_dir.mkdir(parents=True)
        self.outside = self.root / "work" / "duckwork-nightly" / "roll-last-fixture"
        self.outside.mkdir(parents=True)
        self.script = self.outside / "roll_last.sh"
        self.script.write_text('#!/bin/bash\n'
                               f'echo $$ > "{self.outside}/tail.pid"\n'
                               f'echo all_done > "{self.outside}/state"\n')

    def test_registration_refuses_script_inside_runner_tree_and_conflicting_order(self):
        inside = self.run_dir / "nested.sh"
        inside.write_text("#!/bin/bash\n")
        with self.assertRaises(ValueError):
            hook.register(self.run_dir, inside)
        hook.register(self.run_dir, self.script, "0")
        self.assertEqual(hook.register(self.run_dir, self.script, "0")["run_id"], self.run_dir.name)
        with self.assertRaises(ValueError):
            hook.register(self.run_dir, self.script, "1")

    def test_failed_runner_never_installs(self):
        hook.register(self.run_dir, self.script, "0")
        rec = hook.dispatch(self.run_dir, "blocked by failed close")
        self.assertEqual(rec["state"], "held")
        self.assertEqual(rec["attempts"], [])
        self.assertFalse((self.outside / "state").exists())

    def test_launchctl_chain_and_detached_fallback_receipt(self):
        hook.register(self.run_dir, self.script, "0")
        class Failure:
            def __init__(self, rc):
                self.returncode, self.stderr, self.stdout = rc, "guarded", ""
        calls = []
        def launch(argv, **kwargs):
            calls.append(argv[1])
            return Failure({"submit": 134, "bootstrap": 125, "load": 134}[argv[1]])
        with patch.object(hook.subprocess, "run", side_effect=launch):
            rec = hook.dispatch(self.run_dir, "done", launchctl="/bin/launchctl")
        self.assertEqual(calls, ["submit", "bootstrap", "load"])
        self.assertEqual([a["rc"] for a in rec["attempts"]], [134, 125, 134])
        self.assertEqual((rec["state"], rec["method"]), ("dispatched", "double_fork"))
        self.assertEqual(rec["author"], "workflow_runner")
        self.assertEqual((self.outside / "state").read_text().strip(), "all_done")
        self.assertEqual(json.loads((self.run_dir / hook.RECEIPT).read_text()), rec)
        with patch.object(hook.subprocess, "run") as no_relaunch:
            self.assertEqual(hook.dispatch(self.run_dir, "done"), rec)
            no_relaunch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
