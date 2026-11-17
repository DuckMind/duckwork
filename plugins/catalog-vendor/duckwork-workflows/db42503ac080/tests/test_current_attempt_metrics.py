"""Current-attempt heartbeat with real fake child identity; no provider access."""
import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def _load_iso762():
    # est-2ek.1.762: shared launch-env pin helper, exec-loaded by file path
    # (repo convention — a top-level import of a tests/fixtures module would
    # break the test_packaging import-closure from the unpacked package root).
    spec = importlib.util.spec_from_file_location(
        "wf_spawn_isolation_762", Path(__file__).parent / "fixtures" / "wf_spawn_isolation_762.py")
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

door = load('current_attempt_door', ROOT / '__init__.py')
api = load('current_attempt_dashboard', ROOT / 'dashboard' / 'plugin_api.py')
wf = load('current_attempt_writer', ROOT / 'wf.py')

class CurrentAttemptMetrics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='current-attempt-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        # est-2ek.1.762: DUCKWORK_HOME alone is not a sandbox — the ONE resolver
        # ranks an inherited WF_RUNS_ROOT above it, and the fake-runner/child
        # spawns inherit the parent env. Pin both to the test's own home.
        env = patch.dict(os.environ, pin_env(dict(os.environ),
                                              self.home / 'workflows',
                                              home=self.home), clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.run_dir = self.home / 'workflows' / 'heartbeat'
        (self.run_dir / 'nodes').mkdir(parents=True)
        self.node: dict[str, object] = {'id': 'a', 'type': 'agent', 'goal': 'fake'}
        (self.run_dir / 'graph.json').write_text(json.dumps({'name': 'heartbeat', 'nodes': [self.node]}))
        (self.run_dir / 'run.json').write_text('{}')
        self.key = 'wf:heartbeat:a:feedface.unique'
        self.script = self.home / 'sleep.py'
        self.script.write_text('import time\ntime.sleep(45)\n')
        self.db = self.home / 'state.db'
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('create table sessions (title text, model text, input_tokens int, output_tokens int, '
                      'cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, '
                      'estimated_cost_usd real, last_activity_at real, last_activity_description text, '
                      'ended_at real, started_at real)')

    def launch(self, *args):
        p = subprocess.Popen([sys.executable, str(self.script), *args], env=dict(os.environ))
        self.addCleanup(lambda: (p.poll() is None and p.terminate(), p.wait(timeout=5)))
        return p

    def spawn(self, attempt=1, index=None):
        runner_script = self.home / 'wf.py'
        runner_script.write_text('import time\ntime.sleep(45)\n')
        runner = subprocess.Popen([sys.executable, str(runner_script), 'run', self.run_dir.name], env=dict(os.environ))
        self.addCleanup(lambda: (runner.poll() is None and runner.terminate(), runner.wait(timeout=5)))
        (self.run_dir / 'wf.pid').write_text(str(runner.pid))
        title = f'{self.key}#a{attempt}'
        child = self.launch('--continue', title)
        for _ in range(100):
            command = subprocess.run(['ps', '-ww', '-p', str(child.pid), '-o', 'command='],
                                     capture_output=True, text=True).stdout
            if title in command.split():
                break
            time.sleep(0.01)
        else:
            self.fail('fake child did not start')
        wf.write_spawn_record(self.run_dir, self.node, {'a': self.node}, index, attempt,
                              [sys.executable, str(self.script), '--continue', title],
                              self.home / 'child.log', child.pid, self.key)
        rec = json.loads((self.run_dir / 'nodes' / f"a{'' if index is None else f'.{index}'}.json").read_text())
        self.assertEqual((rec['skey'], rec['attempt'], rec['spawn_cmd'][-1]),
                         (self.key, attempt, title))
        return runner, child

    def row(self, attempt, tokens, last, desc, ended):
        return (f'{self.key}#a{attempt}', 'fake', tokens, 2, 1, 0, 1, 1, 0.25,
                last, desc, ended, last - 5)

    def rows(self, data):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('delete from sessions')
            c.executemany('insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?)', data)

    def views(self):
        return door.act_status({'run_id': self.run_dir.name}), api._view(self.run_dir, full=True)

    def fanout(self, with_second_row=True):
        self.node['fanout'] = {'items': ['first', 'second', 'finished'], 'goal': '{item}'}
        (self.run_dir / 'graph.json').write_text(json.dumps({'name': 'heartbeat', 'nodes': [self.node]}))
        self.key = 'wf:heartbeat:a:0:feedface.unique'
        now = time.time()
        rows = [self.row(0, 10, now - 120, 'first activity', None),
                (f'wf:heartbeat:a:2:feedface.unique#a0', 'fake', 30, 2, 1, 0, 1, 1,
                 0.25, now - 1, 'stale completed activity', None, now - 6)]
        if with_second_row:
            rows.append((f'wf:heartbeat:a:1:feedface.unique#a0', 'fake', 20, 2, 1, 0, 1, 1,
                         0.25, now - 60, 'second activity', None, now - 65))
        self.rows(rows)
        (self.run_dir / 'nodes' / 'a.2.json').write_text(json.dumps({
            'status': 'done', 'efp': door.efp({'a': self.node}, self.node)}))
        runner, first = self.spawn(attempt=0)
        second_key = 'wf:heartbeat:a:1:feedface.unique'
        second_title = f'{second_key}#a0'
        second = self.launch('--continue', second_title)
        for _ in range(100):
            command = subprocess.run(['ps', '-ww', '-p', str(second.pid), '-o', 'command='],
                                     capture_output=True, text=True).stdout
            if second_title in command.split():
                break
            time.sleep(0.01)
        else:
            self.fail('second fake child did not start')
        wf.write_spawn_record(self.run_dir, self.node, {'a': self.node}, 1, 0,
                              [sys.executable, str(self.script), '--continue', second_title],
                              self.home / 'second.log', second.pid, second_key)
        rec = json.loads((self.run_dir / 'nodes' / 'a.1.json').read_text())
        self.assertEqual((rec['skey'], rec['attempt'], rec['spawn_cmd'][-1]),
                         (second_key, 0, second_title))
        return now, runner, first, second

    def test_simultaneous_fanout_uses_each_verified_item_not_stale_row(self):
        now, _, _, _ = self.fanout()
        tool, dashboard = self.views()
        node = dashboard['nodes']['a']
        self.assertEqual(tool['nodes']['a']['status'], 'running')
        self.assertEqual(tool['nodes']['a']['metrics']['live'], 2)
        self.assertEqual(tool['nodes']['a']['metrics']['tokens'], '60▸6')
        self.assertEqual(tool['nodes']['a']['metrics']['last'], 'second activity')
        self.assertGreaterEqual(tool['nodes']['a']['metrics']['idle_s'], 59)
        self.assertEqual((node['metrics']['live'], node['metrics']['last_activity']), (2, now - 60))
        self.assertEqual(dashboard['metrics']['live'], 2)
        items = node['item_metrics']
        self.assertEqual([(items[i]['live'], items[i]['last_desc']) for i in range(3)],
                         [(1, 'first activity'), (1, 'second activity'), (0, None)])
        self.assertEqual(items[2]['tokens_in'], 30)  # spend persists, liveness does not

    def test_fanout_spawn_without_session_row_has_unknown_activity(self):
        _, _, _, _ = self.fanout(with_second_row=False)
        tool, dashboard = self.views()
        self.assertEqual(tool['nodes']['a']['metrics']['live'], 2)
        self.assertIsNone(dashboard['nodes']['a']['item_metrics'][1]['last_activity'])
        self.assertEqual(dashboard['nodes']['a']['item_metrics'][1]['live'], 1)
        self.assertEqual(dashboard['nodes']['a']['metrics']['last_desc'], 'first activity')

    def test_fanout_ps_fallback_verifies_both_children(self):
        self.fanout()
        original = Path.read_text
        def no_proc(path, *args, **kwargs):
            if str(path).startswith('/proc/'):
                raise FileNotFoundError(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', no_proc):
            tool, dashboard = self.views()
        self.assertEqual(tool['nodes']['a']['metrics']['live'], 2)
        self.assertEqual(dashboard['nodes']['a']['item_metrics'][1]['live'], 1)

    def test_older_unended_attempt_is_not_current_liveness_or_activity(self):
        now = time.time()
        self.rows([self.row(0, 100, now - 5, 'old activity', None),
                   self.row(1, 7, now - 100, 'current activity', None)])
        self.spawn()
        tool, dashboard = self.views()
        tm, dm = tool['nodes']['a']['metrics'], dashboard['nodes']['a']['metrics']
        self.assertEqual(tool['nodes']['a']['status'], 'running')
        self.assertEqual((tm['live'], dm['live']), (1, 1))
        self.assertEqual(dm['last_desc'], 'current activity')
        self.assertEqual(dm['last_activity'], now - 100)
        self.assertEqual(tm['last'], 'current activity')
        self.assertGreaterEqual(tm['idle_s'], 99)
        self.assertEqual((tm['tokens'], dm['tokens_in'], dm['cost']), ('107▸4', 107, 0.5))

    def test_existing_suffixed_record_still_joins(self):
        now = time.time()
        self.rows([self.row(1, 7, now - 20, 'legacy activity', None)])
        self.spawn()
        path = self.run_dir / 'nodes' / 'a.json'
        rec = json.loads(path.read_text())
        rec['skey'] = f'{self.key}#a1'  # prior hand-written record shape
        path.write_text(json.dumps(rec))
        tool, dashboard = self.views()
        self.assertEqual(tool['nodes']['a']['metrics']['last'], 'legacy activity')
        self.assertEqual(dashboard['nodes']['a']['metrics']['last_activity'], now - 20)

    def test_wrong_attempt_cannot_pass_process_identity(self):
        self.rows([self.row(1, 7, time.time() - 20, 'actual activity', None)])
        self.spawn()
        path = self.run_dir / 'nodes' / 'a.json'
        rec = json.loads(path.read_text())
        rec['attempt'] = 0  # child argv still has #a1
        path.write_text(json.dumps(rec))
        tool, dashboard = self.views()
        self.assertNotIn('live', tool['nodes']['a']['metrics'])
        self.assertEqual(dashboard['nodes']['a']['metrics']['live'], 0)

    def test_unended_historical_row_without_verified_spawn_is_not_live(self):
        now = time.time()
        self.rows([self.row(0, 100, now - 5, 'orphan', None)])
        tool, dashboard = self.views()
        self.assertNotIn('live', tool['nodes']['a']['metrics'])
        self.assertEqual(dashboard['nodes']['a']['metrics']['live'], 0)
        self.assertIsNone(dashboard['nodes']['a']['metrics']['last_activity'])
        self.assertIsNone(dashboard['metrics']['last_activity'])

    def test_current_spawn_without_db_row_has_unknown_idle_not_zero(self):
        self.rows([self.row(0, 100, time.time() - 5, 'orphan', None)])
        self.spawn()
        tool, dashboard = self.views()
        self.assertEqual(tool['nodes']['a']['metrics']['live'], 1)
        self.assertIsNone(tool['nodes']['a']['metrics']['idle_s'])
        self.assertIsNone(tool['nodes']['a']['metrics']['last'])
        self.assertIsNone(dashboard['nodes']['a']['metrics']['last_activity'])

    def test_completed_current_attempt_exposes_cumulative_spend_only(self):
        now = time.time()
        self.rows([self.row(0, 100, now - 5, 'old', None),
                   self.row(1, 7, now - 100, 'finished', now - 90)])
        runner, child = self.spawn()
        child.terminate(); child.wait(timeout=5)
        tool, dashboard = self.views()
        self.assertNotIn('live', tool['nodes']['a']['metrics'])
        self.assertEqual(dashboard['nodes']['a']['metrics']['live'], 0)
        self.assertIsNone(dashboard['nodes']['a']['metrics']['last_activity'])
        self.assertEqual(dashboard['nodes']['a']['metrics']['tokens_in'], 107)
        self.assertEqual(tool['nodes']['a']['status'], 'pending')

    def test_swapped_sql_order_keeps_ended_and_heartbeat_stable(self):
        now = time.time()
        old = self.row(0, 100, now - 5, 'old', None)
        current = self.row(1, 7, now - 100, 'current', now - 90)
        self.spawn()
        snapshots = []
        for rows in ([old, current], [current, old]):
            self.rows(rows)
            metrics = door._common.child_metrics(self.run_dir.name, self.home)[self.key]
            tool, dashboard = self.views()
            snapshots.append((metrics['ended'], tool['nodes']['a']['metrics']['last'],
                              dashboard['nodes']['a']['metrics']['last_desc']))
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(snapshots[0][1:], ('current', 'current'))
        self.assertIsNone(snapshots[0][0])

if __name__ == '__main__':
    unittest.main()
