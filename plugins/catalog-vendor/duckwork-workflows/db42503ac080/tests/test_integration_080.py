#!/usr/bin/env python3
"""Integrated read-model and parser-valid card dedup checks."""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integrated_workflow', ROOT / '__init__.py')
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)
import wf_test_isolation as _iso71_wf17; _iso71_wf17.install(wf)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

class Integrated(unittest.TestCase):
    def test_steer_roundtrip(self):
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT))
        import wf as engine
        with tempfile.TemporaryDirectory(dir=ROOT) as home:
            # #71: DUCKWORK_HOME alone loses to the context-local home override —
            # without the runs-root pin the run lands on the estate shelf and
            # drain_inbox at the sandboxed path sees nothing (the leak shape).
            with patch.dict(os.environ, {'DUCKWORK_HOME': home, 'WF_RUNS_ROOT': str(Path(home) / 'workflows')}), patch.object(wf, '_spawn_runner'):
                result = wf.act_run({'graph': {'name': 'steering', 'nodes': [
                    {'id': 'a', 'type': 'agent', 'goal': 'offline'}]}})
                rid = result['run_id']; run = Path(home) / 'workflows' / rid
                self.assertTrue(wf.act_steer({'run_id': rid, 'node': 'a', 'text': 'first'})['ok'])
                self.assertEqual(engine.drain_inbox(run, set()), {'a': ['first']})
                self.assertTrue(wf.act_steer({'run_id': rid, 'node': 'a', 'text': 'second'})['ok'])
                consumed = set()
                self.assertEqual(engine.drain_inbox(run, consumed), {'a': ['first', 'second']})
                self.assertEqual(engine.drain_inbox(run, consumed), {})

    def test_spawn_projection_is_read_only_and_identity_checked(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            r = Path(td) / 'run'; (r / 'nodes').mkdir(parents=True)
            graph = {'name': 'active', 'nodes': [{'id': 'a', 'type': 'agent', 'goal': 'offline'}]}
            (r / 'graph.json').write_text(json.dumps(graph))
            script = Path(td) / 'wf.py'
            script.write_text('import time\ntime.sleep(20)\n')
            # hk0z (hermetic): runner_alive's root check (RATIFY F1/B3) judges the
            # runner's EFFECTIVE runs root against r.parent, and the #42 resolver
            # lets an owner-pinned settings.runs_root outrank the WF_RUNS_ROOT env.
            # Standalone on a seat whose estate config carries that pin (lane
            # sessions do), the bare DUCKWORK_HOME pass-through below resolves to
            # the estate root, the check says False, live=False, and the
            # projection reads 'pending' — the red: pending != running. Serial CI
            # hid it: its per-file DUCKWORK_HOME (tests/.suite-home) has no config
            # to pin, so the env branch matched. Build the precondition ITSELF:
            # the installed #71 resolver answers settings.runs_root from the
            # CURRENT WF_RUNS_ROOT env, so pinning the env to r.parent makes the
            # liveness law resolve to the scratch root on EVERY seat (pinned or
            # not), and the runner's own env carries the same pin verbatim for
            # the no-pin (CI) path. The assertion semantics are untouched.
            with patch.dict(os.environ, {'WF_RUNS_ROOT': str(r.parent)}):
                runner = subprocess.Popen([sys.executable, str(script), 'run', r.name],
                                          env={**os.environ, 'DUCKWORK_HOME': str(r.parent.parent),
                                               'WF_RUNS_ROOT': str(r.parent)})
                (r / 'wf.pid').write_text(str(runner.pid))
                skey = 'wf:test:a:identity#a0'
                proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)', skey])
                try:
                    rec = {'status': 'running', 'pid': proc.pid, 'skey': skey, 'attempt': 0,
                           'efp': wf.efp({'a': graph['nodes'][0]}, graph['nodes'][0]), 'fp_rule_version': wf._common.FP_RULE_VERSION}
                    (r / 'nodes/a.json').write_text(json.dumps(rec))
                    st = wf.run_state(r)
                    self.assertEqual(st['nodes']['a']['status'], 'running')
                    self.assertEqual(st['nodes']['a']['active_spawn']['pid'], proc.pid)
                    self.assertEqual(wf._common.node_rec(r, graph['nodes'][0], {'a': graph['nodes'][0]})[0], 'pending')
                    # BSD/macOS has no procfs; exercise the real ps fallback on Linux too.
                    from unittest.mock import patch
                    read_text = Path.read_text
                    def no_proc(path, *args, **kwargs):
                        if str(path).startswith('/proc/'):
                            raise FileNotFoundError(str(path))
                        return read_text(path, *args, **kwargs)
                    with patch.object(Path, 'read_text', no_proc):
                        self.assertEqual(wf.run_state(r)['nodes']['a']['status'], 'running')
                    rec['skey'] = 'wrong-identity'; (r / 'nodes/a.json').write_text(json.dumps(rec))
                    with patch.object(Path, 'read_text', no_proc):
                        self.assertEqual(wf.run_state(r)['nodes']['a']['status'], 'pending')
                finally:
                    proc.terminate(); proc.wait(timeout=5)
                    runner.terminate(); runner.wait(timeout=5)

if __name__ == '__main__':
    unittest.main()
