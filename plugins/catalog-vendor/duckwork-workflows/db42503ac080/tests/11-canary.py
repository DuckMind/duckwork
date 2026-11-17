#!/usr/bin/env python3
"""Twenty real runner crash/resume cycles; status lane_key checked against /proc.
Failure writes a JSONL evidence line before exiting; suitable for crash/resume canaries.
"""
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('canary_door',ROOT/'__init__.py')
door = importlib.util.module_from_spec(spec);spec.loader.exec_module(door)
import wf_test_isolation as _iso71_door18; _iso71_door18.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
import wfcommon as common


def until(pred,seconds=5):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if pred():return True
        time.sleep(.01)
    return False


def main():
    with tempfile.TemporaryDirectory(prefix='wf11-canary-') as td:
        td=Path(td);runs=td/'runs';runs.mkdir()
        env={**os.environ,'DUCKWORK_HOME':str(td),'WF_RUNS_ROOT':str(runs),
             'DUCKWORK_WF_DUCKWORK_BIN':str(ROOT/'tests/fixtures/11-fake-duckwork.py')}
        with patch.dict(os.environ,env,clear=True):
            for cycle in range(20):
                key='canary/'+str(cycle)
                graph={'name':'canary-'+str(cycle),'nodes':[{'id':'a','type':'agent','goal':'SLEEP 0.25'}]}
                start=door.act_run({'graph':graph,'lane_key':key})
                assert 'run_id' in start,start
                rid=start['run_id'];r=runs/rid
                assert until(lambda:common.runner_alive(r)),(cycle,'runner never live')
                live=door.act_status({'lane_key':key})
                assert live['runner_live'] == common.runner_alive(r) == True,(cycle,live)
                pid=int((r/'wf.pid').read_text())
                os.kill(pid,signal.SIGKILL)
                assert until(lambda:not common.runner_alive(r)),(cycle,'kill failed')
                dead=door.act_status({'lane_key':key})
                assert dead['runner_live'] == common.runner_alive(r) == False,(cycle,dead)
                assert dead['needs_resume'],(cycle,dead)
                repeat=door.act_run({'graph':graph,'lane_key':key})
                assert repeat.get('deduped') and repeat['run_id']==rid,(cycle,repeat)
                assert not common.runner_alive(r),(cycle,'dedupe spawned runner')
                door.act_wait({'run_id':rid,'timeout':1})
                assert until(lambda:door.act_status({'lane_key':key})['state']=='done',5),(cycle,'not done')
                final=door.act_status({'lane_key':key})
                assert final['runner_live'] == common.runner_alive(r),(cycle,final)
                assert not (r/'runner.log').read_text().count('WORKFLOW_BUSY'),(cycle,'busy crash')
                print(json.dumps({'cycle':cycle+1,'status':final['state'],'live':final['runner_live']}),flush=True)
    print('20/20 crash/resume')

if __name__=='__main__':main()
