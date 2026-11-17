#!/usr/bin/env python3
"""1.1 door contracts: advisory keyed claims, no implicit resume, opt-in source."""
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_11", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71_door15; _iso71_door15.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
G = {"name": "door11", "nodes": [{"id": "x", "type": "echo", "output": {"ok": True}}]}

class DoorLane(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.root),
                                   "DUCKWORK_HOME": str(self.root / "home")})
        env.start()
        self.addCleanup(env.stop)
        self.spawns = []
        spawn = patch.object(door, "_spawn_runner", side_effect=lambda r: self.spawns.append(r))
        spawn.start()
        self.addCleanup(spawn.stop)

    def test_claim_status_interrupted_terminal_collision_and_rows(self):
        key = "team/review-1"
        self.assertEqual(door.act_status({"lane_key": key}),
                         {"lane_key": key, "run_id": None, "unfinished": False})
        a = door.act_run({"graph": G, "lane_key": key, "team": "team"})
        rid = a["run_id"]
        p, lock = door._lane_paths(key)
        self.assertEqual(p.name, hashlib.sha256(key.encode()).hexdigest()[:16] + ".json")
        self.assertTrue(lock.exists())
        self.assertEqual(json.loads(p.read_text())["run_id"], rid)
        self.assertTrue((self.root / rid / "nodes").is_dir())
        self.assertTrue((self.root / rid / "run.json").exists())
        row = door.act_status({"lane_key": key})
        self.assertEqual(row["run_id"], rid)
        self.assertTrue(row["needs_resume"])
        self.assertFalse(row["runner_live"])
        self.assertNotIn("working", row)
        self.assertEqual(len(self.spawns), 1)
        b = door.act_run({"graph": G, "lane_key": key})
        self.assertEqual(b["run_id"], rid)
        self.assertTrue(b["deduped"])
        self.assertTrue(b["needs_resume"])
        self.assertEqual(len(self.spawns), 1)
        listing = next(r for r in door.act_list({})["runs"] if r["run_id"] == rid)
        self.assertEqual((listing["lane_key"], listing["team"]), (key, "team"))
        with patch.object(door, "run_state", return_value={"status": "stopped"}):
            c = door.act_run({"graph": G, "lane_key": key})
        self.assertNotEqual(c["run_id"], rid)
        self.assertEqual(len(self.spawns), 2)
        self.assertEqual(json.loads(p.read_text())["run_id"], c["run_id"])
        p.write_text(json.dumps({"lane_key": "different", "run_id": rid}))
        self.assertEqual(door.act_status({"lane_key": key}), {"error": "lane_key hash collision"})
        self.assertEqual(door.act_run({"graph": G, "lane_key": key}), {"error": "lane_key hash collision"})
        self.assertEqual(len(self.spawns), 2)

    def test_claim_write_boundaries_and_concurrent_claim(self):
        from concurrent.futures import ThreadPoolExecutor
        key = "team/boundary"
        with patch.object(door, "_spawn_runner", side_effect=RuntimeError("killed after entry")):
            with self.assertRaisesRegex(RuntimeError, "after entry"):
                door.act_run({"graph": G, "lane_key": key})
        entry = json.loads(door._lane_paths(key)[0].read_text())
        again = door.act_run({"graph": G, "lane_key": key})
        self.assertEqual(again["run_id"], entry["run_id"])
        self.assertTrue(again["needs_resume"])
        self.assertEqual(self.spawns, [])
        original = door.run_state
        def terminal_once(r):
            if r.name == entry["run_id"]:
                return {"status": "stopped"}
            return original(r)
        with patch.object(door, "run_state", side_effect=terminal_once):
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(lambda _: door.act_run({"graph": G, "lane_key": key}), range(2)))
        fresh = [o for o in outcomes if not o.get("deduped")]
        deduped = [o for o in outcomes if o.get("deduped")]
        self.assertEqual((len(fresh), len(deduped)), (1, 1))
        self.assertEqual(fresh[0]["run_id"], deduped[0]["run_id"])
        self.assertEqual(len(self.spawns), 1)

    def test_provenance_opt_in_and_legacy_bytes(self):
        graph = dict(G)
        saved = door.act_save({"graph": graph, "name": "solo"})
        self.assertEqual(saved["saved"], "solo")
        path = door.library_root() / "solo.json"
        self.assertEqual(path.read_text(), json.dumps(dict(graph, name="solo"), ensure_ascii=False, indent=2))
        legacy = door.act_library({})["library"][0]
        self.assertNotIn("owner", legacy)
        solo_run = door.act_run({"from": "solo"})
        self.assertNotIn("graph_source", json.loads((self.root / solo_run["run_id"] / "run.json").read_text()))
        door.act_save({"graph": G, "name": "solo", "source": "repo/graph.json"})
        prov = json.loads(path.read_text())["provenance"]
        self.assertEqual(prov["source_digest"], door._common.source_digest(G))
        self.assertEqual(prov["owner"], "default")
        self.assertEqual(door.act_library({})["library"][0]["source_digest"], prov["source_digest"])
        sourced = door.act_run({"from": "solo"})
        meta = json.loads((self.root / sourced["run_id"] / "run.json").read_text())
        self.assertEqual(meta["graph_source"], {"name": "solo", "owner": "default",
                                                "source": "repo/graph.json", "source_digest": prov["source_digest"]})
        self.assertIn("source", door.act_save({"graph": G, "source": "x" * 201})["error"])
        with patch.dict(os.environ, {"DUCKWORK_HOME": str(self.root / "profiles" / "reviewer")}):
            door.act_save({"graph": G, "name": "named"})
            self.assertEqual(json.loads((door.library_root() / "named.json").read_text())["provenance"]["owner"],
                             "reviewer")

if __name__ == "__main__":
    unittest.main()
