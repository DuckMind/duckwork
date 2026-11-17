#!/usr/bin/env python3
"""The child launcher is operator-controlled, never a tool argument."""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

os.environ['DUCKWORK_HOME'] = tempfile.mkdtemp(prefix='wf-launcher-test-')
# #71: DUCKWORK_HOME alone loses to the context-local home override — pin the runs
# root beside it so even a guard-refused handle() can never touch estate shelf.
os.environ['WF_RUNS_ROOT'] = str(Path(os.environ['DUCKWORK_HOME']) / 'workflows')
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wf_door_launcher_test', ROOT / '__init__.py')
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)
import wf_test_isolation as _iso71; _iso71.install(wf)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

graph = {'name': 'probe', 'nodes': [{'id': 'a', 'type': 'echo', 'output': 'ok'}]}
result = json.loads(wf.handle({'action': 'run', 'graph': graph, 'duckwork_bin': '/bin/false'}))
assert 'duckwork_bin' in result.get('error', '') and 'not' in result['error'].lower(), result
assert 'duckwork_bin' not in wf.WORKFLOW_PARAMS['properties']

class Context:
    """Core-faithful get_config: plugin-scoped, reserved roots RAISE.

    The real core (duckwork_cli/plugins_state._plugin_relative_segments) rejects
    'plugins'/'model'/'security'/'settings' with ValueError, so the pre-fix fake
    that answered get_config('plugins') modeled an API core never had — which is
    how the illegal cross-plugin read slipped past this test. get_config(key)
    resolves plugins.entries.<id>.settings.<key>, so the real core answers the
    bare relative key with the same value.
    """
    RESERVED = {'model', 'plugins', 'security', 'settings'}
    settings = {'duckwork_bin': '/config/duckwork'}
    def get_config(self, key, default=None):
        if not isinstance(key, str) or '/' in key or key.split('.')[0].lower() in self.RESERVED:
            raise ValueError('Expected a plugin-relative config key such as \'endpoint\' '
                             'or \'retry.policy\'; global, cross-plugin, and traversal '
                             'paths are forbidden')
        cur = self.settings
        for seg in key.split('.'):
            if not isinstance(cur, dict) or seg not in cur:
                return default
            cur = cur[seg]
        return cur

old = os.environ.get('DUCKWORK_WF_DUCKWORK_BIN')
try:
    wf._CTX = Context()
    os.environ['DUCKWORK_WF_DUCKWORK_BIN'] = '/env/duckwork'
    assert wf._duckwork_bin() == '/config/duckwork'
    wf._CTX = None
    assert wf._duckwork_bin() == '/env/duckwork'
finally:
    wf._CTX = None
    if old is None:
        os.environ.pop('DUCKWORK_WF_DUCKWORK_BIN', None)
    else:
        os.environ['DUCKWORK_WF_DUCKWORK_BIN'] = old
print('ALL PASS test_launcher_config')
