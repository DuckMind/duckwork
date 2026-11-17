#!/usr/bin/env python3
"""est-7ps8 (note 3) — scripts/suite.py must clean up its temp WF_RUNS_ROOT.

est-2ek.1.762 made the serial suite export a temporary WF_RUNS_ROOT
(`tempfile.mkdtemp(prefix='wf-suite-runs-')`) so an unpinned test can never
reach the production runs root. The dir was never removed: every suite run
leaks another empty wf-suite-runs-* entry under the system temp dir (zap's
non-blocking note on PR#259, comment 6030355791).

Probe: run the real suite.py over a MINIMAL fake repo (two trivially-green
tests, one that spawns a fixture dir into its inherited WF_RUNS_ROOT so the
root is provably non-empty at run end), snapshot the system temp dir before
and after, and fail if a wf-suite-runs-* dir survived the run.

Run: python3 tests/test_suite_tempdir_cleanup_7ps8.py
"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else "  ::  " + str(detail)[:300]))
    if not cond:
        ok = False

fake = Path(tempfile.mkdtemp(prefix="wf7ps8-repo-"))
(fake / "tests").mkdir(parents=True)
(fake / "tests" / "test_trivial_a.py").write_text("print('a ok')\n")
# one test that WRITES into its inherited WF_RUNS_ROOT — the surviving root
# after cleanup must have contained it during the run (non-empty), proving
# the suite really used its temp root before removing it.
(fake / "tests" / "test_fixture_writer_b.py").write_text(
    "import os\n"
    "from pathlib import Path\n"
    "root = os.environ['WF_RUNS_ROOT']\n"
    "(Path(root) / 'fixture-run-under-suite-root').mkdir(parents=True, exist_ok=True)\n"
    "print('b ok')\n")
out = Path(tempfile.mkdtemp(prefix="wf7ps8-out-"))

# Snapshot the scratch dir the suite's mkdtemp will draw from (TMPDIR-aware,
# same base suite.py uses), then run the real script.
snap_base = Path(tempfile.gettempdir())
def leaked():
    return sorted(d.name for d in snap_base.glob("wf-suite-runs-*") if d.is_dir())

before = set(leaked())
# est-2ek.1.808: the test subprocess must not inherit its caller's workflow lane.
(fake / "tests" / "test_lane_env.py").write_text(
    "import json, os\n"
    "from pathlib import Path\n"
    "Path(os.environ['LANE_ENV_OUT']).write_text(json.dumps({k:v for k,v in os.environ.items() if k.startswith('DUCKWORK_WF_')}))\n")
lane_vars = {"DUCKWORK_WF_RUN_DIR": "/foreign/lane", "DUCKWORK_WF_RUN_ID": "foreign",
             "DUCKWORK_WF_STEER_FILE": "/foreign/steer", "DUCKWORK_WF_RUNNER_PID": "4242",
             "DUCKWORK_WF_PROCTREE_SIDECAR": "/foreign/sidecar",
             "DUCKWORK_WF_EFFECTS_FILE": "/foreign/effects"}
env_out = out / "lane-env.json"
env = {**os.environ, **lane_vars, "TMPDIR": str(snap_base),
       "DUCKWORK_WF_DUCKWORK_BIN": "/operator/duckwork", "LANE_ENV_OUT": str(env_out)}
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "suite.py"),
                    str(fake), str(out)],
                   capture_output=True, text=True, timeout=180, env=env)
check("the minimal suite run itself is green",
      r.returncode == 0, f"rc={r.returncode}\n{r.stdout[-400:]}\n{r.stderr[-400:]}")

import json
seen = json.loads(env_out.read_text()) if env_out.exists() else None
check("test child ran and reported its env", seen is not None)
check("test child inherits no workflow lane identity",
      seen == {"DUCKWORK_WF_DUCKWORK_BIN": "/operator/duckwork"}, seen)

new_leaks = [n for n in leaked() if n not in before]
check("suite.py leaves NO wf-suite-runs-* temp dir behind",
      not new_leaks, f"survivors: {new_leaks}")

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
