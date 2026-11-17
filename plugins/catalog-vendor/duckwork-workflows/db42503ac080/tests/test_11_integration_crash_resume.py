#!/usr/bin/env python3
"""Suite hook for the standalone 20-cycle crash/resume harness."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
class CrashResume(unittest.TestCase):
    def test_twenty_real_runner_cycles(self):
        p=subprocess.run([sys.executable,str(ROOT/'tests/11-canary.py')],
                         text=True,capture_output=True,timeout=80)
        self.assertEqual(p.returncode,0,(p.stdout+'\n'+p.stderr)[-12000:])
        self.assertIn('20/20 crash/resume',p.stdout)
        self.assertEqual(sum('"cycle":' in line for line in p.stdout.splitlines()),20)
if __name__=='__main__': unittest.main()
