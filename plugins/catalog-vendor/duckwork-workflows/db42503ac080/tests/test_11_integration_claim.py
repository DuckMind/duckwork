#!/usr/bin/env python3
"""F3 boundary/claim integration: real door processes + kernel flock; no hook in plugin."""
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
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('lane_e_claim_door', ROOT/'__init__.py')
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71_door18; _iso71_door18.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

class Claim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wf11-claims-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.runs = self.home/'runs'
        self.runs.mkdir()
        self.env = {**os.environ, 'DUCKWORK_HOME':str(self.home), 'WF_RUNS_ROOT':str(self.runs),
                    'DUCKWORK_WF_DUCKWORK_BIN':str(ROOT/'tests/fixtures/11-fake-duckwork.py')}
        self.graph = {'name':'claim-fixture','nodes':[{'id':'a','type':'agent','goal':'SLEEP 2'}]}
        self.graph_file = self.home/'graph.json'
        self.graph_file.write_text(json.dumps(self.graph))

    def terminate_runner(self, run):
        try:
            pid = int((run/'wf.pid').read_text())
            os.kill(pid, 9)
        except (FileNotFoundError, ProcessLookupError):
            return
        # SIGKILL is asynchronous: don't delete a detached runner's files until
        # it has released its ownership lock and can no longer recreate them.
        deadline = time.monotonic() + 8
        while door._common.runner_alive(run) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(door._common.runner_alive(run), 'fixture runner did not exit')

    def claim(self):
        with patch.dict(os.environ,self.env,clear=True):
            return door.act_run({'graph':self.graph,'lane_key':'claim/fixture'})

    def test_three_write_boundaries(self):
        for phase in ('post-run-json','mid-entry','post-entry'):
            with self.subTest(phase=phase):
                p = subprocess.run([sys.executable,str(ROOT/'tests/fixtures/11-claim-wrapper.py'),phase,
                                    str(self.graph_file)],env=self.env,capture_output=True,text=True,timeout=8)
                self.assertEqual(p.returncode,93,(phase,p.stdout,p.stderr))
                # The entry may be absent before publication or point to a fully written
                # incumbent, but may never contain malformed JSON.
                for entry in (self.runs/'lanes').glob('*.json'):
                    doc = json.loads(entry.read_text())
                    self.assertEqual(doc['lane_key'],'claim/fixture')
                response = self.claim()
                self.assertIn('run_id',response,response)
                if phase == 'post-run-json' or phase == 'mid-entry':
                    self.assertFalse(response.get('deduped',False),response)
                else:
                    self.assertTrue(response.get('deduped'),response)
                    self.assertTrue(response['needs_resume'],response)
                # Reset registry+run dirs between independent boundaries.
                import shutil
                for r in self.runs.iterdir():
                    if r.is_dir():
                        if r.name != 'lanes':
                            self.terminate_runner(r)
                        shutil.rmtree(r)

    def test_two_claiming_processes_one_incumbent(self):
        # Two independent interpreters contend for the exact same key.
        script = """import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('door',Path(sys.argv[1])/'__init__.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# The -c child has no tests/ on sys.path: load the test-only pin by explicit path.
iso_spec=importlib.util.spec_from_file_location('wf_test_isolation',Path(sys.argv[1])/'tests'/'wf_test_isolation.py')
iso=importlib.util.module_from_spec(iso_spec);iso_spec.loader.exec_module(iso)
iso.install(m)
print(json.dumps(m.act_run({'graph':json.loads(Path(sys.argv[2]).read_text()),'lane_key':'claim/fixture'})))
"""
        p = [subprocess.Popen([sys.executable,'-c',script,str(ROOT),str(self.graph_file)],env=self.env,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        answers = []
        for proc in p:
            stdout,stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode,0,stderr)
            answers.append(json.loads(stdout))
        self.assertEqual(answers[0]['run_id'],answers[1]['run_id'],answers)
        self.assertEqual(sum(bool(x.get('deduped')) for x in answers),1,answers)
        runs = [r for r in self.runs.iterdir() if (r/'graph.json').exists()]
        self.assertEqual(len(runs),1,runs)
        self.terminate_runner(runs[0])

if __name__ == '__main__': unittest.main()
