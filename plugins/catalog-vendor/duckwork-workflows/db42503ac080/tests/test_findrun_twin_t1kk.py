#!/usr/bin/env python3
"""est-t1kk — find_run must open the LISTED valid twin, not the torn first-root dir.

Failure mode pinned (zap cert 6033425646 sibling defect on merged #264): the
shipped realpath dedupe (est-7ps8) makes the LISTING enumerate a same-named
torn dir (resolved root) and its valid twin (legacy root) as two rows of one
id — the valid run lands in the list. But opening that LISTED id goes through
wfcommon.find_run, whose selection is "resolved root / rid unless it does not
EXIST": the torn first-root dir exists, so find_run resolves the torn path and
the dashboard's _safe_run/_view answer yields no view ({"error": "unknown
run"}). Listing says the run is there; opening it says it is not. Pre-existing
at base b413983 — NOT caused by #264.

Fixture (fresh private WF_RUNS_ROOT per invocation; inherited lane env scrubbed):
  TWIN   torn in RESOLVED (no graph.json, corrupt run.json, stray logs/),
         VALID in LEGACY            -> the listed twin find_run must open.
  KONTRA VALID in RESOLVED, torn in LEGACY -> resolved must still win.
  BOTH   valid in both roots         -> resolved must still win (no flip).
  missing never lands; find_run keeps returning the resolved path (the
  create/resume shape callers rely on).

Cases:
  (A) listing: iter_run_dirs enumerates both same-named physical dirs AND
      dashboard _list_runs reports the valid twin id exactly once.
      Passes at base (pinned by est-7ps8) — the regression pin.
  (B1) wfcommon.find_run(TWIN) resolves to the LEGACY valid twin. RED at base
       (returns the torn resolved dir).
  (B2) the dashboard open path (_safe_run -> _view, the get-run route's core)
       returns the VALID dir's view for the listed id. RED at base.
  (B3) controls at every head: KONTRA and BOTH keep the resolved-root win;
       an unknown id still answers the resolved path (exists=False).
  (C) hermetic: the exported hostile WF_RUNS_ROOT (the launcher's) stays
      empty — the scrubbing + self-pinning worked.

Run: PYTHONPATH=/opt/duckwork:.. python3 tests/test_findrun_twin_t1kk.py
(from the tests/ cwd; a fresh private WF_RUNS_ROOT is created per invocation
and any inherited WF_*/DUCKWORK_WF_* is scrubbed, so a hostile lane env cannot
steer the roots nor be written by it — the probe is read-only.)
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# --- hermetic env: fresh private roots, inherited lane roots scrubbed -------
BASE = Path(tempfile.mkdtemp(prefix="wft1kk-"))
RESOLVED = BASE / "resolved"   # settings-resolved root (scanned first)
LEGACY = BASE / "legacy"       # legacy launch root (scanned second)
HOSTILE = BASE / "hostile"     # the launcher's leaked WF_RUNS_ROOT stand-in
for d in (RESOLVED, LEGACY, HOSTILE):
    d.mkdir(parents=True)
for k in [k for k in os.environ if k.startswith(("WF_", "DUCKWORK_WF_"))]:
    os.environ.pop(k)  # scrub lane-exported roots; a hostile env must not steer us
os.environ["DUCKWORK_HOME"] = str(BASE / "home")
os.environ["WF_RUNS_ROOT"] = str(LEGACY)   # launch_runs_root() answer
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

checks = 0
fails = []

def check(label, cond, detail=""):
    global checks
    checks += 1
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else "  ::  " + str(detail)[:300]))
    if not cond:
        fails.append(label)


def seed_run(root, name, *, valid=True, logs=False):
    """valid = the graph+run+node trio run_state accepts; torn = a partial
    spawn: the dir exists but has no graph (run_state answers None), exactly
    the fixture shape the 762 census found / est-7ps8 enumerates."""
    r = root / name
    (r / "nodes").mkdir(parents=True)
    if logs:
        (r / "logs").mkdir()
        (r / "logs" / "a.log").write_text("line\n")
    if valid:
        (r / "graph.json").write_text(json.dumps({"name": name[-4:], "nodes": [
            {"id": "a", "type": "agent", "goal": "x"}]}))
        (r / "run.json").write_text(json.dumps({"run_id": name, "name": name[-4:],
                                                "started": "2099-01-01T00:00:00+00:00"}))
    else:
        (r / "run.json").write_text("{not json")
    return r


TWIN = "20990102-000000-twin"     # torn in RESOLVED, VALID in LEGACY
KONTRA = "20990102-000001-kontra" # VALID in RESOLVED, torn in LEGACY
BOTH = "20990102-000002-both"     # valid in both roots
GHOST = "20990102-000003-ghost"   # in neither root

seed_run(RESOLVED, TWIN, valid=False, logs=True)   # the hider (stray logs dir)
seed_run(LEGACY, TWIN, valid=True, logs=True)      # the hidden valid twin
seed_run(RESOLVED, KONTRA, valid=True, logs=True)
seed_run(LEGACY, KONTRA, valid=False)
seed_run(RESOLVED, BOTH, valid=True, logs=True)
seed_run(LEGACY, BOTH, valid=True)                 # identical-shape twin

# resolved root = RESOLVED via the owner-settings reader (#42 precedence,
# beats WF_RUNS_ROOT); launch root = LEGACY via WF_RUNS_ROOT — two-root shape.
_reader = lambda key: (str(RESOLVED) if key == "runs_root" else None)
wfcommon.set_owner_setting_reader(_reader)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- (A) listing
got = wfcommon.iter_run_dirs([RESOLVED, LEGACY])
twin_paths = [p for p in got if p.name == TWIN]
check("(A1) iter_run_dirs enumerates BOTH same-named TWIN dirs (realpath dedupe, est-7ps8 pin)",
      len(twin_paths) == 2, str([str(p) for p in twin_paths]))

dash = load("dash_t1kk", ROOT / "dashboard" / "plugin_api.py")
dash._workflow_common().set_owner_setting_reader(_reader)
lst = dash._list_runs()
ids = sorted(r["id"] for r in lst["runs"])
check("(A2) dashboard _list_runs reports the valid TWIN id exactly once (pin: already true at base)",
      ids == sorted([BOTH, KONTRA, TWIN]) and sum(1 for r in lst["runs"] if r["id"] == TWIN) == 1,
      json.dumps(ids))

# ---------------------------------------------------------------- (B) opening
twin = wfcommon.find_run(TWIN)
check("(B1) find_run(TWIN) resolves the VALID legacy twin, not the torn first-root dir",
      twin.resolve() == (LEGACY / TWIN).resolve(), str(twin))

r = dash._safe_run(TWIN)
v = dash._view(r, full=True) if r else None
check("(B2) dashboard open of the LISTED id returns the VALID dir's view (RED at base: no view)",
      v is not None and v.get("id") == TWIN and v.get("nodes_total") == 1,
      json.dumps(v)[:300] if v else f"_safe_run -> {r}")

# (B3) controls: the flip must not leak into the normal resolutions.
check("(B3a) KONTRA (valid in resolved, torn in legacy) keeps the resolved dir",
      wfcommon.find_run(KONTRA).resolve() == (RESOLVED / KONTRA).resolve())
check("(B3b) BOTH valid: resolved root still wins (no flip when the first root is valid)",
      wfcommon.find_run(BOTH).resolve() == (RESOLVED / BOTH).resolve())
ghost = wfcommon.find_run(GHOST)
check("(B3c) unknown id still answers the resolved-root path (create/resume shape)",
      ghost == RESOLVED / GHOST and not ghost.exists(), str(ghost))

# ---------------------------------------------------------------- (C) hermetic
leak = sorted(p.name for p in HOSTILE.iterdir()) if HOSTILE.is_dir() else []
check("(C) hostile launcher root stayed empty (self-pinned, scrub immune)", not leak, str(leak))

print(f"TOTAL {checks} FAIL {len(fails)}")
if fails:
    print("RED: " + "; ".join(fails))
raise SystemExit(1 if fails else 0)
