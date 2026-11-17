"""est-jue3: shared parseable-content marker waits — the read_pid_marker shape
introduced by #267 (est-gzmm), lifted out of test_proctree_61b.py so sibling
fixtures reuse ONE helper family instead of each hand-rolling the same wait.

The race class: a marker file becomes visible at OPEN, before its buffered
bytes reach it, so `while not p.exists(): sleep` can exit on an EMPTY file and
the very next read raises ValueError/IndexError (fixture-only race, seen as the
lone red in serial suite run 20261003-074008 ra-pr-deep-wf158). The writers
live in embedded child scripts and non-atomic write_text calls, so the gate
goes on the READER side: wait for PARSEABLE content, never mere existence.

Standards: not a suite case (scripts/suite.py discovers test_*.py only, same
shape as wf_test_isolation.py); stdlib-only; honest timeout (AssertionError).
"""
import json
import time
from pathlib import Path


def read_pid_marker(path, timeout=10.0):
    """Wait until `path` holds parseable ints; return them all. Honest timeout."""
    t = time.time() + timeout
    while True:
        try:
            vals = [int(l) for l in Path(path).read_text().splitlines() if l.strip()]
            if vals:
                return vals
        except (OSError, ValueError):
            pass
        if time.time() >= t:
            raise AssertionError(f"pid marker {path} never held parseable pids within {timeout}s")
        time.sleep(0.02)


def read_json_marker(path, timeout=10.0):
    """Wait until `path` holds parseable JSON; return the parsed object.
    Same gate, same honest timeout as read_pid_marker."""
    t = time.time() + timeout
    while True:
        try:
            return json.loads(Path(path).read_text())
        except (OSError, ValueError):
            pass
        if time.time() >= t:
            raise AssertionError(f"json marker {path} never held parseable json within {timeout}s")
        time.sleep(0.02)
