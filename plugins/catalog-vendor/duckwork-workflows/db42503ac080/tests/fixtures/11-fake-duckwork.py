#!/usr/bin/env python3
"""Dedicated 1.1 child fixture. Never imports the installed Duckwork installation.

With -p, DUCKWORK_HOME is the estate root; a missing profile is a hard failure,
not an accidental fallback to the launcher's home. TRACE_FILE is an explicit
fixture channel (not inherited by profiled production spawns); without it the
trace is written beside the target state.db. The legacy child behavior is the
unchanged tests/fake_duckwork.py, whose imports are avoided here.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

argv = sys.argv[1:]
env = dict(os.environ)
root = Path(env['DUCKWORK_HOME'])
if '-p' in argv:
    idx = argv.index('-p')
    if idx + 1 >= len(argv):
        sys.exit('profile missing after -p')
    profile = argv[idx + 1]
    home = root / 'profiles' / profile
    if profile == 'default' or not (home / 'config.yaml').is_file():
        sys.exit('unknown profile: ' + profile)
    argv = argv[:idx] + argv[idx + 2:]
else:
    profile, home = None, root
if not argv or argv[0] != 'chat':
    sys.exit('expected chat')
if '--query-file' in argv:
    prompt = Path(argv[argv.index('--query-file') + 1]).read_text()
else:
    prompt = sys.stdin.read()
trace = Path(env.get('DUCKWORK_WF_RUN_DIR', str(home))) / '11-child-trace.jsonl'
trace.parent.mkdir(parents=True, exist_ok=True)
with trace.open('a') as f:
    f.write(json.dumps({'profile': profile, 'home': str(home), 'argv': sys.argv[1:],
                        'env': env, 'prompt': prompt, 'pid': os.getpid()}) + '\n')
if '--continue' in argv:
    title = argv[argv.index('--continue') + 1]
    with sqlite3.connect(home / 'state.db') as db:
        db.execute('create table if not exists sessions (id text primary key, title text, model text, billing_provider text, input_tokens int, output_tokens int, cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, estimated_cost_usd real, last_activity_at real, last_activity_description text, ended_at real, started_at real)')
        t = time.time()
        db.execute('insert or replace into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   ('fixture-' + title, title, 'fixture', 'fixture', 3, 2, 0, 0, 1, 0, 0.0, t, 'fixture', t, t))
if 'SLEEP' in prompt:
    try:
        time.sleep(float(prompt.split('SLEEP', 1)[1].split()[0]))
    except (ValueError, IndexError):
        pass
if 'JSON:' in prompt:
    payload = next(line.split('JSON:', 1)[1].strip() for line in prompt.splitlines() if 'JSON:' in line)
else:
    payload = json.dumps({'result': 'ok'})
print('```json\n' + payload + '\n```')
