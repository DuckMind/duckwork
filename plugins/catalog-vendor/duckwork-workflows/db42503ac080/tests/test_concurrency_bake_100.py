#!/usr/bin/env python3
"""#100: optional graph scheduling limits are owner-clamped at the door.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME PYTHONPATH=/opt/duckwork
     /opt/duckwork/.venv/bin/python tests/test_concurrency_bake_100.py
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_100", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)

BASE = {"name": "limit100", "nodes": [{"id": "a", "type": "echo", "output": 1}]}


class Owner:
    def __init__(self):
        self.settings = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)


class ConcurrencyBake100(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf100-bake-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "home").mkdir()
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.root / "runs"),
                                      "DUCKWORK_HOME": str(self.root / "home")})
        env.start()
        self.addCleanup(env.stop)
        wf_test_isolation.install(door)  # resolver-level pin, not a _CTX substitute
        self.owner = Owner()
        ctx = patch.object(door, "_CTX", self.owner)
        ctx.start()
        self.addCleanup(ctx.stop)
        spawn = patch.object(door, "_spawn_runner")
        self.spawn = spawn.start()
        self.addCleanup(spawn.stop)

    def launch(self, **options):
        graph = {**BASE, **options}
        result = door.act_run({"graph": graph})
        self.assertIn("run_id", result, result)
        path = self.root / "runs" / result["run_id"]
        self.assertTrue(path.is_dir(), str(path))
        return json.loads((path / "run.json").read_text()), path

    def test_absent_is_original_meta_shape(self):
        meta, _ = self.launch()
        # ra-plan#125-1 (est-0sj4): EVERY run stamps plugin_version (derived from
        # plugin.yaml), so the stamp joins the base key set; the concurrency keys
        # stay absent, which is what this test pins.
        self.assertEqual(set(meta), {"name", "duckwork_bin", "started", "fp_rule_version",
                                     "owner", "launch_root", "plugin_version"}, meta)
        self.assertEqual(meta["launch_root"], str(self.root / "runs"))
        self.assertNotIn("concurrency", meta)
        self.assertNotIn("item_concurrency", meta)

    def test_author_clamped_to_default_caps_and_owner_caps(self):
        meta, _ = self.launch(concurrency=20, item_concurrency=30)
        self.assertEqual((meta["concurrency"], meta["item_concurrency"]), (4, 8))
        self.owner.settings.update(max_concurrency=6, max_item_concurrency=3)
        meta, _ = self.launch(concurrency=16, item_concurrency=12)
        self.assertEqual((meta["concurrency"], meta["item_concurrency"]), (6, 3))
        meta, _ = self.launch(concurrency=2, item_concurrency=1)
        self.assertEqual((meta["concurrency"], meta["item_concurrency"]), (2, 1))

    def test_owner_cap_below_runner_default_applies_without_author_knob(self):
        self.owner.settings.update(max_concurrency=2, max_item_concurrency=3)
        meta, _ = self.launch()
        self.assertEqual((meta["concurrency"], meta["item_concurrency"]), (2, 3))

    def test_bad_values_fail_at_submit_before_write(self):
        for key in ("concurrency", "item_concurrency"):
            for value in (0, -1, True, 1.5, "2", None, []):
                with self.subTest(key=key, value=value):
                    result = door.act_run({"graph": {**BASE, key: value}})
                    self.assertIn(key, result.get("error", ""), result)
                    self.assertFalse(list((self.root / "runs").glob("*/run.json")))
        for key in ("max_concurrency", "max_item_concurrency"):
            self.owner.settings[key] = False
            result = door.act_run({"graph": BASE})
            self.assertIn(key, result.get("error", ""), result)
            self.assertFalse(list((self.root / "runs").glob("*/run.json")))
            self.owner.settings.clear()

    def test_node_and_graph_fingerprints_ignore_limits(self):
        base = BASE["nodes"][0]
        changed = {**base, "concurrency": 16, "item_concurrency": 2}
        common = door._common
        self.assertEqual(common.def_hash(base), common.def_hash(changed))
        self.assertEqual(common.graph_fingerprint(BASE),
                         common.graph_fingerprint({**BASE, "concurrency": 16,
                                                   "item_concurrency": 2}))
        self.assertNotEqual(common.def_hash(base), common.def_hash({**base, "output": 2}))


if __name__ == "__main__":
    unittest.main()
