#!/usr/bin/env python3
"""Import-purity contract (outbound review Fordex/duckwork-agent#133387).

Three code asks from the upstream maintainer, pinned as executable law:
1. Spec-loading wf.py (or importing it) must never mutate the host sys.path and
   must never leave a generic 'wf'/'wfcommon' entry in sys.modules. The door
   must not spec-load wf.py at all on run/amend — bake_route_receipts lives in
   wfcommon, which the door already spec-loads privately.
2. wfcommon's harvest validator must be privately bound — no generic
   `from wf import validate` that could import a foreign top-level 'wf'.
3. Shipped example probes must not write handoff state to a fixed shared /tmp
   path; it lives under the run dir (release-lifecycle) or $DUCKWORK_HOME
   (machine-watch, incident-response — cross-run state that the run dir dies
   with on a fresh dispatch).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ok = True


def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        ok = False


PROBE = r'''
import importlib.util, json, sys
root = sys.argv[1]
before_path = list(sys.path)
before_mods = set(sys.modules)
spec = importlib.util.spec_from_file_location("_probe_wf", root + "/wf.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps({
    "path_delta": [p for p in sys.path if p not in before_path],
    "mod_delta": sorted(set(sys.modules) - before_mods),
    "has_bake": hasattr(mod, "bake_route_receipts"),
    "has_validate": callable(getattr(mod, "validate", None)),
}))
'''

with tempfile.TemporaryDirectory(prefix="purity-133387-") as td:
    # --- 1a: spec-loading wf.py is import-pure for the host ---
    out = subprocess.run([sys.executable, "-c", PROBE, str(ROOT)],
                         capture_output=True, text=True, timeout=60)
    check(out.returncode == 0, f"wf.py spec-loads cleanly ({out.stderr[-200:]})")
    res = json.loads(out.stdout) if out.returncode == 0 else {}
    check(res.get("path_delta") == [],
          f"spec-load of wf.py adds NOTHING to host sys.path (delta: {res.get('path_delta')})")
    leaked = [m for m in res.get("mod_delta", []) if m in ("wf", "wfcommon")]
    check(not leaked,
          f"spec-load of wf.py leaves NO generic 'wf'/'wfcommon' in sys.modules (leaked: {leaked})")
    check(res.get("has_bake") is True, "wf.py still exposes bake_route_receipts (runner-side API)")
    check(res.get("has_validate") is True, "wf.py still exposes validate (runner-side API)")

    # --- 1b: importing the DOOR must not leave a generic 'wfcommon' either,
    #         and the door's bake path must not touch sys.path ---
    PROBE_DOOR = r'''
import importlib.util, json, os, sys
root = sys.argv[1]
os.environ["DUCKWORK_HOME"] = sys.argv[2]
before_path = list(sys.path)
before_mods = set(sys.modules)
spec = importlib.util.spec_from_file_location("_probe_door", root + "/__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
after_path = list(sys.path)
print(json.dumps({
    "path_delta": [p for p in after_path if p not in before_path],
    "mod_delta": sorted(set(sys.modules) - before_mods),
    "door_has_bake": hasattr(door, "_common") and hasattr(door._common, "bake_route_receipts"),
}))
'''
    out = subprocess.run([sys.executable, "-c", PROBE_DOOR, str(ROOT), td + "/home"],
                         capture_output=True, text=True, timeout=60)
    check(out.returncode == 0, f"door spec-loads cleanly ({out.stderr[-200:]})")
    res = json.loads(out.stdout) if out.returncode == 0 else {}
    check(res.get("path_delta") == [],
          f"spec-load of the door adds NOTHING to host sys.path (delta: {res.get('path_delta')})")
    leaked = [m for m in res.get("mod_delta", []) if m in ("wf", "wfcommon")]
    check(not leaked,
          f"door spec-load leaves NO generic 'wf'/'wfcommon' in sys.modules (leaked: {leaked})")
    check(res.get("door_has_bake") is True,
          "the door reaches bake_route_receipts through its privately-bound wfcommon")

    # --- 1c: no door-side spec-load of wf.py survives in run/amend ---
    door_src = (ROOT / "__init__.py").read_text()
    check('"_duckwork_workflows_wf"' not in door_src,
          "the door never spec-loads wf.py by name (bake moved to wfcommon)")

    # --- 2: the harvest validator is privately bound ---
    src = (ROOT / "wfcommon.py").read_text()
    check("from wf import" not in src and "import wf\b" not in src.replace("import wfcommon", ""),
          "wfcommon contains no generic 'from wf import' / 'import wf'")
    spec = importlib.util.spec_from_file_location("_purity_wfcommon", ROOT / "wfcommon.py")
    assert spec is not None and spec.loader is not None
    wc = importlib.util.module_from_spec(spec)
    _mp = dict(sys.modules)
    try:
        spec.loader.exec_module(wc)
        rec = {"harvest": {"declared_status": "done"}, "output": {"answer": "x"}}
        node = {"schema": {"type": "object", "required": ["answer"]}}
        check(wc._answer_harvest_valid(node, rec) is True,
              "_answer_harvest_valid validates WITHOUT importing any top-level 'wf'")
        check("wf" not in set(sys.modules) - set(_mp),
              "no top-level 'wf' entered sys.modules through the harvest read path")
    finally:
        sys.modules.clear(); sys.modules.update(_mp)

    # --- 3: shipped example probes carry no fixed shared-/tmp handoff paths ---
    for rel, marker in (("examples/release/release-lifecycle.workflow.json", "/tmp/"),
                        ("examples/release/machine-watch.workflow.json", "/tmp/"),
                        ("examples/ops/incident-response.json", "/tmp/")):
        blob = (ROOT / rel).read_text()
        check(marker not in blob, f"{rel}: no fixed shared-{marker[:-1]} handoff path")
    rl = json.loads((ROOT / "examples/release/release-lifecycle.workflow.json").read_text())
    aw = next(n for n in rl["nodes"] if n["id"] == "await-ci")
    check("DUCKWORK_WF_RUN_DIR" in aw["wait"]["until_argv"][2],
          "the await-ci probe reads its pointer under the run dir")
    mw = json.loads((ROOT / "examples/release/machine-watch.workflow.json").read_text())
    mwp = next(n for n in mw["nodes"] if n.get("wait", {}).get("until_argv"))["wait"]["until_argv"][2]
    check("DUCKWORK_HOME" in mwp, "the machine-watch probe roots under $DUCKWORK_HOME")
    ir = json.loads((ROOT / "examples/ops/incident-response.json").read_text())
    irp = next(n for n in ir["nodes"] if n["id"] == "recovery-probe")["wait"]["until_argv"][2]
    check("DUCKWORK_HOME" in irp, "the incident recovery probe roots under $DUCKWORK_HOME")

    # --- behavior preserved: bake + route refusal still work through wf.py ---
    sys.path.insert(0, str(ROOT))
    try:
        spec = importlib.util.spec_from_file_location("_purity_wf", ROOT / "wf.py")
        assert spec is not None and spec.loader is not None
        wf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wf)
        run = Path(td) / "run"
        graph = {"nodes": [{"id": "a", "type": "agent", "provider": "p",
                           "model": "m", "route_verified": "p/m"}]}
        check(wf.bake_route_receipts(run, graph) is True, "bake_route_receipts still writes receipts")
        check(json.loads((run / "route_receipts.json").read_text()) == {"a": "p/m"},
              "the baked receipt carries the door's proved-alive route")
        rec = wf._route_substitution_refusal({"_run": run}, {"id": "a", "provider": "p",
                                                             "model": "other"}, 1)
        check(rec and rec.get("error_class") == "route_substitution_denied",
              "the substitution refusal still fires against the baked receipt")
        check(wf.validate({"answer": 5}, {"type": "object", "required": ["answer"],
                                          "properties": {"answer": {"type": "string"}}}),
              "wf.validate still reports schema errors")
    finally:
        del sys.path[0]

print("IMPORT-PURITY CONTRACT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
