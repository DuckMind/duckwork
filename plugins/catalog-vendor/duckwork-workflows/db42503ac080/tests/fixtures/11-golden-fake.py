#!/usr/bin/env python3
"""Identical solo child wrapper for both tag and candidate; records env key sets.
The baseline fake_duckwork.py remains untouched and executes via os.execv.
"""
import json
import os
from pathlib import Path
import sys

home=Path(os.environ['DUCKWORK_HOME'])
with (home/'11-golden-env.jsonl').open('a') as f:
    f.write(json.dumps({'argv':sys.argv[1:],'env_keys':sorted(os.environ)})+'\n')
os.execv(os.environ['GOLDEN_FAKE'],[os.environ['GOLDEN_FAKE'],*sys.argv[1:]])
