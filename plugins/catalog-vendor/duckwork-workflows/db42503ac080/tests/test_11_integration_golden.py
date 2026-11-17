#!/usr/bin/env python3
"""Frozen v1.0.15 solo gate; six real fake_duckwork workflows; no team settings."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GoldenSolo(unittest.TestCase):
    def test_v1015_six_graphs_and_legacy_run_key_set(self):
        p = subprocess.run([sys.executable, str(ROOT/'tests/11-golden-solo.py'),
                            'compare', str(ROOT), str(ROOT/'tests/golden_solo/v1.0.15.json')],
                           capture_output=True, text=True, timeout=80)
        self.assertEqual(p.returncode, 0, (p.stdout+p.stderr)[:18000])
        self.assertIn('EMPTY diff 6 scenarios', p.stdout)

if __name__ == '__main__': unittest.main()
