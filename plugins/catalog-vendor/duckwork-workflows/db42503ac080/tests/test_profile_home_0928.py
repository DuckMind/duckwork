#!/usr/bin/env python3
"""Runner + children must inherit the OWNER's resolved profile home.

Host fact (measured live, 2026-09-28): `duckwork -p X gateway run` under a supervisor
and `duckwork -p default dashboard --open-profile Y` both keep
os.environ["DUCKWORK_HOME"] at the LAUNCH root and serve the profile through core's
context-local override (duckwork_constants.set_duckwork_home_override, installed per
turn by gateway._profile_runtime_scope). Resolution that reads the raw env hands
the door, the runner, and every child the BASE profile: seat config invisible,
profile-defined providers die 'Unknown provider' (transport_exhausted on all
nodes), run dirs land under the wrong home. Core's own contract
(duckwork_constants.get_duckwork_home: override -> DUCKWORK_HOME -> default; its #18594
warning instructs subprocess spawners to pass DUCKWORK_HOME explicitly) is what the
plugin now uses; the env fallback keeps bare-CLI/no-core hosts byte-identical.

Mirrors the clean-room repro WITHOUT the real core: a stub duckwork_constants with
override semantics is injected in-process (door seam) and onto the runner's
PYTHONPATH (cross-process seam). Asserts:
  1. runs_root()/seat config/launcher identity follow the resolved home;
  2. the door stamps the runner env with the resolved home;
  3. end-to-end: a real runner + child inherit the OWNER's home;
  4. R10: a pre-fix run under the launch root is still found (find_run);
  5. no-core host: env-only resolution unchanged.
"""
import importlib.util, json, os, shutil, subprocess, sys, time, types
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
HOME = BUILD / "tests" / ".tmp-profile-home"
shutil.rmtree(HOME, ignore_errors=True)
BASE = HOME / "base"
PROF = BASE / "profiles" / "p1"
(PROF / "workflows").mkdir(parents=True)
(BASE / "config.yaml").write_text("model:\n  default: q\n")
(PROF / "config.yaml").write_text("model:\n  default: q\n  aliases:\n    seatonly: q\n")

os.environ["DUCKWORK_HOME"] = str(BASE)          # launch root stays base (measured host)
os.environ.pop("WF_RUNS_ROOT", None)

# ---- seam: a resolved profile home the env does NOT carry ----
stub_dir = HOME / "stub"; stub_dir.mkdir()
(stub_dir / "duckwork_constants.py").write_text(
    "import os\nfrom pathlib import Path\n"
    "_OVERRIDE = r'%s'\n"
    "def get_duckwork_home():\n"
    "    return Path(_OVERRIDE) if _OVERRIDE else "
    "Path(os.environ.get('DUCKWORK_HOME') or (Path.home() / '.duckwork'))\n" % PROF)
mod = types.ModuleType("duckwork_constants")
exec(compile((stub_dir / "duckwork_constants.py").read_text(), "stub", "exec"), mod.__dict__)
sys.modules["duckwork_constants"] = mod

sys.path.insert(0, str(BUILD))
spec = importlib.util.spec_from_file_location("hw_ph", str(BUILD / "__init__.py"))
assert spec is not None and spec.loader is not None
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
import wf_test_isolation as _iso71_hw56; _iso71_hw56.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

failures = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else " " + str(detail)))
    if not ok:
        failures.append(name)

check("runs_root follows resolved home, not env", hw.runs_root() == PROF / "workflows", hw.runs_root())
check("seat config sees the profile alias", "seatonly" in hw._seat_aliases(), hw._seat_aliases())
check("launcher identity resolves to the profile", hw._common.launcher_profile() == "p1",
      hw._common.launcher_profile())

# ---- R10 first (before any new run exists): pre-fix run under the launch root ----
legacy = BASE / "workflows" / "old-run"
(legacy / "nodes").mkdir(parents=True)
(legacy / "graph.json").write_text(json.dumps(
    {"name": "old", "nodes": [{"id": "a", "type": "agent", "goal": "x"}]}))
(legacy / "run.json").write_text(json.dumps({"name": "old"}))
check("pre-fix run stays findable from a profile-scoped door", hw.run_dir("old-run") == legacy,
      hw.run_dir("old-run"))

# ---- door spawn-env stamp ----
captured = {}
real_popen = hw.subprocess.Popen
def spy_popen(argv, **kw):
    captured["env"] = dict(kw.get("env") or os.environ)
    return real_popen(argv, **kw)
hw.subprocess.Popen = spy_popen

fake_dir = HOME / "fake"; fake_dir.mkdir()
fake_py = fake_dir / "fake_ph.py"
fake_py.write_text(
    "import os, json\n"
    "p = os.environ.get('PH_OUT')\n"
    "open(p, 'a').write(os.environ.get('DUCKWORK_HOME', '') + '\\n')\n"
    "print('```json\\n' + json.dumps({'result':'ok'}) + '\\n```')\n")
fake = fake_dir / "fake"
fake.write_text("#!/bin/sh\nexec \"%s\" \"%s\" \"$@\"\n" % (sys.executable, fake_py))
os.chmod(fake, 0o755)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(fake)
OUT = HOME / "child_home.txt"
os.environ["PH_OUT"] = str(OUT)
# the runner resolves the profile through core's override exactly like the host:
# same stub, via PYTHONPATH.
os.environ["PYTHONPATH"] = str(stub_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

r = hw.handle({"action": "run", "graph": {"name": "ph", "nodes": [
    {"id": "n1", "type": "agent", "goal": "LIST: go"}]}})
r = json.loads(r) if isinstance(r, str) else r
rid = r.get("run_id")
check("run launches", bool(rid), r)
check("runner env carries resolved DUCKWORK_HOME",
      captured.get("env", {}).get("DUCKWORK_HOME") == str(PROF), captured.get("env", {}).get("DUCKWORK_HOME"))
check("new run dir under the OWNER's home, not the launch root",
      rid and (PROF / "workflows" / rid).is_dir() and not (BASE / "workflows" / rid).exists(), rid)

deadline = time.time() + 30
lines: list[str] = []
while time.time() < deadline:
    try:
        lines = [l for l in OUT.read_text().splitlines() if l.strip()]
    except OSError:
        lines = []
    if lines:
        break
    time.sleep(0.2)
child_home = lines[0] if lines else "<no child spawn observed>"
check("child inherits the OWNER's home (profile provider config visible to it)",
      child_home == str(PROF), child_home)

st = hw.handle({"action": "wait", "run_id": rid, "timeout": 30})
st = json.loads(st) if isinstance(st, str) else st
check("run reaches done through the profile-scoped door/runner/child chain",
      st.get("status") == "done", json.dumps({k: st.get(k) for k in ("status", "note")}))

lst = hw.handle({"action": "list"})
lst = json.loads(lst) if isinstance(lst, str) else lst
check("act_list shows both the new (profile) and legacy (launch-root) runs",
      rid in {x["run_id"] for x in lst.get("runs", [])} and "old-run" in {x["run_id"] for x in lst.get("runs", [])},
      str([x["run_id"] for x in lst.get("runs", [])][:6]))

# ---- F1 (#14 review): library, dashboard list, and lane registry relocated with
# runs_root() must keep the same legacy fallback find_run/act_list got ----
# 1. a graph saved under the LAUNCH root pre-fix is listed and replays from the scoped door
legacy_graph = {"name": "old-graph", "nodes": [{"id": "a", "type": "agent", "goal": "x"}]}
(BASE / "workflows" / "library").mkdir(parents=True, exist_ok=True)
(BASE / "workflows" / "library" / "old-graph.json").write_text(json.dumps(legacy_graph))
lib = json.loads(hw.handle({"action": "library"}))
check("act_library includes a pre-fix launch-root graph",
      "old-graph" in {x["name"] for x in lib.get("library", [])},
      str([x["name"] for x in lib.get("library", [])]))
# replay must bind the legacy graph (it fails later on the fake child at worst, but
# must NOT answer 'no library graph named')
rep = json.loads(hw.handle({"action": "run", "from": "old-graph",
                            "name": "legacy-replay"}))
check("run from=<legacy graph> resolves it, not 'no library graph'",
      bool(rep.get("run_id")) and rep.get("error") is None, rep)
if rep.get("run_id"):
    hw.handle({"action": "stop", "run_id": rep["run_id"]})

# 2. dashboard _list_runs sees the legacy run too (same merge as act_list)
_api_spec = importlib.util.spec_from_file_location("hw_dash_api", str(BUILD / "dashboard" / "plugin_api.py"))
assert _api_spec and _api_spec.loader
dash = importlib.util.module_from_spec(_api_spec)
_api_spec.loader.exec_module(dash)
dl = dash._list_runs()
dids = {x["id"] for x in dl.get("runs", [])}
check("dashboard _list_runs merges the legacy launch root",
      "old-run" in dids and rid in dids, str(sorted(dids)[:6]))

# 3. a lane entry written under the LAUNCH root dedupes a relaunch from the scoped door
(BASE / "workflows" / "lanes").mkdir(parents=True, exist_ok=True)
lane_key = "team/x"
stem = __import__("hashlib").sha256(lane_key.encode("utf-8")).hexdigest()[:16]
(BASE / "workflows" / "lanes" / f"{stem}.json").write_text(
    json.dumps({"lane_key": lane_key, "run_id": "old-run", "graph_name": "old"}))
entry, coll = hw._lane_entry(lane_key)
check("legacy launch-root lane entry is visible to the scoped door",
      entry is not None and entry.get("run_id") == "old-run" and coll is None,
      str((entry, coll)))
# writes still land in the RESOLVED root
check("lane write path stays resolved (not legacy)",
      str(hw._lane_paths(lane_key)[0]).startswith(str(PROF)), hw._lane_paths(lane_key)[0])

hw.subprocess.Popen = real_popen
sys.modules.pop("duckwork_constants", None)

# ---- no-core host: env-only resolution stays byte-identical to 1.0.15 ----
spec2 = importlib.util.spec_from_file_location("hw_ph_nc", str(BUILD / "wfcommon.py"))
assert spec2 and spec2.loader
wc_nc = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(wc_nc)
check("no-core import: duckwork_home == the raw env value", wc_nc.duckwork_home() == BASE, wc_nc.duckwork_home())
check("no-core import: runs_root == env/workflows", wc_nc.runs_root() == BASE / "workflows", wc_nc.runs_root())

shutil.rmtree(HOME, ignore_errors=True)
print("TOTAL FAIL", len(failures))
sys.exit(1 if failures else 0)
