#!/usr/bin/env python3
"""sys-5lnm17 (upstream of sys-ntdq1v): the read model must enumerate WHICH nodes
failed. Crash-reason synthesis (`crashed (no exit record)`) tells a lap consumer
that a run died; until now `failed_nodes[]` was never populated anywhere, so
localizing the death still required reading events.jsonl.

Fix law: run_state() derives failed_nodes (id, error, error_class) from the SAME
efp-valid states its status verdict used — derive-only (A3), never stored, never
re-derived from prose. act_status surfaces it on every status/wait output.

S1: an efp-valid failed node rides failed_nodes with its error bytes.
S2: a clean done run reports the honest-empty list (key present, []).
S3: a crash with NO failed node still lists nothing and keeps the synthesized
    runner_exit reason byte-identical (no-regression pin).
S4: honest-status law — a failed record whose harvest validates reads done and
    must NOT appear in failed_nodes.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

checks = 0
failures = 0


def check(label, cond, detail=""):
    global checks, failures
    checks += 1
    if cond:
        print(f"PASS {label}")
    else:
        failures += 1
        print(f"FAIL {label}: {detail}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory(prefix="failednodes5lnm-", dir=HERE,
                                 ignore_cleanup_errors=True) as td:
    home = Path(td) / "home"
    runs = home / "workflows"
    runs.mkdir(parents=True)
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["WF_RUNS_ROOT"] = str(runs)  # #71 env pin
    wfcommon = load("fn5_wfcommon", ROOT / "wfcommon.py")
    door = load("fn5_door", ROOT / "__init__.py")
    import wf_test_isolation as _iso71_fn5
    _iso71_fn5.install(door)  # #71: pin settings.runs_root too

    def scene(run_id, nodes, records, events=None):
        r = runs / run_id
        (r / "nodes").mkdir(parents=True)
        (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
        (r / "run.json").write_text("{}")
        byid = {n["id"]: n for n in nodes}
        for nid, rec in records.items():
            rec = dict(rec)
            rec.setdefault("efp", wfcommon.efp(byid, byid[nid]))
            (r / "nodes" / f"{nid}.json").write_text(json.dumps(rec))
        if events:
            (r / "events.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in events))
        return r

    NODES = [{"id": "a", "type": "agent", "goal": "x"},
             {"id": "b", "type": "agent", "goal": "y", "after": ["a"]}]

    # ---- S1: failed node enumerated with its error bytes ----
    r1 = scene("fn5-fail", NODES,
               {"a": {"status": "done", "output": {"result": "ok"}},
                "b": {"status": "failed", "error": "child died rc=1",
                      "error_class": "child_exit"}})
    st1 = wfcommon.run_state(r1)
    check("S1: run reports failed status", st1["status"] == "failed", st1["status"])
    check("S1: failed_nodes names the dead node with error bytes",
          st1["failed_nodes"] == [{"id": "b", "error": "child died rc=1",
                                   "error_class": "child_exit"}],
          json.dumps(st1["failed_nodes"]))
    out1 = door.act_status({"run_id": "fn5-fail"})
    check("S1: status output surfaces failed_nodes",
          out1.get("failed_nodes") == [{"id": "b", "error": "child died rc=1",
                                        "error_class": "child_exit"}],
          json.dumps(out1.get("failed_nodes")))

    # ---- S2: clean done run -> honest-empty list ----
    r2 = scene("fn5-done", NODES,
               {"a": {"status": "done", "output": {"result": "ok"}},
                "b": {"status": "done", "output": {"result": "ok"}}},
               events=[{"event": "run.done"}])
    st2 = wfcommon.run_state(r2)
    check("S2: clean run keeps done status", st2["status"] == "done", st2["status"])
    check("S2: failed_nodes is present and empty", st2["failed_nodes"] == [],
          json.dumps(st2["failed_nodes"]))

    # ---- S3: crash with no failed node -> empty list, bare reason intact ----
    r3 = scene("fn5-crash", NODES, {"a": {"status": "done", "output": {"result": "ok"}}})
    (r3 / "wf.pid").write_text("999998")  # never exists -> dead pid, no exit record
    st3 = wfcommon.run_state(r3)
    check("S3: synthesized crash reason is unchanged",
          (st3["runner_exit"] or {}).get("reason") == "crashed (no exit record)",
          json.dumps(st3["runner_exit"]))
    check("S3: a runner-crash lists NO failed nodes", st3["failed_nodes"] == [],
          json.dumps(st3["failed_nodes"]))

    # ---- S4: harvest-on-death reads done, never lists ----
    n_b = NODES[1]
    answer = {"verdict": "built", "notes": "done"}
    harvest = {"declared_status": "done"}
    r4 = scene("fn5-harvest", NODES,
               {"a": {"status": "done", "output": {"result": "ok"}}},
               )
    # stamp b by hand so the harvest shape matches _answer_harvest_valid's law
    schema = n_b.get("output_schema")
    rec_b = {"status": "failed", "error": "rc=1 after harvest",
             "error_class": "child_exit", "harvest": harvest, "output": answer,
             "efp": wfcommon.efp({n["id"]: n for n in NODES}, n_b)}
    (r4 / "nodes" / "b.json").write_text(json.dumps(rec_b))
    st4 = wfcommon.run_state(r4)
    check("S4: a dead-but-harvested node is not in failed_nodes",
          all(f["id"] != "b" for f in st4["failed_nodes"]),
          json.dumps(st4["failed_nodes"]))

    print(f"\n{checks - failures}/{checks} checks passed")
    sys.exit(1 if failures else 0)
