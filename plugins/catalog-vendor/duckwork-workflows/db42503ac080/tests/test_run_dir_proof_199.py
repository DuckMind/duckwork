#!/usr/bin/env python3
"""est-2ek.1.199 — durable run-dir proof in act_run + plugin-level orphaned-run status.

The failure shape this run pins: a door launch handed back a run_id whose run
dir never landed under the durable root (neighbours intact, cause unknown), and
the estate ledger slept for hours because the census only ever saw the lane
entry as 'in_progress'/'pending'.

Two plugin-level gates pin this run:

1. act_run durability proof: BEFORE the runner spawns and BEFORE the run_id
   rides back to the caller, the door fsyncs the three mandatory durable files
   (graph.json, run.json, wake_protocol — absence is an explicit failure, never
   a silent skip), fsyncs the run dir, the runs root, and every ancestor dir
   the launch itself created (first-launch durability: an fsynced file in an
   un-fsynced dir can vanish with the dir), then VERIFIES the run dir still
   exists under the resolved durable root. Any failure RAISES, naming the
   attempted path, and the runner is never started — a phantom run_id is never
   handed back and no work begins behind a failed proof. (handle() turns the
   raise into the tool's loud error payload; act_run itself must not swallow
   it.)

2. orphaned-run status: a lane-ledger entry whose run dir does NOT exist on
   disk — the ledger's in-progress claim that the census could not see
   through — surfaces as state 'orphaned' from act_status(lane_key=...) and
   from the act_run dedupe row, instead of a forever-'pending' ghost.

Stdlib only; no network; the spawn is stubbed so nothing ever launches.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = {"name": "proof199", "nodes": [{"id": "x", "type": "echo", "output": {"ok": True}}]}


class RunDirProof199(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.root),
                                      "DUCKWORK_HOME": str(self.root / "home")})
        env.start()
        self.addCleanup(env.stop)
        self.door = load("door199_" + self.id(), ROOT / "__init__.py")
        import wf_test_isolation as _iso71
        _iso71.install(self.door)
        self.spawns = []
        patch.object(self.door, "_spawn_runner",
                     side_effect=lambda r: self.spawns.append(r)).start()
        self.addCleanup(patch.stopall)

    def _launched_dir(self):
        out = self.door.act_run({"graph": G})
        return self.root / out["run_id"]

    # ---- 1. durability proof -------------------------------------------------
    def test_phantom_run_id_raises(self):
        # The phantom shape: the run dir is gone by the time the proof looks at
        # it (simulated by an fsync hook that deletes the dir, standing for
        # "wrote to a non-durable root / the dir vanished"). act_run must raise
        # with the attempted path, never hand back a run_id — and the runner
        # must never have started (blocker 2: proof before work).
        state = {"killed": False}
        real_fsync = os.fsync
        def guess():
            cands = [p for p in self.root.iterdir()
                     if p.is_dir() and "proof199" in p.name]
            return cands[0]
        def killer(fd):
            if not state["killed"]:
                state["killed"] = True
                shutil.rmtree(guess(), ignore_errors=True)
            return real_fsync(fd)
        with patch.object(os, "fsync", side_effect=killer):
            with self.assertRaises(RuntimeError) as cm:
                self.door.act_run({"graph": G})
        msg = str(cm.exception)
        self.assertIn("run dir", msg.lower())
        # the attempted path is named loudly
        attempted = [x for x in msg.split() if "proof199" in x]
        self.assertTrue(attempted, msg)
        self.assertTrue(any(str(self.root) in x for x in attempted), msg)
        self.assertEqual(self.spawns, [], "runner started despite a failed proof")

    def test_fsync_eio_refuses_before_work_starts(self):
        # Blocker 2: an fsync failure must refuse the launch BEFORE the runner
        # starts — a caller retry may not duplicate work that already began.
        def eio(fd):
            raise OSError(5, "injected EIO")
        with patch.object(os, "fsync", side_effect=eio):
            with self.assertRaises(RuntimeError) as cm:
                self.door.act_run({"graph": G})
        self.assertIn("run dir proof FAILED", str(cm.exception))
        self.assertEqual(self.spawns, [], "runner started before the proof refused")

    def test_proof_runs_before_spawn_in_happy_path(self):
        # Ordering gate: at the moment the durability proof's fsyncs run, the
        # stubbed spawn must not yet have recorded anything; the spawn happens
        # only after the full proof passes.
        seen = {"spawns_at_fsync": None}
        real_fsync = os.fsync
        def spy(fd):
            if seen["spawns_at_fsync"] is None:
                seen["spawns_at_fsync"] = len(self.spawns)
            return real_fsync(fd)
        with patch.object(os, "fsync", side_effect=spy):
            out = self.door.act_run({"graph": G})
        self.assertEqual(seen["spawns_at_fsync"], 0,
                         "spawn happened before the durability proof ran")
        self.assertEqual(self.spawns, [self.root / out["run_id"]])

    def test_happy_launch_fsyncs_and_proves(self):
        # A normal launch still returns its run_id (golden keys unchanged) AND
        # the durability proof really fsyncs: files, run dir, and the runs root.
        real_fsync = os.fsync
        fsynced = []
        def spy(fd):
            fsynced.append(os.fstat(fd))
            return real_fsync(fd)
        with patch.object(os, "fsync", side_effect=spy):
            out = self.door.act_run({"graph": G})
        rid = out["run_id"]
        r = self.root / rid
        self.assertEqual(
            {"run_id", "models", "routes", "hint", "card", "lifecycle_notice"},
            set(out))
        self.assertTrue((r / "graph.json").exists() and (r / "run.json").exists())
        self.assertTrue(fsynced, "no fsync calls — the durability proof is a no-op")
        # every fsynced inode must resolve to the run dir, one of its durable
        # files, or the runs root itself
        targets = []
        for st in fsynced:
            for cand in (self.root, r, r / "graph.json", r / "run.json",
                         r / "wake_protocol"):
                try:
                    cst = cand.stat()
                except OSError:
                    continue
                if cst.st_ino == st.st_ino and cst.st_dev == st.st_dev:
                    targets.append(cand)
                    break
        self.assertTrue(any(str(t) == str(self.root) for t in targets),
                        "runs root never fsynced")
        self.assertTrue(any(str(t).startswith(str(r)) for t in targets),
                        "run dir/files never fsynced")

    # ---- fresh-run admission: all three mandatory files are required ---------
    def _fresh_dir(self):
        # A run dir shaped exactly as the door leaves it, minus the file under
        # test. Built through the door itself, then the file is removed to
        # stand for a half-written launch.
        out = self.door.act_run({"graph": G})
        return self.root / out["run_id"]

    def test_missing_graph_json_fails_the_proof(self):
        r = self._fresh_dir()
        (r / "graph.json").unlink()
        with self.assertRaises(RuntimeError) as cm:
            self.door._prove_run_dir(r)
        self.assertIn("graph.json", str(cm.exception))
        self.assertIn(str(r), str(cm.exception))

    def test_missing_run_json_fails_the_proof(self):
        r = self._fresh_dir()
        (r / "run.json").unlink()
        with self.assertRaises(RuntimeError) as cm:
            self.door._prove_run_dir(r)
        self.assertIn("run.json", str(cm.exception))
        self.assertIn(str(r), str(cm.exception))

    def test_missing_wake_protocol_fails_the_proof(self):
        r = self._fresh_dir()
        (r / "wake_protocol").unlink()
        with self.assertRaises(RuntimeError) as cm:
            self.door._prove_run_dir(r)
        self.assertIn("wake_protocol", str(cm.exception))
        self.assertIn(str(r), str(cm.exception))

    def test_first_launch_absent_root_syncs_created_ancestors(self):
        # Blocker 3: mkdir(parents=True) may create the runs root AND its
        # ancestors; every newly-created directory ENTRY must be synchronised,
        # not just the run dir and the root.
        deep = self.root / "a" / "b" / "runs"
        real_fsync = os.fsync
        fsynced = []
        def spy(fd):
            fsynced.append(os.fstat(fd))
            return real_fsync(fd)
        with patch.dict(os.environ, {"WF_RUNS_ROOT": str(deep)}):
            with patch.object(os, "fsync", side_effect=spy):
                out = self.door.act_run({"graph": G})
        got = {(st.st_dev, st.st_ino) for st in fsynced}
        for p in (deep, deep.parent, deep.parent.parent):
            st = p.stat()
            self.assertIn((st.st_dev, st.st_ino), got,
                          f"newly-created ancestor {p} was never fsynced")
        r = deep / out["run_id"]
        self.assertTrue(r.is_dir())

    # ---- 2. orphaned-run status ----------------------------------------------
    def test_missing_run_dir_reports_orphaned(self):
        key = "lane199/orphan"
        a = self.door.act_run({"graph": G, "lane_key": key})
        rid = a["run_id"]
        # The ledger entry CLAIMS the run; the dir is gone (the census-blind state).
        shutil.rmtree(self.root / rid)
        row = self.door.act_status({"lane_key": key})
        self.assertEqual(row["run_id"], rid)
        self.assertEqual(row["state"], "orphaned", row)
        # dedupe row on a re-submit says the same thing, loudly
        again = self.door.act_run({"graph": G, "lane_key": key})
        self.assertTrue(again.get("deduped"), again)
        self.assertEqual(again.get("state"), "orphaned", again)

    def test_live_and_normal_lane_states_unchanged(self):
        # Byte-compat: a normal (non-orphan) lane row keeps the exact key set
        # and its 'pending'/'running' read-model values.
        key = "lane199/normal"
        a = self.door.act_run({"graph": G, "lane_key": key})
        row = self.door.act_status({"lane_key": key})
        self.assertEqual({"lane_key", "run_id", "state", "runner_live",
                          "unfinished", "needs_resume", "last_event_ts"}, set(row))
        self.assertNotEqual(row["state"], "orphaned")
        self.assertEqual(row["run_id"], a["run_id"])

    def test_stub_ctx_poisoned_root_is_a_named_refusal_not_a_phantom(self):
        # The suspect launch shape: a truthy stub _CTX whose get_config can
        # redirect settings.runs_root. If the configured durable root cannot
        # hold/keep the run dir, the door must refuse LOUDLY with the attempted
        # path — never return a run_id the estate census can't see.
        bogus = self.root / "gone-root"
        bogus.mkdir()
        class StubCtx:
            def get_config(self, key, default=None):
                if key == "runs_root":
                    return str(bogus)
                return default
        self.door._CTX = StubCtx()
        def killer(r):
            shutil.rmtree(r, ignore_errors=True)   # dir "never lands"
        # the writer sandbox (wf_test_isolation) keeps the door pinned to the
        # env root; flip the pin so the door resolves the poisoned root exactly
        # as the incident's stub seat did, then restore.
        with patch.dict(os.environ, {"WF_RUNS_ROOT": str(bogus)}):
            with patch.object(self.door, "_spawn_runner", side_effect=killer):
                with self.assertRaises(RuntimeError) as cm:
                    self.door.act_run({"graph": G})
        self.assertIn(str(bogus), str(cm.exception))
        self.assertFalse((bogus / "proof199").exists())
        self.door._CTX = None


if __name__ == "__main__":
    unittest.main(verbosity=2)
