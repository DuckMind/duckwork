#!/usr/bin/env python3
"""#57 — `list` payload gains the per-root provenance rollup (QM digest contract).

Contract (field vocab PINNED by the #52 ruling — renames need zap's digest thread):
  provenance: {"dispatched_by_set": <int>, "total": <int>}
a fold over the run.jsons the list loop ALREADY enumerates (zero extra scans).
An absent `dispatched_by` key or a null value counts toward total only.
Additive key: the SOLO install (no run carries dispatched_by) keeps the v1.0.15
response key set {runs, total, counts} exactly — the F1 emit-only-when-derivable law,
the same law that keeps golden-solo EMPTY.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_57", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)

GRAPH = {"name": "prov57", "nodes": [{"id": "x", "type": "echo", "output": {"ok": True}}]}


def mk_run(root, run_id, run_json_body):
    """Materialise a committed-done run dir; run_json_body is written verbatim to run.json
    (dict -> json, str -> raw text, None -> no run.json at all)."""
    r = root / run_id
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(GRAPH))
    (r / "nodes" / "x.json").write_text(json.dumps(
        {"id": "x", "status": "done", "output": {"ok": True}}))
    if run_json_body is not None:
        text = run_json_body if isinstance(run_json_body, str) else json.dumps(run_json_body)
        (r / "run.json").write_text(text)
    return r


class ProvenanceCounters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "runs"
        self.root.mkdir(parents=True)
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.root),
                                      "DUCKWORK_HOME": str(Path(self.tmp.name) / "home")})
        env.start()
        self.addCleanup(env.stop)

    def test_mixed_root_counts_both_counters(self):
        # (a) mixed census: stamped, absent key, null value, no run.json at all.
        mk_run(self.root, "20260930-000001-stamped-a",
               {"duckwork_bin": "hb", "dispatched_by": "qm-alpha"})
        mk_run(self.root, "20260930-000002-stamped-b",
               {"duckwork_bin": "hb", "dispatched_by": "qm-beta", "team": "qm"})
        mk_run(self.root, "20260930-000003-absent", {"duckwork_bin": "hb"})
        mk_run(self.root, "20260930-000004-null", {"duckwork_bin": "hb", "dispatched_by": None})
        mk_run(self.root, "20260930-000005-norunjson", None)
        out = door.act_list({})
        self.assertEqual(out["provenance"], {"dispatched_by_set": 2, "total": 5}, out)
        # pinned vocab: exactly these two keys, ints, nothing renamed (#52 ruling)
        self.assertEqual(sorted(out["provenance"]), ["dispatched_by_set", "total"])
        self.assertTrue(all(isinstance(v, int) for v in out["provenance"].values()))
        # additive key only: the rest of the response is the pre-#57 shape
        self.assertEqual(sorted(out), ["counts", "provenance", "runs", "total"])
        self.assertEqual(out["total"], out["provenance"]["total"])
        self.assertEqual(len(out["runs"]), 5)

    def test_solo_root_key_set_unchanged(self):
        # (b) solo install: no run carries dispatched_by -> NO provenance key at all
        # (v1.0.15 key set; this is the law golden-solo freezes).
        mk_run(self.root, "20260930-000001-solo-1", {"duckwork_bin": "hb", "name": "solo-1"})
        mk_run(self.root, "20260930-000002-solo-2", {"duckwork_bin": "hb", "name": "solo-2"})
        out = door.act_list({})
        self.assertNotIn("provenance", out)
        self.assertEqual(sorted(out), ["counts", "runs", "total"])
        self.assertEqual(out["total"], 2)

    def test_empty_root_solo_shape(self):
        out = door.act_list({})
        self.assertNotIn("provenance", out)
        self.assertEqual(out["runs"], [])
        self.assertEqual(out["total"], 0)

    def test_fold_is_free_no_extra_scans(self):
        # (c) the rollup is a fold over the run.jsons the loop ALREADY reads: exactly
        # one jload of run.json per enumerated run — the provenance fold adds none.
        mk_run(self.root, "20260930-000001-stamped", {"duckwork_bin": "hb", "dispatched_by": "qm"})
        mk_run(self.root, "20260930-000002-absent", {"duckwork_bin": "hb"})
        calls = []
        real_jload = door.jload

        def spy(p, default=None):
            calls.append(str(p))
            return real_jload(p, default)
        with patch.object(door, "jload", side_effect=spy):
            out = door.act_list({})
        reads = [p for p in calls if p.endswith("run.json")]
        self.assertEqual(len(reads), 2, reads)  # exactly one read per enumerated run
        self.assertEqual(out["provenance"], {"dispatched_by_set": 1, "total": 2})

    def test_malformed_run_json_counts_total_only(self):
        # honest degradation: an unreadable run.json is a total-only run, never a crash
        # and never a fabricated dispatched_by.
        mk_run(self.root, "20260930-000001-stamped", {"duckwork_bin": "hb", "dispatched_by": "qm"})
        mk_run(self.root, "20260930-000002-garbage", "{not json")
        out = door.act_list({})
        self.assertEqual(out["provenance"], {"dispatched_by_set": 1, "total": 2}, out)


if __name__ == "__main__":
    unittest.main()
