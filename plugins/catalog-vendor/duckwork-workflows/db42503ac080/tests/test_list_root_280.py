#!/usr/bin/env python3
"""est-2ek.1.280 (wave-2 intake, docs-ux-misc): the list surfaces must name the
root they actually scanned.

Papercut: run root is <duckwork_home>/workflows as seen by the DASHBOARD process;
in multi-profile setups a tool launched from a profile writes profiles/<p>/
workflows/ while the API globs the canonical dir — BOTH answer an empty list
that says nothing about WHERE it looked, and ~10h was burned chasing auth
instead of the stale root. The F1 identity law keeps the non-empty payload
byte-identical (golden-solo v1.0.15): `roots` is emitted ONLY when the scan
found zero runs — the exact silent-empty-state case the papercut is about.

Contracts:
  C1 door act_list, empty root  -> keys {runs,total,counts,roots}; roots lists
     the resolved runs_root first, plus the legacy launch root when different.
  C2 door act_list, one run     -> key set EXACTLY {runs,total,counts(,provenance)}
     — no roots key (golden-solo byte law).
  C3 dashboard _list_runs, empty -> same roots field alongside run_summary.
  C4 roots values are the strings runs_root()/launch_runs_root() resolve to,
     so one look catches empty-root AND stale-root.
"""
import importlib.util, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and cond

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

empty = Path(tempfile.mkdtemp(prefix="wf280-empty-"))
os.environ["WF_RUNS_ROOT"] = str(empty)

door = load("door280", ROOT / "__init__.py")
# est-2ek.1.762: on a host whose config carries the owner settings.runs_root,
# that value OUTRANKS WF_RUNS_ROOT (#42 precedence) and this scan would read
# the production library — the same non-hermetic class #71 pins at the
# resolver. Neutralise it so both pins answer the scratch root (C4 still
# checks the resolved root is first; with the pin both resolvers agree).
import wf_test_isolation as _iso71; _iso71.install(door)
out = door.act_list({})
check("C1 empty scan names its roots", out.get("runs") == [] and out.get("roots"),
      json.dumps({k: out.get(k) for k in ("runs", "roots")}))
check("C4 resolved root is first", isinstance(out.get("roots"), list)
      and out["roots"] and Path(out["roots"][0]) == empty, out.get("roots"))
import wfcommon
legacy = str(wfcommon.launch_runs_root())
check("C4 legacy launch root included when it differs from the resolved root",
      legacy == str(empty) or (legacy in out.get("roots", [])), out.get("roots"))

# C3 on the SAME empty scan: the dashboard API answers with the same roots.
dash = load("dash280", ROOT / "dashboard" / "plugin_api.py")
# The dashboard loads its OWN private wfcommon copy (per-plugin-root module key),
# so the door's #71 pin above does not reach it: pin its owner-settings reader
# at the same law — the env pin answers runs_root, everything else unset.
dash._workflow_common().set_owner_setting_reader(
    lambda key: (os.environ.get("WF_RUNS_ROOT") or None) if key == "runs_root" else None)
lst = dash._list_runs()
check("C3 dashboard empty scan names its roots",
      lst.get("runs") == [] and lst.get("roots") == out.get("roots") and lst.get("roots"),
      json.dumps({k: lst.get(k) for k in ("runs", "roots", "total", "counts")}))

# C2: a non-empty scan keeps the golden-solo key set exactly (no roots key).
run = empty / "20990101-000000-nonempty"
(run / "nodes").mkdir(parents=True)
(run / "graph.json").write_text(json.dumps({"name": "n280", "nodes": [
    {"id": "a", "type": "agent", "goal": "x"}]}))
(run / "run.json").write_text(json.dumps({"run_id": run.name, "name": "n280",
                                           "started": "2099-01-01T00:00:00+00:00"}))
(run / "nodes" / "a.json").write_text(json.dumps(
    {"status": "done", "output": {"answer": "ok"}, "efp": "",
     "fp_rule_version": wfcommon.FP_RULE_VERSION}))
out2 = door.act_list({})
keys2 = set(out2) - {"provenance"}
check("C2 non-empty scan keeps golden-solo keys (no roots)",
      out2["runs"] and keys2 == {"runs", "total", "counts"}, json.dumps(sorted(out2)))
lst2 = dash._list_runs()
check("C2-dash non-empty scan keeps its key set (no roots)",
      lst2["runs"] and set(lst2) == {"runs", "total", "counts"}, json.dumps(sorted(lst2)))

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
