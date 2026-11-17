#!/usr/bin/env python3
"""Executable machine-watch contract: probe transitions and native gate scheduling."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
GRAPH = json.loads((ROOT / 'examples/release/machine-watch.workflow.json').read_text())


def argv(root):
    # 133387 ask #3: the shipped probe roots itself under $DUCKWORK_HOME by
    # default; tests steer the root with the MW_STATE_ROOT override (the
    # probe reads it FIRST), so the executed bytes are the shipped bytes.
    return list(GRAPH['nodes'][1]['wait']['until_argv'])


def check(root, cmd):
    root.mkdir(parents=True, exist_ok=True)
    file = root / 'check_cmd.txt'
    if cmd is None:
        file.unlink(missing_ok=True)
    else:
        file.write_text(cmd)
    p = subprocess.run(argv(root), capture_output=True, text=True, timeout=5,
                     env=dict(os.environ, MW_STATE_ROOT=str(root)))
    return p.returncode, (root / 'probe_broken').exists(), p.stderr


def probe_transitions(tmp):
    s = tmp / 'transitions'
    cases = [('exit 1', 1, False), ('exit 2', 2, True),
             ('exit 1', 1, True), ('true', 0, False)]
    for cmd, rc, sticky in cases:
        got, marked, stderr = check(s, cmd)
        assert (got, marked) == (rc, sticky), (cmd, got, marked)
        if rc == 2:
            assert 'probe broken' in stderr and 'adapter exit 2' in stderr
    assert (s / 'transition.claim').exists()
    assert check(s, 'true')[0] == 1  # unchanged healthy: no second report
    assert check(s, 'exit 1')[0] == 1  # genuine unhealthy re-arms
    assert not (s / 'transition.claim').exists()
    assert check(s, 'true')[0] == 0
    for cmd in (None, '', '  \t  '):
        q = tmp / ('missing' if cmd is None else 'empty' if not cmd else 'blank')
        got, marked, stderr = check(q, cmd)
        assert (got, marked) == (2, True), (cmd, got, marked)
        assert 'probe broken' in stderr
        assert check(q, 'exit 1')[:2] == (1, True)
        assert check(q, 'true')[:2] == (0, False)
    s = tmp / 'broken-retarget'
    assert check(s, 'exit 2')[:2] == (2, True)
    assert check(s, ' ')[0] == 2
    assert (s / 'probe_broken').exists()
    print('PASS probe transition table 1,2,1,0, blank fail-closed, sticky marker')


def native_engine(tmp):
    # Only root/cadence/deadline are redirected; the shipped inline argv is executed.
    os.environ['DUCKWORK_HOME'] = str(tmp / 'home')
    os.environ['WF_RUNS_ROOT'] = str(tmp / 'runs')
    (tmp / 'home').mkdir()
    (tmp / 'home' / 'config.yaml').write_text('{}\n')
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('watch94door', ROOT / '__init__.py')
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    import wf_test_isolation as _iso71
    _iso71.install(door)
    fake = tmp / 'fake_duckwork.py'
    fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, re, sys
q=pathlib.Path(sys.argv[sys.argv.index('--query-file')+1]).read_text()
s=pathlib.Path(os.environ['MW_STATE']); s.mkdir(exist_ok=True,parents=True)
with (pathlib.Path(os.environ['MW_ROOT'])/'children.jsonl').open('a') as f:
 f.write(json.dumps({'kind':'bootstrap' if 'Install the watch probe.' in q else 'report'})+'\\n')
if 'Install the watch probe.' in q:
 cmd=q.split('check_cmd.txt:\\n',1)[1].split('\\n4)',1)[0]
 (s/'check_cmd.txt').write_text(cmd+'\\n')
 out={'watch_name':'test-watch','check_cmd':cmd,'state_written':True}
else:
 if os.environ.get('MW_ACK')=='1':
  (s/'delivered.transition').write_text('test-watch accepted\\n')
 out={'released':True,'report':'test-watch cleared'}
print('```json\\n'+json.dumps(out)+'\\n```',flush=True)
''')
    fake.chmod(0o755)
    door._duckwork_bin = lambda: str(fake)
    procs = {}
    streams = []
    state = tmp / 'state'
    state.mkdir()
    def spawn(run):
        env = dict(os.environ, MW_STATE=str(state), MW_ROOT=str(tmp), MW_ACK='1',
                 MW_STATE_ROOT=str(state))
        f = (run / 'native-runner.log').open('w')
        streams.append(f)
        procs[run.name] = subprocess.Popen(
            [sys.executable, str(ROOT / 'wf.py'), 'run', run.name],
            env=env, stdout=f, stderr=subprocess.STDOUT)
    door._spawn_runner = spawn
    g = copy.deepcopy(GRAPH)
    for n in g['nodes']:
        if 'goal' in n:
            n['goal'] = n['goal'].replace('$DUCKWORK_HOME/machine-watch-example', str(state))
    g['nodes'][1]['wait'].update(until_argv=argv(state), every_s=.15, timeout_s=1.5)
    args = {'graph':g, 'name':'native-machine-watch',
            'run_context':{'watch_name':'test-watch','check_cmd':'true'},
            'lane_key':'example/machine-watch-94'}
    def start():
        r = door.act_run(args)
        assert 'run_id' in r, r
        path = tmp / 'runs' / r['run_id']
        return r, path
    def finish(r, path):
        procs[r['run_id']].wait(timeout=12)
        return json.loads((path / 'runner_exit.json').read_text())
    try:
        first, path = start()
        assert finish(first, path)['reason'] == 'done'
        assert (state / 'delivered.transition').exists()
        # Fresh completed dispatches with the same lane_key MUST NOT spawn report.
        again, path2 = start()
        assert again['run_id'] != first['run_id']
        assert finish(again, path2)['reason'] != 'done'
        events = [json.loads(line) for line in (path2 / 'events.jsonl').read_text().splitlines()]
        assert not any(e['event']=='node.started' and e.get('node')=='report' for e in events)
        # Broken -> blank retarget in one native gate run must never release.
        (state / 'check_cmd.txt').write_text('exit 1')
        # The next dispatch's bootstrap re-installs the seeded command.
        args['run_context']['check_cmd']='exit 2'
        broken, path3 = start()
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            parked = path3 / 'gates/watch.parked.json'
            if parked.exists() and json.loads(parked.read_text()).get('attempt', 0) >= 2:
                break
            time.sleep(.03)
        else:
            raise AssertionError('broken native probe did not park twice')
        assert (state / 'probe_broken').exists()
        assert json.loads(parked.read_text())['last_exit'] == 2
        (state / 'check_cmd.txt').write_text('  ')
        assert finish(broken, path3)['reason'] != 'done'
        assert (state / 'probe_broken').exists()
        delivered = [json.loads(l) for l in (tmp / 'children.jsonl').read_text().splitlines()]
        assert sum(e['kind']=='report' for e in delivered) == 1
        print('PASS native gate release, broken park, empty retarget, completed-run dedup')
    finally:
        for proc in procs.values():
            if proc.poll() is None:
                proc.kill(); proc.wait()
        for f in streams:
            f.close()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        probe_transitions(t)
        native_engine(t)
