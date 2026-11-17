#!/usr/bin/env python3
"""est-7ps8 — runs-root census fixes from the PR#259 non-blocking notes.

Three probes, all behaviour-driven (no source-text pins, R6):

  (U) iter_run_dirs dedupes by REALPATH, not run-dir NAME. A torn dir with
      the same NAME in the first (resolved) root currently HIDES a valid
      same-named dir in the legacy root — the valid run vanishes from every
      read model. Realpath dedupe still collapses symlinked mirror roots
      (the original est-2ek.1.762 multiply-hit case): the same physical dir
      seen through two roots is ONE row.

  (D) dashboard executed-accounting: `executed` counts ONLY rows that land
      in `runs` (a torn dir with a stray logs/ dir is not an executed run —
      it never appears in the list, so counting it makes executed > total).

  (S) scripts/suite.py removes the temporary WF_RUNS_ROOT it exports when
      the run ends (no wf-suite-runs-* dir left under the system temp dir).
      Leg (S) lives in tests/test_suite_tempdir_cleanup_7ps8.py.

Red discipline: RED at base (name-dedupe hides the valid dir; executed
counts non-landing rows), GREEN after the fix.

Run: PYTHONPATH=/opt/duckwork python3 tests/test_runs_root_realpath_7ps8.py
"""
import importlib.util, json, os, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = Path(os.environ.get("TMPDIR", "/tmp")) / "wf7ps8-realpath"
shutil.rmtree(BASE, ignore_errors=True)
BASE.mkdir(parents=True)

RESOLVED = BASE / "resolved"     # the settings/root-pinned runs root (scanned FIRST)
LEGACY = BASE / "legacy"         # the legacy launch root (scanned SECOND)
MIRROR = BASE / "mirror"         # a symlinked mirror of LEGACY (multiply-hit case)
for d in (RESOLVED, LEGACY, MIRROR):
    d.mkdir(parents=True)
os.symlink(str(LEGACY), str(MIRROR / "alias"))
MIRROR_ROOT = MIRROR / "alias"

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


def seed_run(root, name, *, valid=True, logs=False):
    """A run dir: valid = the graph+run+node trio run_state accepts; logs =
    a non-empty logs/ dir (what run_executed keys on)."""
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
        (r / "nodes" / "a.json").write_text(json.dumps(
            {"status": "done", "output": {"answer": "ok"}, "efp": "",
             "fp_rule_version": wfcommon.FP_RULE_VERSION}))
    else:
        # torn: the dir exists (a partial spawn) but has no graph — run_state
        # answers None. This is exactly the fixture shape the 762 census found.
        (r / "run.json").write_text("{not json")
    return r


HID = "20990101-000000-hidden"    # torn in RESOLVED (scanned first), VALID in LEGACY
NOLOGS = "20990101-000001-nologs" # valid in LEGACY, never executed
TORNLOGS = "20990101-000002-torn" # torn in RESOLVED but HAS a logs/ dir

seed_run(RESOLVED, HID, valid=False, logs=True)      # the hider
seed_run(LEGACY, HID, valid=True, logs=True)         # the hidden valid twin
seed_run(LEGACY, NOLOGS, valid=True, logs=False)     # a landed-but-unexecuted row
seed_run(RESOLVED, TORNLOGS, valid=False, logs=True) # never lands; must not count

# ---------------------------------------------------------------- (U) unit
got = wfcommon.iter_run_dirs([RESOLVED, LEGACY])
names = sorted(p.name for p in got)
check("(U1) a same-NAMED dir in two physically-distinct roots is not hidden",
      names == sorted([HID, HID, NOLOGS, TORNLOGS]), str(names))
same_named = [p for p in got if p.name == HID]
check("(U1b) both same-named paths are enumerated (realpath-distinct dirs)",
      len(same_named) == 2, str([str(p) for p in same_named]))

got2 = wfcommon.iter_run_dirs([RESOLVED, LEGACY, MIRROR_ROOT])
check("(U2) a symlinked mirror root still collapses to one row per physical dir",
      len(got2) == 4 and len(set(str(p.resolve()) for p in got2)) == 4,
      str([str(p) for p in got2]))

# ------------------------------------------------- behaviour: door + dash
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

door = load("door7ps8", ROOT / "__init__.py")
# resolved root = RESOLVED via the owner-settings reader (beats WF_RUNS_ROOT,
# #42 precedence); launch root = LEGACY via WF_RUNS_ROOT — the two-root shape.
door._common.set_owner_setting_reader(
    lambda key: (str(RESOLVED) if key == "runs_root" else None))
out = door.act_list({})
ids = sorted(r["run_id"] for r in out["runs"])
check("(B1) door act_list lists the valid twin hidden by the torn first-root dir",
      ids == sorted([HID, NOLOGS]), json.dumps(ids))

dash = load("dash7ps8", ROOT / "dashboard" / "plugin_api.py")
dash._workflow_common().set_owner_setting_reader(
    lambda key: (str(RESOLVED) if key == "runs_root" else None))
lst = dash._list_runs()
dids = sorted(r["id"] for r in lst["runs"])
check("(B2) dashboard _list_runs lists the valid twin too",
      dids == sorted([HID, NOLOGS]), json.dumps(dids))

# ---------------------------------------------------------------- (D) executed
# Post-fix the landed rows are HID (valid twin, logs -> executed) and NOLOGS
# (valid, no logs -> NOT executed). TORNLOGS never lands (run_state None) but
# HAS a logs/ dir: counting it is the probe's inflation bug — negative
# assertion executed <= total (and executed == the executed count AMONG rows).
counts = lst.get("counts", {})
check("(D) executed counts ONLY rows that land in runs (torn+logs dir excluded)",
      counts.get("executed") == 1 and lst.get("total") == 2,
      json.dumps({**counts, "total": lst.get("total")}))
check("(D-) executed never exceeds total (negative: the non-landing stray-logs dir must not inflate)",
      counts.get("executed", 0) <= lst.get("total", 0),
      json.dumps({**counts, "total": lst.get("total")}))

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
