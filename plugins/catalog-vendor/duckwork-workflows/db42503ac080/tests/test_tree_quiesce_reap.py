#!/usr/bin/env python3
"""Tree quarantine reaps its adopted children before publishing dead proof."""
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf

assert wf._set_subreaper(), 'Linux subreaper prerequisite'
passed = True
for mode in ('kill', 'already-dead'):
    with tempfile.TemporaryDirectory(prefix='wf-tree-reap-') as tmp:
        pid_file = Path(tmp) / 'child.pid'
        parent = os.fork()
        if parent == 0:
            os.setsid()
            child = os.fork()
            if child == 0:
                time.sleep(30 if mode == 'kill' else 0.1)
                os._exit(0)
            pid_file.write_text(str(child))
            os._exit(0)
        os.waitpid(parent, 0)
        child = int(pid_file.read_text())
        try:
            if mode == 'already-dead':
                deadline = time.monotonic() + 5
                while wf._proc_alive(child) and time.monotonic() < deadline:
                    time.sleep(0.005)
                assert not wf._proc_alive(child), 'child must have exited'
            proof, stuck = wf._tree_quiesce({child}, parent, 0, 2, term_grace_s=0)
            try:
                os.kill(child, 0)
                reaped = False
            except ProcessLookupError:
                reaped = True
            good = proof == ('dead' if mode == 'kill' else '') and not stuck and reaped
            print(('PASS ' if good else 'FAIL ') + mode + ': adopted child absent at quarantine return',
                  {'proof':proof, 'stuck':stuck, 'reaped':reaped}, flush=True)
            passed = passed and good
        finally:
            if wf._proc_alive(child):
                os.kill(child, signal.SIGKILL)
            try:
                os.waitpid(child, 0)
            except ChildProcessError:
                pass
print('RESULT', 'PASS' if passed else 'FAIL')
sys.exit(0 if passed else 1)
