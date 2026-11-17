"""Runner identity and truthful public read paths; fixture home is isolated here."""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util
import json
import os
from pathlib import Path
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
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

door = load('live_truth_door_test', ROOT / '__init__.py')
api = load('live_truth_api_test', ROOT / 'dashboard/plugin_api.py')

class LiveTruth(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='live-truth-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        # est-2ek.1.762: DUCKWORK_HOME alone is not a sandbox — the ONE resolver
        # honors an inherited WF_RUNS_ROOT above it, and the launched children
        # (identity-probe stand-ins) must never ride a lane-exported root either.
        self.env = patch.dict(os.environ, pin_env(dict(os.environ),
                                                   self.home / 'workflows',
                                                   home=self.home), clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        (self.home / 'workflows').mkdir()
        self.script = self.home / 'wf.py'
        self.script.write_text('import time\ntime.sleep(30)\n')

    def run_dir(self, name='sample', nodes=None):
        r = self.home / 'workflows' / name
        (r / 'nodes').mkdir(parents=True)
        graph = {'name': name, 'nodes': nodes or [{'id': 'a', 'type': 'agent', 'goal': 'x'}]}
        (r / 'graph.json').write_text(json.dumps(graph))
        (r / 'run.json').write_text('{}')
        return r

    def launch(self, name='sample'):
        p = subprocess.Popen([sys.executable, str(self.script), 'run', name], env=dict(os.environ))
        for _ in range(100):
            if 'wf.py' in subprocess.run(['ps', '-p', str(p.pid), '-o', 'command='],
                                         capture_output=True, text=True).stdout:
                break
            time.sleep(0.01)
        self.addCleanup(lambda: (p.poll() is None and p.terminate(), p.wait(timeout=5)))
        return p

    def paths(self, r):
        st = door.act_status({'run_id': r.name})
        item = next(x for x in door.act_list({})['runs'] if x['run_id'] == r.name)
        short = api._view(r)
        full = api._view(r, full=True)
        self.assertEqual({st['status'], item['status'], short['status'], full['status']}, {st['status']})
        self.assertEqual(st['runner_live'], item['runner_live'])
        return st, full

    def test_dead_runner_incomplete_is_interrupted_not_running(self):
        r = self.run_dir()
        (r / 'events.jsonl').write_text('{"event":"run.started"}\n')
        (r / 'wf.pid').write_text('99999999')
        st, full = self.paths(r)
        self.assertEqual(st['status'], 'interrupted')
        self.assertFalse(st['runner_live'])
        self.assertEqual(full['runner_exit']['reason'], 'crashed (no exit record)')

    def test_non_runner_and_other_run_pid_cannot_claim_liveness(self):
        r = self.run_dir()
        self.run_dir('other')
        for p in (subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']), self.launch('other')):
            self.addCleanup(lambda p=p: (p.poll() is None and p.terminate(), p.wait(timeout=5)))
            (r / 'wf.pid').write_text(str(p.pid))
            st, _ = self.paths(r)
            self.assertEqual(st['status'], 'interrupted')
            self.assertFalse(st['runner_live'])
            self.assertEqual(st['runner_exit']['reason'], 'crashed (no exit record)')

    def test_real_runner_and_machine_gate_stay_running(self):
        r = self.run_dir(nodes=[{'id': 'g', 'type': 'gate', 'wait': {'wait_s': 30}}])
        p = self.launch()
        (r / 'wf.pid').write_text(str(p.pid))
        st, _ = self.paths(r)
        self.assertEqual(st['status'], 'running')
        self.assertTrue(st['runner_live'])
        self.assertNotIn('gate', st)
        p.terminate(); p.wait(timeout=5)
        self.assertEqual(self.paths(r)[0]['status'], 'interrupted')

    def test_stale_spawn_record_never_makes_node_running(self):
        r = self.run_dir()
        node = json.loads((r / 'graph.json').read_text())['nodes'][0]
        byid = {'a': node}
        (r / 'nodes/a.json').write_text(json.dumps({'status': 'running', 'efp': door.efp(byid, node),
                                                     'pid': self.launch('other').pid, 'skey': 'unused', 'fp_rule_version': door._common.FP_RULE_VERSION}))
        (r / 'wf.pid').write_text('99999999')
        st, full = self.paths(r)
        self.assertEqual(st['nodes']['a']['status'], 'pending')
        self.assertEqual(full['nodes']['a']['status'], 'pending')
        self.assertEqual(st['status'], 'interrupted')

    def test_terminal_and_held_stay_valid_without_runner(self):
        for name, state in [('done', 'done'), ('failed', 'failed'), ('stopped', 'stopped'), ('held', 'held')]:
            node = {'id': 'a', 'type': 'gate'} if state == 'held' else {'id': 'a', 'type': 'agent', 'goal': 'x'}
            r = self.run_dir(name, [node])
            (r / 'wf.pid').write_text('99999999')
            if state in ('done', 'failed'):
                (r / 'nodes/a.json').write_text(json.dumps({'status': state, 'efp': door.efp({'a': node}, node), 'fp_rule_version': door._common.FP_RULE_VERSION}))
            elif state == 'stopped':
                (r / 'events.jsonl').write_text('{"event":"run.stopped"}\n')
            self.assertEqual(self.paths(r)[0]['status'], state)

    def test_ps_fallback_checks_identity_and_zombie(self):
        r = self.run_dir()
        p = self.launch()
        (r / 'wf.pid').write_text(str(p.pid))
        original = Path.read_text
        def no_proc(path, *a, **kw):
            if str(path).startswith('/proc/'):
                raise FileNotFoundError(path)
            return original(path, *a, **kw)
        with patch.object(Path, 'read_text', no_proc):
            self.assertTrue(door.runner_alive(r))
            self.assertEqual(door.run_state(r)['status'], 'running')
            p.terminate(); p.wait(timeout=5)
            self.assertFalse(door.runner_alive(r))

    def test_counts_cover_runs_omitted_from_recent_lists(self):
        for i in range(105):
            self.run_dir(f'z{i:03}')
        r = self.run_dir('000-active', [{'id': 'g', 'type': 'gate', 'wait': {'wait_s': 30}}])
        p = self.launch('000-active')
        (r / 'wf.pid').write_text(str(p.pid))
        tool = door.act_list({})
        self.assertEqual(tool.get('counts', {}).get('running'), 1)
        self.assertEqual(tool.get('total'), 106)
        self.assertEqual(len(tool['runs']), 50)
        view = api._list_runs()
        # est-7ps8 repair (zap CHANGES 6033425646): the dashboard MEASURES
        # executed and now always reports it, including a measured zero;
        # act_list's census never measures it. Compare the COMMON status-count
        # portion — whole-dict equality here once forced the dashboard to
        # DROP a real measurement to satisfy the door's key set.
        self.assertEqual({k: v for k, v in view['counts'].items() if k != 'executed'},
                         {k: v for k, v in tool['counts'].items() if k != 'executed'})
        self.assertEqual(view['counts'].get('executed'), 0)  # measured zero rides
        self.assertEqual(view['total'], tool['total'])
        self.assertEqual(len(view['runs']), 100)

    def test_fatal_runner_exit_is_failed_and_wait_does_not_loop(self):
        r = self.run_dir(nodes=[{'id': 'g', 'type': 'gate', 'goal': 'invalid', 'wait': {'wait_s': 30}}])
        graph = json.loads((r / 'graph.json').read_text())
        (r / 'wf.pid').write_text('99999999')
        (r / 'runner_exit.json').write_text(json.dumps({
            'reason': 'crashed: graph invalid', 'graph_fingerprint': door._common.graph_fingerprint(graph), 'fp_rule_version': door._common.FP_RULE_VERSION}))
        self.assertEqual(self.paths(r)[0]['status'], 'failed')
        with patch.object(door, '_spawn_runner') as spawn:
            self.assertEqual(door.act_wait({'run_id': r.name, 'timeout': 0})['status'], 'failed')
            spawn.assert_not_called()

    def test_wait_explicitly_resumes_interrupted(self):
        r = self.run_dir()
        (r / 'wf.pid').write_text('99999999')
        with patch.object(door, '_spawn_runner') as spawn:
            with patch.object(door, 'runner_alive', return_value=False):
                result = door.act_wait({'run_id': r.name, 'timeout': 0})
            self.assertEqual(spawn.call_count, 1)
            self.assertIn('status', result)

if __name__ == '__main__':
    unittest.main()
