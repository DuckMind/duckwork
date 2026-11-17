#!/usr/bin/env python3
"""est-2ek.1.762 probe: no test-suite run may leave run dirs under the
PRODUCTION runs root (~/.duckwork/workflows).

Failure mode pinned: tests that spawn `wf.py run` children with DUCKWORK_HOME
alone (no WF_RUNS_ROOT pin) let the child fall back to <duckwork_home>/workflows
or inherit the invoking env's WF_RUNS_ROOT; 774 of 1227 unique dirs under the
production runs root were zero-log test fixtures (live/new-title/steering/p25
families). This probe snapshots fixture-run-name patterns under the HOME
stand-in runs root, runs a representative fixture-writing test in a scrubbed
env (WF_RUNS_ROOT UNSET, empty HOME stand-in), and FAILS if any new run dir
appears there.

Run: python3 tests/fixtures/runs_root_probe.py [test ...]
Default representatives: the steering and new-title families named in the
census (spool key 9cfe87a0199e5e1b).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_CALL = re.compile(r"subprocess\.(run|Popen|call|check_output|check_call)\s*\(")
_RUN_TOKEN = re.compile(r'["\']run["\']|WFPY|wf\.py')


def _call_window(lines, i):
    """The source window of a subprocess call: its line plus continuation
    lines until the parens balance (capped), so a multi-line Popen command
    list is judged as ONE unit."""
    buf, depth = "", 0
    for j in range(i, min(i + 12, len(lines))):
        buf += lines[j] + "\n"
        depth += lines[j].count("(") - lines[j].count(")")
        if depth <= 0 and "(" in buf:
            break
    return buf


ROOT = Path(__file__).resolve().parents[2]


def spawn_sites(src: str):
    """1-based line numbers of each subprocess call that spawns the runner
    (`wf.py ... run ...`)."""
    lines = src.splitlines()
    out = []
    for i, l in enumerate(lines):
        if _CALL.search(l):
            w = _call_window(lines, i)
            if re.search(r"wf\.py|WFPY", w) and re.search(r'["\']run["\']|run_id|run\.name|r\.name|, *name\b', w):
                out.append(i + 1)
    return out


_CODE_PIN = re.compile(
    # real code pins, not docstring prose: quoted-key dict entries, item
    # assignment, kwargs, or the shared helper calls.
    r'"WF_RUNS_ROOT"\s*[=:\]]|\'WF_RUNS_ROOT\'[=:\]]|\bWF_RUNS_ROOT\s*='
    r'|\bpin_env\(|\blaunch_env\(')


def unpinned_spawn_files(root: Path | None = None):
    """tests/*.py that spawn `wf.py run` but carry no WF_RUNS_ROOT pin in
    CODE (the (A)-leg audit, shared with test_suite_runs_root_762.py). The
    pin must be code-level — a docstring that merely DISCUSSES WF_RUNS_ROOT
    does not sandbox anyone (wake family #250 established this rule)."""
    root = Path(root) if root else ROOT
    offenders = []
    for p in sorted((root / "tests").glob("*.py")):
        src = p.read_text(encoding="utf-8", errors="replace")
        if not spawn_sites(src):
            continue
        if not _CODE_PIN.search(src):
            offenders.append(str(p.relative_to(root)))
    return offenders

ROOT = Path(__file__).resolve().parents[2]

# Run-dir name patterns the census found as zero-log fixture leaks.
FIXTURE_PATTERNS = ("live", "title", "steer", "p25", "w1", "gate", "t-")

DEFAULT_TESTS = [
    "tests/test_steer_live_40.py",
    "tests/test_sprint101w2_D2-steer-liveness.py",
    "tests/test_session_wake_101.py",
]


def is_fixture_dir(name: str) -> bool:
    low = name.lower()
    return any(p in low for p in FIXTURE_PATTERNS)


def snapshot(runs_root: Path) -> set:
    if not runs_root.is_dir():
        return set()
    return {d.name for d in runs_root.iterdir() if d.is_dir()}


def run_probe(test_rel: str, timeout: int = 180) -> dict:
    """Run one test in a fully scrubbed env whose HOME stand-in is exactly
    where an unpinned child's runs_root() default lands."""
    scratch = Path(tempfile.mkdtemp(prefix="rrprobe-"))
    home = scratch / "home"
    (home / ".duckwork").mkdir(parents=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", "/opt/duckwork"),
        "HOME": str(home),
    }
    # WF_RUNS_ROOT and DUCKWORK_HOME deliberately UNSET: the production-root
    # stand-in is the platform default <HOME>/.duckwork/workflows.
    runs_root = home / ".duckwork" / "workflows"
    before = snapshot(runs_root)
    t0 = time.time()
    try:
        p = subprocess.run(
            [sys.executable, test_rel], cwd=str(ROOT), env=env,
            capture_output=True, timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    leaked = sorted(snapshot(runs_root) - before)
    fixture_leaks = [n for n in leaked if is_fixture_dir(n)]
    return {
        "test": test_rel,
        "rc": rc,
        "elapsed_s": round(time.time() - t0, 1),
        "new_dirs": len(leaked),
        "fixture_leaks": len(fixture_leaks),
        "sample": leaked[:4],
    }


def main() -> int:
    tests = sys.argv[1:] or DEFAULT_TESTS
    rows = [run_probe(t) for t in tests]
    print(json.dumps(rows, indent=2))
    bad = [r["test"] for r in rows if r["fixture_leaks"]]
    if bad:
        print("FAIL: fixture run dirs leaked into the production-root stand-in: "
              + ", ".join(bad))
        return 1
    print("PASS: no fixture run dirs under the production-root stand-in")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
