"""est-2ek.1.762 — every spawned-runner test must pin WF_RUNS_ROOT to its own
isolated runs root (the suite-leak tripwire).

Failure mode pinned (feedback census spool key 9cfe87a0199e5e1b): 774 of 1227
unique dirs under the PRODUCTION runs root (~/.duckwork/workflows) were
zero-log test fixtures (live / new-title / steering / p25 families; symlinked
profile roots multiply hits). Root cause: the runs-root resolver precedence
(#42) is

    settings.runs_root  >  WF_RUNS_ROOT env  >  <duckwork_home>/workflows

so a test that spawns `wf.py run` with DUCKWORK_HOME alone INHERITS the invoking
process's WF_RUNS_ROOT — on a production lane that root is the estate library,
and every fixture run lands there. The wake family already self-pins (#250,
est-aywd #257); this suite extends the same law to the whole spawned-runner
family and makes it non-regressable.

Legs:
  (A) STATIC audit — every tests/*.py that spawns `wf.py run` as a child must
      carry a WF_RUNS_ROOT pin in source (literal or via the shared helper
      tests/fixtures/wf_spawn_isolation_762.py). Offenders are named; the suite
      exits 1. This is the leg that catches a NEW unpinned spawn added later.
  (B) BEHAVIOURAL probe — representative fixture-writing tests (steering/live/
      engine/new-title families) run twice in scrubbed envs:
        clean   : WF_RUNS_ROOT UNSET, HOME = scratch stand-in for the
                  production root. FAIL if any new run dir appears under
                  <scratch>/.duckwork/workflows (that is exactly where an
                  unpinned child's default lands) or the test itself goes red.
        hostile : WF_RUNS_ROOT exported to a stray root (the leaked-lane-env
                  repro). FAIL if the test goes red or writes under the stray
                  root — a self-pinned test is immune to both.
  (C) STATIC suite backstop — scripts/suite.py must export a temporary
      WF_RUNS_ROOT for the whole serial run, so even an unpinned future test
      can never reach the production root through the suite.

Red discipline: with the 29 unpinned spawn files unmodified, leg (A) names
them and leg (B) goes red on the steering/engine/v4 reps under the hostile
root. usage: python3 tests/test_suite_runs_root_762.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# est-2ek.1.762: the shared detector/probe is exec-loaded by FILE PATH, not
# imported bare — a top-level import of a tests/fixtures module is outside the
# shipped import closure (test_packaging #105 probe resolves only
# root/tests/dashboard) and REDs the unpacked-package gate.
_spec_probe = importlib.util.spec_from_file_location(
    "runs_root_probe", HERE / "fixtures" / "runs_root_probe.py")
assert _spec_probe and _spec_probe.loader
_probe = importlib.util.module_from_spec(_spec_probe)
_spec_probe.loader.exec_module(_probe)  # noqa: E402  (shared detector + clean probe)

checks = 0
fails = []


def check(name, cond, detail=""):
    global checks
    checks += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:300]))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- (A) static
offenders = _probe.unpinned_spawn_files()
check("(A) every spawned-runner test carries a WF_RUNS_ROOT pin",
      not offenders, f"unpinned spawn files: {offenders}")

# ---------------------------------------------------------------- (B) probe
# One representative per census family: steering, live, engine-lifecycle,
# new-title (door-side). All must be immune to BOTH environments.
REPS = [
    "tests/test_steer_live_40.py",          # steering/live family
    "tests/test_engine.py",                 # engine lifecycle (live) family
    "tests/test_v4_fixes.py",               # legacy live runner family
    "tests/test_authoring_next_cut.py",     # new-title / caller-title (door)
]


def _scrub(home: Path) -> dict:
    return {"PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", "/opt/duckwork"),
            "HOME": str(home)}


def _spawn_runner(test_rel: str, env: dict, timeout: int = 150) -> int:
    try:
        return subprocess.run([sys.executable, test_rel], cwd=str(ROOT),
                              env=env, capture_output=True, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        return 124


def _run_dirs(root: Path) -> set:
    return {d.name for d in root.iterdir() if d.is_dir()} if root.is_dir() else set()


for rep in REPS:
    base = Path(tempfile.mkdtemp(prefix="rr762-"))
    home = base / "home"
    (home / ".duckwork").mkdir(parents=True)
    prod_root = home / ".duckwork" / "workflows"

    # clean leg — WF_RUNS_ROOT UNSET: an unpinned default lands in prod_root
    rc_clean = _spawn_runner(rep, _scrub(home))
    leaked_clean = _run_dirs(prod_root)
    check(f"(B) clean env: {rep} rc=0", rc_clean == 0, f"rc={rc_clean}")
    check(f"(B) clean env: {rep} writes nothing under the production-root stand-in",
          not leaked_clean, f"new dirs: {sorted(leaked_clean)[:4]}")

    # hostile leg — the leaked-lane-env repro: WF_RUNS_ROOT exported
    hostile = base / "hostile"
    henv = _scrub(home)
    henv["WF_RUNS_ROOT"] = str(hostile)
    rc_hostile = _spawn_runner(rep, henv)
    leaked_hostile = _run_dirs(hostile)
    check(f"(B) hostile WF_RUNS_ROOT: {rep} rc=0 (self-pinned, immune)",
          rc_hostile == 0, f"rc={rc_hostile}")
    check(f"(B) hostile WF_RUNS_ROOT: {rep} writes nothing under the stray root",
          not leaked_hostile, f"new dirs: {sorted(leaked_hostile)[:4]}")

# ---------------------------------------------------------------- (C) suite
suite_src = (ROOT / "scripts" / "suite.py").read_text()
check("(C) scripts/suite.py exports an isolated WF_RUNS_ROOT for the run",
      "WF_RUNS_ROOT" in suite_src, "suite.py never sets WF_RUNS_ROOT")

print(f"TOTAL {checks} FAIL {len(fails)}")
if fails:
    print("RED: " + "; ".join(fails))
raise SystemExit(1 if fails else 0)
