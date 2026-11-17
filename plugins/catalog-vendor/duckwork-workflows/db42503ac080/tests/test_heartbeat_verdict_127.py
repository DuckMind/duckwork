"""duckwork-workflows#127 (jam-h1, est-zsws): runner-derived heartbeat verdict per
running node + one-line run-level explain — pure read-model derivation, zero new
persisted surface, no child cooperation.

Two halves:
1. Pure units over wfcommon.heartbeat / wfcommon.run_explain (no IO).
2. A door fixture on the test_current_attempt_metrics.py fake-child pattern: a
   RUNNING node whose verified child's session row has a STALE last_activity_at
   must surface nodes[n].heartbeat.stalled True, and the run-level one-line
   `explain` must name the stalled node; a fresh artifact under the node's child
   work dir (the #128 progress channel) counts as evidence and un-stalls it; a
   terminal run ships no explain and pending nodes gain no heartbeat.

Stdlib only. The child DB home is the test's scratch DUCKWORK_HOME (never the
lane's state.db); WF_RUNS_ROOT is pinned via the est-2ek.1.762 fixture helper.
"""
import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def _load_iso762():
    spec = importlib.util.spec_from_file_location(
        "wf_spawn_isolation_762_127", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
pin_env = _load_iso762().pin_env

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

wfcommon = load('heartbeat_verdict_wfcommon', ROOT / 'wfcommon.py')
door = load('heartbeat_verdict_door', ROOT / '__init__.py')


class HeartbeatPure(unittest.TestCase):
    """The derivation itself: alive from verified liveness, age = the freshest
    known evidence among {idle_s, artifact mtime_age}, stall only from KNOWN
    age past the threshold — never inferred from absence."""

    def test_live_fresh_child_is_not_stalled(self):
        hb = wfcommon.heartbeat({"live": 1, "idle_s": 30})
        self.assertEqual(hb["alive"], True)
        self.assertEqual(hb["last_evidence_age_s"], 30)
        self.assertEqual(hb["stalled"], False)

    def test_live_child_idle_past_threshold_is_stalled(self):
        hb = wfcommon.heartbeat({"live": 1, "idle_s": 900})
        self.assertEqual(hb["alive"], True)
        self.assertEqual(hb["last_evidence_age_s"], 900)
        self.assertEqual(hb["stalled"], True)

    def test_fresh_artifact_evidence_un_stalls_a_stale_session_row(self):
        hb = wfcommon.heartbeat({"live": 1, "idle_s": 900}, {"mtime_age_s": 12})
        self.assertEqual(hb["last_evidence_age_s"], 12)
        self.assertEqual(hb["stalled"], False)

    def test_unknown_age_never_infers_a_stall(self):
        hb = wfcommon.heartbeat({"live": 1, "idle_s": None})
        self.assertIsNone(hb["last_evidence_age_s"])
        self.assertEqual(hb["alive"], True)
        self.assertEqual(hb["stalled"], False)

    def test_no_liveness_is_not_alive_and_never_stalled(self):
        hb = wfcommon.heartbeat({})
        self.assertEqual(hb["alive"], False)
        self.assertEqual(hb["stalled"], False)


class RunExplainPure(unittest.TestCase):
    def test_non_terminal_status_gets_one_line(self):
        out = {"status": "running",
               "nodes": {
                   "build": {"status": "running",
                             "heartbeat": {"alive": True, "stalled": True,
                                           "last_evidence_age_s": 640}},
                   "p1": {"status": "pending", "blocked_by": ["build: running idle 640s"]},
                   "p2": {"status": "pending", "blocked_by": ["build: running"]},
                   "park": {"status": "pending", "parked": {"kind": "ratelimit"}}}}
        line = wfcommon.run_explain(out)
        self.assertIsInstance(line, str)
        self.assertEqual(line.count("\n"), 0)
        self.assertTrue(line.startswith("running: "), line)
        self.assertIn("1 running", line)
        self.assertIn("1 stalled", line)
        self.assertIn("build", line)
        self.assertIn("2 pending", line)
        self.assertIn("blocked by build", line)
        self.assertIn("1 parked", line)

    def test_terminal_status_explains_nothing(self):
        out = {"status": "done", "nodes": {"a": {"status": "done"}}}
        self.assertIsNone(wfcommon.run_explain(out))


class HeartbeatDoor(unittest.TestCase):
    """The acceptance stub: a stale-metrics verified child flips stalled true."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="heartbeat-verdict-127-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        env = patch.dict(os.environ, pin_env(dict(os.environ),
                                              self.home / "workflows",
                                              home=self.home), clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.run_dir = self.home / "workflows" / "hb127"
        (self.run_dir / "nodes").mkdir(parents=True)
        self.node = {"id": "a", "type": "agent", "goal": "fake"}
        graph = {"name": "hb127", "nodes": [self.node]}
        (self.run_dir / "graph.json").write_text(json.dumps(graph))
        (self.run_dir / "run.json").write_text('{"name": "hb127"}')
        self.key = "wf:hb127:a:feedface.00000000"
        self.script = self.home / "sleep.py"
        self.script.write_text("import time\ntime.sleep(120)\n")
        self.db = self.home / "state.db"
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("create table sessions (title text, model text, input_tokens int, "
                      "output_tokens int, cache_read_tokens int, reasoning_tokens int, "
                      "api_call_count int, tool_call_count int, estimated_cost_usd real, "
                      "last_activity_at real, last_activity_description text, ended_at real, "
                      "started_at real)")

    def _wait_visible(self, pid, title):
        for _ in range(200):
            command = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "command="],
                                     capture_output=True, text=True).stdout
            if title in command.split():
                return
            time.sleep(0.01)
        self.fail("fake process did not start: " + title)

    def _live(self, argv_tail):
        """Spawn a live process whose argv carries argv_tail as separate words."""
        p = subprocess.Popen([sys.executable, str(self.script), *argv_tail],
                             env=dict(os.environ))
        self.addCleanup(lambda: (p.poll() is None and p.terminate(), p.wait(timeout=5)))
        return p

    def spawn_running_child(self, last_activity_age_s=900):
        now = time.time()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (f"{self.key}#a1", "fake", 10, 2, 1, 0, 5, 3, 0.25,
                       now - last_activity_age_s, "old work", None, now - 1000))
        # verified runner: a live process whose argv reads `wf.py run hb127`
        runner = self._live(["wf.py", "run", "hb127"])
        (self.run_dir / "wf.pid").write_text(str(runner.pid))
        self._wait_visible(runner.pid, "hb127")
        # verified child: status=running spawn record + skey title in its argv
        child = self._live(["--continue", f"{self.key}#a1"])
        self._wait_visible(child.pid, f"{self.key}#a1")
        title = f"{self.key}#a1"
        (self.run_dir / "nodes" / "a.json").write_text(json.dumps({
            "status": "running", "pid": child.pid, "skey": title, "attempt": 1,
            "started": now - 1000, "log_path": str(self.home / "child.log"),
            "spawn_cmd": [sys.executable, str(self.script), "--continue", title],
            "efp": door.efp({"a": self.node}, self.node),
            "fp_rule_version": wfcommon.FP_RULE_VERSION}))
        return child

    def test_stale_metrics_child_flips_stalled_and_explain_names_it(self):
        self.spawn_running_child(last_activity_age_s=900)
        st = door.act_status({"run_id": "hb127"})
        self.assertEqual(st["nodes"]["a"]["status"], "running")
        hb = st["nodes"]["a"]["heartbeat"]
        self.assertEqual(hb["alive"], True)
        self.assertGreaterEqual(hb["last_evidence_age_s"], 899)
        self.assertEqual(hb["stalled"], True)
        explain = st["explain"]
        self.assertIsInstance(explain, str)
        self.assertIn("stalled", explain)
        self.assertIn("a", explain)

    def test_fresh_artifact_evidence_un_stalls_through_progress(self):
        self.spawn_running_child(last_activity_age_s=900)
        work = self.run_dir / "work" / "a"
        work.mkdir(parents=True)
        art = work / "answer.md"
        art.write_text("# fresh evidence\n")
        st = door.act_status({"run_id": "hb127"})
        self.assertIn("progress", st["nodes"]["a"])      # #128 channel present
        hb = st["nodes"]["a"]["heartbeat"]
        self.assertLess(hb["last_evidence_age_s"], 60)   # the artifact is the evidence
        self.assertEqual(hb["stalled"], False)

    def test_running_without_stall_is_explained_without_stall_words(self):
        self.spawn_running_child(last_activity_age_s=5)
        st = door.act_status({"run_id": "hb127"})
        self.assertEqual(st["nodes"]["a"]["heartbeat"]["stalled"], False)
        self.assertIsInstance(st["explain"], str)
        self.assertNotIn("stalled", st["explain"])

    def test_terminal_run_has_no_explain_and_no_heartbeat(self):
        self.spawn_running_child(last_activity_age_s=900)
        # commit node a (the honest commit shape): the run goes terminal
        (self.run_dir / "nodes" / "a.json").write_text(json.dumps({
            "status": "done", "output": {"r": 1},
            "efp": door.efp({"a": self.node}, self.node),
            "fp_rule_version": wfcommon.FP_RULE_VERSION}))
        st = door.act_status({"run_id": "hb127"})
        self.assertEqual(st["status"], "done")
        self.assertNotIn("explain", st)
        self.assertNotIn("heartbeat", st["nodes"]["a"])

    def test_pending_node_gains_no_heartbeat(self):
        node_b = {"id": "b", "type": "agent", "goal": "later", "after": ["a"]}
        graph = {"name": "hb127", "nodes": [self.node, node_b]}
        (self.run_dir / "graph.json").write_text(json.dumps(graph))
        self.spawn_running_child(last_activity_age_s=900)
        st = door.act_status({"run_id": "hb127"})
        self.assertEqual(st["nodes"]["b"]["status"], "pending")
        self.assertNotIn("heartbeat", st["nodes"]["b"])

    def test_unverified_child_gets_no_alive_claim(self):
        # No spawn record at all: a DB row alone proves no liveness — no
        # heartbeat key on a pending node, and nothing claims alive.
        now = time.time()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (f"{self.key}#a1", "fake", 10, 2, 1, 0, 5, 3, 0.25,
                       now - 900, "orphan", None, now - 1000))
        st = door.act_status({"run_id": "hb127"})
        self.assertNotIn("heartbeat", st["nodes"]["a"])


if __name__ == "__main__":
    unittest.main()
