#!/usr/bin/env python3
"""Tier self-report (2026-09-24): a FAILED child's core -Q turn report tier is
recorded once at <run>/turn_report.tier — typed when the report dict CONTAINS
the "turn_exit_reason" key (value may be empty), untyped otherwise — and the
door's act_status surfaces it as out["turn_report"] (plain string). Success
leaves NO file (honest absence). Lock law: typed locks forever; untyped writes
only when no file exists (direct-helper check).
Engine-driven with the fake duckwork (FAKE_MODE=typed_maxturns / untyped_report),
plus an importlib door read and a direct helper call.
"""
import importlib.util
import json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home76"
os.environ["DUCKWORK_HOME"] = str(HOME)  # door's run_dir()/act_status() resolve home in-process
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake76.log"))
FAKE = str(BUILD / "fake")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

def mk(run_id, nodes, extra=None):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    cfg = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}
    cfg.update(extra or {})
    (r / "run.json").write_text(json.dumps(cfg))
    return r

def wf(run_id, extra_env=None):
    e = dict(env, **(extra_env or {}))
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=e, capture_output=True, text=True, timeout=120)
    return p.stdout.strip()

def load_door():
    spec = importlib.util.spec_from_file_location("tier_report_door", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    return door

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

# ---- (a) typed child death -> tier=typed on disk AND door read model ----
r = mk("tier-typed", [{"id": "a", "type": "agent", "goal": "typed budget death"}])
wf("tier-typed", {"FAKE_MODE": "typed_maxturns"})
tier_path = r / "turn_report.tier"
check("(a) failed run dir carries turn_report.tier", tier_path.exists())
rec = json.loads(tier_path.read_text()) if tier_path.exists() else {}
check("(a) tier=typed", rec.get("tier") == "typed", json.dumps(rec))
check("(a) via names the node", rec.get("via") == "a", json.dumps(rec))
check("(a) at is iso", "T" in (rec.get("at") or "") and "-" in (rec.get("at") or ""), rec.get("at"))
door = load_door()
st = door.act_status({"run_id": "tier-typed"})
check("(a) act_status surfaces turn_report=typed", st.get("turn_report") == "typed", json.dumps(st)[:200])

# ---- (b) report WITHOUT the key -> untyped ----
r = mk("tier-untyped", [{"id": "b", "type": "agent", "goal": "report without the typed key"}])
wf("tier-untyped", {"FAKE_MODE": "untyped_report"})
tier_path = r / "turn_report.tier"
rec = json.loads(tier_path.read_text()) if tier_path.exists() else {}
check("(b) tier=untyped when the key is absent", rec.get("tier") == "untyped", json.dumps(rec))
st = door.act_status({"run_id": "tier-untyped"})
check("(b) act_status surfaces turn_report=untyped", st.get("turn_report") == "untyped", json.dumps(st)[:200])

# ---- (c) fully successful run -> honest absence ----
r = mk("tier-ok", [{"id": "c", "type": "agent", "goal": "fine task"}])
wf("tier-ok")
rec = json.loads((r / "nodes" / "c.json").read_text())
check("(c) run really succeeded", rec.get("status") == "done", str(rec.get("status")))
check("(c) NO turn_report.tier on success", not (r / "turn_report.tier").exists())
st = door.act_status({"run_id": "tier-ok"})
check("(c) act_status carries no turn_report key", "turn_report" not in st)

# ---- (d) lock law: direct helper — typed then untyped stays typed ----
spec = importlib.util.spec_from_file_location("tier_report_wf", ROOT / "wf.py")
wfm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wfm)
d = BUILD / "home76-lockdir"
shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
rp = d / "child.turn.json"
rp.write_text(json.dumps({"turn_exit_reason": "max_iterations_reached(61/60)"}))
wfm._note_turn_tier(d, "n1", rp)
first = json.loads((d / "turn_report.tier").read_text())
check("(d) first note is typed via n1", first["tier"] == "typed" and first["via"] == "n1", json.dumps(first))
rp.write_text(json.dumps({"nope": 1}))  # now an untyped report
wfm._note_turn_tier(d, "n2", rp)
second = json.loads((d / "turn_report.tier").read_text())
check("(d) typed locks forever (untyped never rewrites)", second["tier"] == "typed" and second["via"] == "n1", json.dumps(second))
# and the mirror: untyped first locks too
d2 = BUILD / "home76-lockdir2"
shutil.rmtree(d2, ignore_errors=True); d2.mkdir(parents=True)
wfm._note_turn_tier(d2, "x", d2 / "missing.turn.json")   # no report at all -> untyped
rp2 = d2 / "child.turn.json"; rp2.write_text(json.dumps({"turn_exit_reason": "max_iterations_reached(2/1)"}))
wfm._note_turn_tier(d2, "y", rp2)
check("(d) untyped first also writes exactly once", json.loads((d2 / "turn_report.tier").read_text())["tier"] == "untyped")

print(("PASS" if fails == 0 else "FAIL") + f" test_tier_report_0924 ({fails} failing checks)")
sys.exit(0 if fails == 0 else 1)
