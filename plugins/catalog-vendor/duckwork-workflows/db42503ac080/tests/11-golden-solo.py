#!/usr/bin/env python3
"""Golden solo capture/compare against v1.0.15 using the SAME fake_duckwork.

python3 tests/11-golden-solo.py capture /path/to/v1.0.15 tests/golden_solo/v1.0.15.json
python3 tests/11-golden-solo.py compare . tests/golden_solo/v1.0.15.json
All execution is in temporary homes. Both sides run identical graph plans.
"""
import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import duckwork_constants as hc

SCENARIOS = {
    'dag': [{'id':'a','type':'agent','goal':'JSON:{"result":"ok"}'},
            {'id':'b','type':'agent','after':['a'],'goal':'continue {a.result}'}],
    'fanout-quorum': [{'id':'a','type':'agent','goal':'LIST: list'},
                      {'id':'b','type':'agent','after':['a'],'fanout':{'items_from':'a.result','goal':'item {item}','quorum':3},'goal':'join'}],
    'when-prune': [{'id':'a','type':'agent','goal':'JSON:{"go":false}'},
                   {'id':'g','type':'gate','after':['a'],'question':'Continue?','options':['yes','no'],
                    'when':"out.a.go == True",'on_skip':'prune'},
                   {'id':'b','type':'agent','after':['g'],'goal':'pruned'}],
    'echo': [{'id':'a','type':'agent','goal':'JSON:{"message":"echo"}','schema':{'type':'object','properties':{'message':{'type':'string'}},'required':['message']}}],
    'retry-partial': [{'id':'a','type':'agent','goal':'DIETEST','schema':{'type':'object','properties':{'result':{'type':'string'}},'required':['result']}}],
    'legacy-ra-sample': [{'id':'review','type':'agent','goal':'Review this change and report the findings.'}],
}


# Integrator fix (merge E): env keys are either set DETERMINISTICALLY by the runner
# or passed through from the harness process (volatile between sessions: PAGER,
# GIT_PAGER, provider keys...). Only the runner-set core is comparable across
# captures; the harness-own session stamps are owner provenance, not run bytes.
# DUCKWORK_WF_RUN_DIR is the F1 sanctioned env delta (scaffold gate ruling).
# DUCKWORK_WF_PROCTREE_* are the #61c sanctioned env deltas: the survivor-registry
# pins (path + per-spawn token) the spawn seam injects for the process-tree
# escape guard. Runner-minted, never owner state; excluded both sides like F1.
RUNNER_ENV_CORE = {'DUCKWORK_HOME', 'DUCKWORK_QUIET_TURN_REPORT_FILE', 'DUCKWORK_WRITE_SAFE_ROOT',
                   'GOLDEN_FAKE', 'FAKE_MODE'}
SANCTIONED_ENV_DELTA = {'DUCKWORK_WF_RUN_DIR',                        # F1; excluded both sides, counted under F1(1)
                        'DUCKWORK_WF_PROCTREE_SIDECAR', 'DUCKWORK_WF_PROCTREE_SPAWN'}  # #61c; excluded both sides

def normalize(value, paths):
    if isinstance(value, dict):
        if 'env_keys' in value and 'argv' in value:   # spawn trace record
            value = dict(value, env_keys=[k for k in value['env_keys']
                                          if (k in RUNNER_ENV_CORE or k.startswith('DUCKWORK_WF_'))
                                          and k not in SANCTIONED_ENV_DELTA])
        return {k: normalize(v, paths) for k,v in sorted(value.items()) if k not in
                {'ts','started','ended','at','saved_at','ms','pid','run_id','started_at','last_activity','last_event_ts',
                 'last_activity_at','elapsed_s','elapsed_ms','last_heartbeat','created_at','duration_s',
                 'committed_at',        # est-2ek.1.765: per-item commit wall-clock (volatile stamp;
                                        # the est-2ek.1.765 fanout law COMMITTED the per-item records,
                                        # so their commit moment rides the record — volatile, like every
                                        # other wall clock in this set)
                 'plugin_version',      # ra-plan#125-1/2 (est-ciin): unconditional provenance stamp —
                                        # sanctioned delta like `started`: its VALUE is the repo's own
                                        # plugin.yaml version (bumps every release), so pinning it would
                                        # re-freeze a volatile; its PRESENCE is proven by the coarse
                                        # tests/test_unconditional_version_stamp.py, not by the golden.
                 'session_id','ui_session_id'}}   # harness session stamp = owner provenance, volatile
    if isinstance(value, list):
        return [normalize(v, paths) for v in value]
    if isinstance(value, str):
        for prefix, replacement in paths:
            value = value.replace(prefix, replacement)
        value = re.sub(r'\b\d{8}-\d{6}(-[A-Za-z0-9_.-]+)?\b', '<RUN>', value)
        value = re.sub(r'(?<=#a)\d+', '<ATTEMPT>', value)
        value = re.sub(r'(wf:<RUN>:[^\s"#]*[0-9a-f]{8})\.[0-9a-f]{6}\b', r'\1.<NONCE>', value)
        value = re.sub(r'(?<![\w])\d{10}(?:\.\d+)?(?![\w])', '<TIME>', value)
    return value


@contextmanager
def _core_home(path):
    token = hc.set_duckwork_home_override(path)
    try:
        yield
    finally:
        hc.reset_duckwork_home_override(token)


def _reset_session_context():
    """est-2ek.1.862: neutralize the core session-identity ContextVars for the
    golden capture. get_session_env prefers a BOUND ContextVar over os.environ,
    so on a host where gateway.session_context is importable and a session was
    ever bound in this process, stripping env alone would still stamp the owner
    keys. reset_session_vars puts every var back to _UNSET ("never bound here")
    which makes get_session_env fall through to the — now stripped — environment.
    On a standalone plugin host without the gateway the ImportError path is the
    status quo: _session_env already reads os.environ only, env-stripping is the
    whole story."""
    try:
        from gateway.session_context import reset_session_vars
    except ImportError:
        return
    reset_session_vars()


def capture(root, after_save=None):
    inherited_override = hc.get_duckwork_home_override()
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location('golden_door', root/'__init__.py')
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    import wf_test_isolation as _iso71_door70; _iso71_door70.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
    result = {}
    with tempfile.TemporaryDirectory(prefix='wf11-golden-') as td:
        td = Path(td)
        home = td/'home'; home.mkdir()
        fake = Path(__file__).resolve().parent/'fixtures/11-golden-fake.py'
        env = {**os.environ, 'DUCKWORK_HOME':str(home), 'DUCKWORK_WF_DUCKWORK_BIN':str(fake),
               'GOLDEN_FAKE':str(root/'tests/fake')}
        # Hermetic capture: wf.py forwards DUCKWORK_WRITE_SAFE_ROOT to children only
        # when the PARENT already exports it (1.0.17 main), so the frozen baseline
        # was captured from a Duckwork seat that exports it while a GitHub runner
        # does not -> the spawn env_keys list depended on the machine (CI-red,
        # workstation-green). Set it deterministically so every capture, on every
        # machine, carries the key; the key stays under comparison (not excluded).
        (td/'safe').mkdir()
        env['DUCKWORK_WRITE_SAFE_ROOT'] = str(td/'safe')
        for key in ('WF_RUNS_ROOT','FAKE_MODE','FAKE_API_CALLS','FAKE_LOG','FAKE_PROMPT_LOG','FAKE_ARGV_LOG'):
            env.pop(key,None)
        # est-2ek.1.862: the golden seat is the FROZEN v1.0.15 seat — no owner
        # identity. The door stamps run.json.owner.{session_id,ui_session_id,
        # platform} from _session_env; an API-inherited DUCKWORK_SESSION_PLATFORM
        # leaked through the dict-merge below and made the frozen baseline
        # (owner.platform null) seat-red / CI-green. Strip the identity keys from
        # the child seat AND neutralize the core ContextVar channel (it outranks
        # os.environ when bound), so a capture launched from a Duckwork seat sees
        # exactly the clean-runner seat on every machine.
        for key in [k for k in env if k.startswith('DUCKWORK_SESSION_')
                    or k.startswith('DUCKWORK_UI_SESSION_')]:
            env.pop(key, None)
        _reset_session_context()
        paths = [(str(Path(__file__).resolve().parents[1]),'<REPO>'),(str(root),'<REPO>'), (str(td),'<TEMP>')]
        # The child runs retain their original seat-default identity (no launch_root).
        # Shield them from an inherited core-home override without altering DUCKWORK_HOME.
        with patch.dict(os.environ, env, clear=True), _core_home(home):
            for label, nodes in SCENARIOS.items():
                trace_file = home/'11-golden-env.jsonl'
                before = len(trace_file.read_text().splitlines()) if trace_file.exists() else 0
                graph = {'name':label,'nodes':nodes}
                if label == 'retry-partial':
                    os.environ['FAKE_MODE'] = 'die_after_json'
                else:
                    os.environ.pop('FAKE_MODE', None)
                if label == 'legacy-ra-sample':
                    # Exercise the inherited owner override at the actual save. The
                    # env pin and installed resolver keep its configured root out;
                    # remove the pin only AFTER save so runs keep v1.0.15 bytes.
                    os.environ['WF_RUNS_ROOT'] = str(home/'workflows')
                    try:
                        with _core_home(inherited_override):
                            save = door.act_save({'graph':graph,'name':'ra-review-golden'})
                            assert 'saved' in save, save
                            if after_save is not None:
                                after_save(home/'workflows')  # probe before any runner spawn
                    finally:
                        os.environ.pop('WF_RUNS_ROOT', None)
                    library = door.act_library({})
                    started = door.act_run({'from':'ra-review-golden'})
                else:
                    library = None
                    started = door.act_run({'graph':graph})
                assert 'run_id' in started, (label,started)
                rid = started['run_id']; r = home/'workflows'/rid
                for _ in range(400):
                    status = door.act_status({'run_id':rid})
                    if status['status'] in ('done','failed','stopped','held') and not status['runner_live']:
                        break
                    time.sleep(.025)
                else:
                    raise AssertionError('run did not settle: '+label)
                waited = door.act_wait({'run_id':rid,'timeout':.1})
                files = {}
                for base in ('graph.json','run.json','events.jsonl'):
                    p = r/base
                    if p.exists():
                        files[base] = ([json.loads(line) for line in p.read_text().splitlines()]
                                       if base.endswith('jsonl') else json.loads(p.read_text()))
                for folder in ('nodes','gates','logs','prompts'):
                    if (r/folder).exists():
                        for p in sorted((r/folder).rglob('*')):
                            if not p.is_file(): continue
                            if p.suffix == '.json':
                                try: files[str(p.relative_to(r))] = json.loads(p.read_text())
                                except json.JSONDecodeError: files[str(p.relative_to(r))] = p.read_text()
                            elif 'prompt' in p.name or p.suffix == '.txt':
                                files[str(p.relative_to(r))] = p.read_text()
                verdict = json.loads((r/'runner_exit.json').read_text()) if (r/'runner_exit.json').exists() else None
                if library is None:
                    library = door.act_library({})
                listing = door.act_list({})
                listing['runs'] = sorted(listing['runs'], key=lambda row: row['name'])
                for file_name, content in files.items():
                    if file_name == 'events.jsonl':
                        # Fanout items finish in real wall-clock order; compare event sequence
                        # except for a contiguous batch of independent item.finished events.
                        for start in range(len(content)):
                            stop = start
                            while stop < len(content) and content[stop].get('event') == content[start].get('event') and content[start].get('event') in ('item.started','item.finished'): stop += 1
                            content[start:stop] = sorted(content[start:stop], key=lambda e:e.get('index',-1))
                spawns = [json.loads(line) for line in trace_file.read_text().splitlines()[before:]]
                spawns.sort(key=lambda s: next((a for a in s['argv'] if '.prompt.md' in a), ''))
                result[label] = normalize({'files':files,'status':status,'wait':waited,
                    'list':listing, 'library':library,
                    'spawn_argv_env_keys':spawns,
                    'verdict':verdict,
                    'run_json_keys':[k for k in sorted(files['run.json'])
                                     if k != 'plugin_version'],     # est-ciin: same sanctioned delta —
                                                                     # the frozen baseline predates the
                                                                     # unconditional stamp; presence is
                                                                     # proven by the coarse test
                                                                     # (list entries are strings, so the
                                                                     # dict-key exclusion alone can't
                                                                     # drop a key NAME from this row)
                    }, paths)
    return result


def main():
    command, root, output = sys.argv[1:4]
    data = capture(root)
    path = Path(output)
    if command == 'capture':
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
        print('captured', len(data), 'scenarios at',path)
    elif command == 'compare':
        # Re-normalize the frozen baseline too: normalization may have been
        # tightened after capture (volatile harness keys); both sides must
        # face the same normalizer or the diff is meaningless.
        expected = normalize(json.loads(path.read_text()), [])
        if expected != data:
            import difflib
            diff = difflib.unified_diff(json.dumps(expected,indent=2,sort_keys=True).splitlines(),
                                        json.dumps(data,indent=2,sort_keys=True).splitlines(),
                                        fromfile=str(path),tofile=str(root),lineterm='')
            print('\n'.join(diff))
            sys.exit(1)
        print('EMPTY diff',len(data),'scenarios; solo run.json key sets match v1.0.15')
    else:
        sys.exit('capture|compare')

if __name__ == '__main__': main()
