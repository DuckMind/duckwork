#!/usr/bin/env python3
"""ra-plan#125-1 (est-0sj4, issue #125 slice 1): the plugin_version stamp is
UNCONDITIONAL — every new run.json reports the arming door's own truth
(plugin.yaml via wfcommon.plugin_version()), not only runs that declared
requires_plugin (the est-2ek.1.166 carve-out removed; plan comment 6048098690).

Surfaces (R6 — every behaviour change ships its check):
  (1) plain run.json (NO requires_plugin) carries plugin_version == plugin.yaml;
  (2) act_status returns it for a plain run (the existing derive-only echo,
      unchanged code path at the est-2ek.1.166 status block);
  (3) R10 migration: an OLD run dir whose run.json has no plugin_version still
      loads and status OMITS the key (derive-only — bytes only, never invented);
  (4) an applied amend preserves the stamp (amend reads-merges-writes run.json;
      the no-op law holds — the key is neither rewritten nor dropped);
  (5) an unreadable plugin.yaml ('' from wfcommon.plugin_version) keeps the key
      ABSENT on a plain run (honest absence, R2: an unknown runner version is
      never invented into the stamp).
Coarse-shape mirrors tests/test_plugin_asks_166_version_handshake.py.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home_uvs"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake_uvs.log"))
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE

spec = importlib.util.spec_from_file_location("uvs_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)

import re
m = re.search(r"(?m)^version:\s*(\S+)\s*$", (ROOT / "plugin.yaml").read_text())
RUNNER_V = m.group(1)
check("(0) plugin.yaml carries the runner version", bool(RUNNER_V), RUNNER_V)

G = {"name": "uvs", "nodes": [{"id": "a", "type": "agent", "goal": "GO uvs"}]}

# ---- (1)+(2) plain run: NO requires_plugin anywhere, stamp still lands ----
plain = door.act_run({"graph": dict(G, name="uvs-plain")})
rid = plain.get("run_id")
check("(1) plain run launched", bool(rid), json.dumps(plain)[:200])
if rid:
    meta = json.loads((HOME / "workflows" / rid / "run.json").read_text())
    check("(1) plain run.json carries plugin_version == plugin.yaml version",
          meta.get("plugin_version") == RUNNER_V, json.dumps(meta)[:250])
    check("(1) the stamp did NOT drag requires_plugin into graph.json",
          "requires_plugin" not in (json.loads(
              (HOME / "workflows" / rid / "graph.json").read_text()) or {}))
    # let the runner finish so status is terminal (same seam as the 166 test)
    subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", rid],
                   env={**env, "WF_RUNS_ROOT": str(HOME / "workflows")},
                   capture_output=True, text=True, timeout=120)
    st = door.act_status({"run_id": rid})
    check("(2) status echoes plugin_version for a PLAIN run",
          st.get("plugin_version") == RUNNER_V, json.dumps(st)[:250])

    # ---- (4) an applied amend preserves the stamp (read-merge-write) ----
    am = door.act_amend({"run_id": rid, "graph": dict(G, name="uvs-plain-renamed")})
    check("(4) amend applied", am.get("ok") is True, json.dumps(am)[:200])
    meta2 = json.loads((HOME / "workflows" / rid / "run.json").read_text())
    check("(4) amend restamp preserves plugin_version (no-op law)",
          meta2.get("plugin_version") == RUNNER_V and meta2.get("name") == "uvs-plain-renamed",
          json.dumps(meta2)[:250])
    st2 = door.act_status({"run_id": rid})
    check("(4) status still echoes the preserved stamp after the amend",
          st2.get("plugin_version") == RUNNER_V, json.dumps(st2)[:250])

# ---- (3) R10: old run dir WITHOUT the key still loads; status omits it ----
r3 = HOME / "workflows" / "uvs-old"
if r3.exists():
    shutil.rmtree(r3)
(r3 / "nodes").mkdir(parents=True)
(r3 / "gates").mkdir()
(r3 / "logs").mkdir()
(r3 / "graph.json").write_text(json.dumps(
    {"name": "uvs-old", "nodes": [{"id": "a", "type": "agent", "goal": "GO uvs-old"}]}))
(r3 / "run.json").write_text(json.dumps(
    {"name": "uvs-old", "duckwork_bin": FAKE, "node_timeout": 30,
     "started": "2026-10-01T00:00:00+00:00"}))   # pre-stamp shape: no plugin_version
st3 = door.act_status({"run_id": "uvs-old"})
check("(3) old run dir without the key still loads", "error" not in st3, json.dumps(st3)[:250])
check("(3) status OMITS plugin_version for the old dir (derive-only, never invented)",
      "plugin_version" not in st3, json.dumps(st3)[:250])
check("(3) run.json was not back-filled by the read",
      "plugin_version" not in json.loads((r3 / "run.json").read_text()))

# ---- (5) unreadable plugin.yaml (''): honest absence, key never invented ----
_real_pv = door._common.plugin_version
door._common.plugin_version = lambda: ""
try:
    nopv = door.act_run({"graph": dict(G, name="uvs-nopv")})
    rid5 = nopv.get("run_id")
    check("(5) run launched with an unreadable plugin.yaml", bool(rid5), json.dumps(nopv)[:200])
    if rid5:
        meta5 = json.loads((HOME / "workflows" / rid5 / "run.json").read_text())
        check("(5) empty plugin_version keeps the key ABSENT (never '')",
              "plugin_version" not in meta5, json.dumps(meta5)[:250])
        door.act_stop({"run_id": rid5})
finally:
    door._common.plugin_version = _real_pv

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
