#!/usr/bin/env python3
"""The dashboard reports its MEASURED executed count, INCLUDING a measured zero.

wfcommon.run_summary's declared contract distinguishes a SUPPLIED count
(runs inside `counts`, even 0) from an omitted argument (key absent). The
dashboard's census always measures, so it always supplies (est-7ps8).

Cases (all through an isolated REAL _list_runs() invocation — fresh private
WF_RUNS_ROOT per process, no shared root):

  (A) ZERO valid never-executed runs: the all-zero census keeps its measured
      zero — counts["executed"] == 0 (key PRESENT). Base answer: absent.
  (B) ONE valid never-executed run: counts == {"running":0,"pending":1,
      "executed":0}. Base answer: no executed key.
  (C) Helper controls on the same row shape, pinning the declared
      supplied-versus-unmeasured distinction itself:
        run_summary(rows, executed=0)  -> counts["executed"] == 0 (present)
        run_summary(rows)              -> "executed" NOT in counts

Red discipline: (A) and (B) are rc=1 at base b413983 (the `or None` dropped
the key) and rc=0 at the repair head. (C) is the contract control — green at
both, and the reason (A)/(B) are meaningful.

Run: PYTHONPATH=/opt/duckwork:.. python3 tests/test_measured_zero_7ps8.py
(from the tests/ cwd; a fresh private WF_RUNS_ROOT is created per invocation
and any inherited WF_RUNS_ROOT is scrubbed, so a hostile lane env cannot steer
the census nor be written by it — the probe is read-only.)
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# --- hermetic env: fresh private runs root, inherited lane roots scrubbed --
BASE = Path(tempfile.mkdtemp(prefix="wf7ps8-mz-"))
RESOLVED = BASE / "resolved"   # settings-resolved root (scanned first)
LEGACY = BASE / "legacy"       # legacy launch root (scanned second)
RESOLVED.mkdir()
LEGACY.mkdir()
for k in [k for k in os.environ if k.startswith(("WF_", "DUCKWORK_WF_"))]:
    os.environ.pop(k)  # scrub lane-exported roots; a hostile env must not steer us
os.environ["DUCKWORK_HOME"] = str(BASE / "home")
os.environ["WF_RUNS_ROOT"] = str(LEGACY)   # launch_runs_root() answer
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else "  ::  " + str(detail)[:300]))
    if not cond:
        ok = False


def seed_run(root, name, *, logs=False):
    """A VALID never-executed run: the graph+run+node trio run_state accepts,
    no logs/ dir (run_executed False), no events/pid (status: pending)."""
    r = root / name
    (r / "nodes").mkdir(parents=True)
    if logs:
        (r / "logs").mkdir()
        (r / "logs" / "a.log").write_text("line\n")
    (r / "graph.json").write_text(json.dumps({"name": name[-4:], "nodes": [
        {"id": "a", "type": "agent", "goal": "x"}]}))
    (r / "run.json").write_text(json.dumps({"run_id": name, "name": name[-4:],
                                            "started": "2099-01-01T00:00:00+00:00"}))
    # NO node record: the node stays pending and, with no events.jsonl/wf.pid,
    # run_state answers 'pending' — the never-executed row shape.
    return r


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fresh_dashboard():
    d = load("dash_mz", ROOT / "dashboard" / "plugin_api.py")
    # resolved root = RESOLVED via the owner-settings reader (#42 precedence,
    # beats WF_RUNS_ROOT); launch root = LEGACY via WF_RUNS_ROOT — two-root shape.
    d._workflow_common().set_owner_setting_reader(
        lambda key: (str(RESOLVED) if key == "runs_root" else None))
    return d


# ---------------------------------------------------------------- (A) all-zero
lst = fresh_dashboard()._list_runs()
counts = lst.get("counts", {})
check("(A) zero valid runs: the all-zero census keeps its measured zero (executed key present, 0)",
      "executed" in counts and counts["executed"] == 0,
      json.dumps({**counts, "total": lst.get("total")}))

# ---------------------------------------------------------------- (B) one row
seed_run(RESOLVED, "20990101-000000-unexec")   # valid, never executed
lst = fresh_dashboard()._list_runs()
counts = lst.get("counts", {})
check("(B) one valid never-executed run: counts == {running:0, pending:1, executed:0}",
      counts == {"running": 0, "pending": 1, "executed": 0},
      json.dumps({**counts, "total": lst.get("total")}))

# ------------------------------------------------- (C) helper contract controls
# Same row shape passed straight to the shared census helper: the declared
# supplied-count-versus-unmeasured distinction (wfcommon.py:3507-3518).
rows = [{"status": "pending"}]
supplied = wfcommon.run_summary(rows, executed=0)["counts"]
check("(C1) run_summary(executed=0): supplied zero rides as key-present 0",
      "executed" in supplied and supplied["executed"] == 0, json.dumps(supplied))
omitted = wfcommon.run_summary(rows)["counts"]
check("(C2) run_summary() arg omitted: unmeasured stays key-absent (v1.0.15 key set)",
      "executed" not in omitted, json.dumps(omitted))

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
