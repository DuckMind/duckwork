#!/usr/bin/env python3
"""est-2ek.1.599 regression pin: lanes must not materialize run graphs onto the
SHARED shelf (waves 26/27/28/29/31 all re-published ra-pr-deep committee graphs
into <runs>/library — bare form, empty description, hardcoded PR#/scratch paths).

Machine law: a process that CARRIES its lane identity (DUCKWORK_WF_RUN_DIR, baked by
the runner at every agent spawn, wf.py) is a spawned child — its `save` may only
land RUN-LOCAL (under its own run dir). A save that would publish to the shared
shelf from such a process is refused with typed error_class lane_shelf_write and
writes NOTHING. A parent/owner process (no lane identity) saves as before.

Three parts, standalone (no pytest), house style. Pinned per #71 law:
WF_RUNS_ROOT + wf_test_isolation so nothing here can touch the real estate shelf.
"""
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
ok = True


def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " if cond is False else "SKIP ") + label
          + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)


sys.path.insert(0, "/opt/duckwork")

spec = importlib.util.spec_from_file_location("hw1599", str(BUILD / "__init__.py"))
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso  # noqa: E402
_iso.install(door)

G = {"name": "ra-pr-deep-committee-probe", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
LANE_ENV_KEYS = ("WF_RUNS_ROOT", "DUCKWORK_WF_RUN_ID", "DUCKWORK_WF_RUN_DIR")

with tempfile.TemporaryDirectory(prefix="shelf1599-") as td:
    sandbox = Path(td)
    saved = {k: os.environ.get(k) for k in LANE_ENV_KEYS}
    try:
        # ---- T1: a lane child CANNOT publish to the shared shelf ----
        os.environ["WF_RUNS_ROOT"] = str(sandbox / "runs")
        runs = sandbox / "runs"
        (runs / "library").mkdir(parents=True)
        lane_run = runs / "20261003-131900-ra-pr-deep-wf156c"   # the wave-26 shape
        lane_run.mkdir()
        os.environ["DUCKWORK_WF_RUN_ID"] = lane_run.name
        os.environ["DUCKWORK_WF_RUN_DIR"] = str(lane_run)
        r = json.loads(door.handle({"action": "save", "graph": G, "name": "ra-pr-deep-wf156c"}))
        landed = (runs / "library" / "ra-pr-deep-wf156c.json")
        check("T1a lane-child save is refused", "error" in r and "saved" not in r, json.dumps(r)[:300])
        check("T1b refusal is typed lane_shelf_write",
              r.get("error_class") == "lane_shelf_write", json.dumps(r)[:300])
        check("T1c shared shelf gained NOTHING", not landed.exists(),
              f"{landed} exists — the wave-26 shape again")

        # ---- T2: run-local graph copies stay allowed (pin resolves shelf under own run dir) ----
        os.environ["WF_RUNS_ROOT"] = str(lane_run)
        r = json.loads(door.handle({"action": "save", "graph": G, "name": "ra-pr-deep-wf156c"}))
        local = lane_run / "library" / "ra-pr-deep-wf156c.json"
        check("T2 run-local save (child) still succeeds",
              r.get("saved") == "ra-pr-deep-wf156c" and local.exists(), json.dumps(r)[:300])

        # ---- T4: symlink run-dir evasion is refused (recon ask 1, marker 5980069065) ----
        # The legit T2 shape (WF_RUNS_ROOT pinned AT the run dir) with <run>/library
        # PRE-SWAPPED for a symlink to the SHARED library: containment must be judged
        # on tgt_r (realpath) only, and tgt_r compared against library_root() — a
        # raw-string containment pass must not let the graph land on the shared shelf.
        shutil.rmtree(lane_run / "library")
        os.symlink(str(runs / "library"), str(lane_run / "library"))
        r = json.loads(door.handle({"action": "save", "graph": G, "name": "atk-sym-escape"}))
        esc = runs / "library" / "atk-sym-escape.json"
        check("T4a symlinked-<run>/library save is refused",
              "error" in r and "saved" not in r, json.dumps(r)[:300])
        check("T4b refusal is typed lane_shelf_write",
              r.get("error_class") == "lane_shelf_write", json.dumps(r)[:300])
        check("T4c shared shelf gained NOTHING", not esc.exists(),
              f"{esc} exists — saved={r.get('saved')!r}: the symlink escape landed")

        # ---- T5: ancestor-swapped run dir (S3, deep lane 20261004-131221,
        # recon #179 marker 5980900759). <run> is REPLACED by a symlink to an
        # ANCESTOR (here: the runs root itself) with the runner-stamped env
        # UNTOUCHED (WF_RUNS_ROOT=runs, DUCKWORK_WF_RUN_DIR=runs/<lane>). At r4
        # base_r=resolve(DUCKWORK_WF_RUN_DIR) swallowed the whole root, cand_lib
        # resolved inside base_r so the shared-shelf veto self-skipped, and the
        # save to <runs>/library/atk-s3.json LANDED (saved=atk-s3). r5 clause A
        # (run-dir containment under the resolved runs root) + clause B (tgt_r
        # vs realpath(library_root()) judged regardless of base_r) must refuse.
        # Neuter-sensitive BOTH WAYS: deleting clause A turns this block RED
        # (the save lands); deleting clause B turns this block RED (the veto is
        # what judges the null-base_r case — see the r5 note on #179).
        os.unlink(str(lane_run / "library"))            # undo the T4 swap
        (runs / "library").mkdir(parents=True, exist_ok=True)
        os.rmdir(str(lane_run))                          # <run> itself...
        os.symlink(str(runs), str(lane_run))             # ...becomes a symlink to <runs>
        os.environ["WF_RUNS_ROOT"] = str(runs)           # runner stamp UNTOUCHED
        os.environ["DUCKWORK_WF_RUN_DIR"] = str(lane_run)  # raw shape still claims runs/<lane>
        r = json.loads(door.handle({"action": "save", "graph": G, "name": "atk-s3"}))
        s3 = runs / "library" / "atk-s3.json"
        check("T5a ancestor-swapped <run> save is refused",
              "error" in r and "saved" not in r, json.dumps(r)[:300])
        check("T5b refusal is typed lane_shelf_write",
              r.get("error_class") == "lane_shelf_write", json.dumps(r)[:300])
        check("T5c shared shelf gained NOTHING", not s3.exists(),
              f"{s3} exists — saved={r.get('saved')!r}: the S3 shape landed")

        # ---- T3: the owner/parent path is untouched (no lane identity) ----
        del os.environ["DUCKWORK_WF_RUN_ID"], os.environ["DUCKWORK_WF_RUN_DIR"]
        os.environ["WF_RUNS_ROOT"] = str(sandbox / "runs")
        r = json.loads(door.handle({"action": "save", "graph": G, "name": "owner-entry"}))
        check("T3 owner-process save still succeeds",
              r.get("saved") == "owner-entry"
              and (sandbox / "runs" / "library" / "owner-entry.json").exists(),
              json.dumps(r)[:300])
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
