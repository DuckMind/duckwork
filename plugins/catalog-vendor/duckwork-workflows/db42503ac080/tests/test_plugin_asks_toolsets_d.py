#!/usr/bin/env python3
"""spool key c258f0730346b426 (from est-2ek.1.142): the `toolsets` node field
passes the validator but a hostile shape crashes the runner at spawn with a
TypeError (the reported death: toolsets:["terminal"] -> PathLike TypeError).

Root cause (reproduced minimally, direct-call below): _filter_child_toolsets
calls .strip() on every element of whatever the author wrote. A dict element
dies AttributeError, an int element dies AttributeError, a BARE DICT or a bare
number reaches `"/".join` upstream paths as TypeError — the field is accepted by
the closed-set validator (toolsets in AGENT_KEYS) yet has no SHAPE check, so
anything non-List[str] survives validation and detonates at spawn.

Disposition: HONOR (trivially). The runner keeps honoring List[str] and
comma-strings exactly as before (est-flah clamp law intact); the door and the
runner's load-time net now reject a non-list-of-strings toolsets at VALIDATE
with a message naming the node, the key, and the offending value — never a
spawn-time TypeError, never a silent broadening.
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

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

# ---- (1) RED repro (direct call, exact reported shapes): hostile toolsets
# ---- values must NOT raise out of the runner's filter — they are rejected
# ---- upstream at validation, and the filter itself fails CLOSED to None. ----
spec = importlib.util.spec_from_file_location("asksD_wf", ROOT / "wf.py")
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

for shape in ([{"a": 1}], [123], {"web": "x"}, 5, [["terminal"]]):
    node = {"id": "a", "type": "agent", "goal": "g", "toolsets": shape}
    try:
        out = wf._filter_child_toolsets(None, {"_clamp_warned": set()}, node)
        crashed = None
    except Exception as e:
        out, crashed = None, e
    check(f"(1) filter survives hostile shape {shape!r} (no exception escapes to spawn)",
          crashed is None, f"raised {type(crashed).__name__}: {crashed}")

# ---- (2) GREEN: the door REFUSES those shapes at validation, naming the key ----
dhome = BUILD / "home_166d"
shutil.rmtree(dhome, ignore_errors=True)
dhome.mkdir(parents=True)
os.environ["DUCKWORK_HOME"] = str(dhome)
os.environ["WF_RUNS_ROOT"] = str(dhome / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
dspec = importlib.util.spec_from_file_location("asksD_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(dspec)
dspec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)

def run_err(graph):
    e = door._validation_error(dict(graph, name="asksD"))
    return (e or {}).get("error", ""), json.dumps(e or {})

for shape in ([{"a": 1}], [123], {"web": "x"}, 5, [["terminal"]]):
    err, blob = run_err({"nodes": [{"id": "a", "type": "agent", "goal": "g",
                                    "toolsets": shape}]})
    check(f"(2) door rejects toolsets={shape!r} naming node+key",
          "error" in blob and "toolsets" in blob and "a" in blob, err[:160])

for good in (["terminal"], "terminal", ["web", "files"], []):
    err, blob = run_err({"nodes": [{"id": "a", "type": "agent", "goal": "g",
                                    "toolsets": good}]})
    check(f"(2) door ACCEPTS toolsets={good!r} (shape honored)", "error" not in blob,
          err[:160])

# ---- (3) honored end-to-end: toolsets:["terminal"] spawns with -t terminal,
# ---- NOT a crash, exactly as an author expects (the est-flah law intact) ----
HOME = BUILD / "home_ts166"
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True)
RUNS = HOME / "workflows"
RUNS.mkdir()
env = dict(os.environ, DUCKWORK_HOME=str(HOME), FAKE_LOG=str(BUILD / "fake_ts166.log"),
           WF_RUNS_ROOT=str(RUNS))

r = RUNS / "asksD-honor"
if r.exists():
    shutil.rmtree(r)
(r / "nodes").mkdir(parents=True)
(r / "gates").mkdir()
(r / "graph.json").write_text(json.dumps(
    {"name": "asksD-honor", "nodes": [{"id": "a", "type": "agent",
                                       "goal": "GO asksD-honor",
                                       "toolsets": ["terminal"]}]}))
(r / "run.json").write_text(json.dumps({"duckwork_bin": str(BUILD / "fake"),
                                        "node_timeout": 60}))
argv_log = BUILD / "argv_ts166.log"
argv_log.unlink(missing_ok=True)
p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", "asksD-honor"],
                   env=dict(env, FAKE_ARGV_LOG=str(argv_log)),
                   capture_output=True, text=True, timeout=120)
rec = json.loads((r / "nodes" / "a.json").read_text())
line = argv_log.read_text().splitlines()[0] if argv_log.exists() else ""
check("(3) honored: child spawns with -t terminal", "-t terminal" in line, line[:200])
check("(3) node commits done (no PathLike/TypeError death)",
      rec.get("status") == "done",
      json.dumps({k: rec.get(k) for k in ("status", "error_class", "error")})[:300])

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
