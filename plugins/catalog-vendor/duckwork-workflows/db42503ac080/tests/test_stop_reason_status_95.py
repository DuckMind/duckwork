#!/usr/bin/env python3
"""est-2ek.1.95: status surfaces a STRUCTURED stop_reason so budget exhaustion
is never error_class=unknown.

act_status (and act_wait, via the same one-read path) adds
`stop_reason = {turn_tier, tier_via_node, source: "turn_report.tier"}`, plus
`class: "cap_exhausted"` when a failed/partial node record's error_class says
so — pure passthrough of bytes already in hand (derive-only, A3 law). No key at
all when evidence is absent (honest absence); never relabel partial as passed.

Engine-driven with the fake duckwork (FAKE_MODE=maxturns / typed_maxturns /
untyped_report), mirroring tests/test_tier_report_0924.py's harness shape.
"""
import importlib.util
import json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
sys.path.insert(0, str(ROOT))
HOME = BUILD / "home95"
os.environ["DUCKWORK_HOME"] = str(HOME)  # door's run_dir()/act_status() resolve home in-process
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
RUNS = HOME / "workflows"
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake95.log"))
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
    spec = importlib.util.spec_from_file_location("stop_reason_door", ROOT / "__init__.py")
    door = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(door)
    return door

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

door = load_door()

# ---- (a) typed max-turns death -> stop_reason typed + class=cap_exhausted ----
r = mk("sr95-typed", [{"id": "a", "type": "agent", "goal": "ty sr95-typed", "max_turns": 60}])
wf("sr95-typed", {"FAKE_MODE": "typed_maxturns"})
rec = json.loads((r / "nodes" / "a.json").read_text())
check("(a) node record really says cap_exhausted", rec.get("error_class") == "cap_exhausted",
      json.dumps(rec)[:200])
st = door.act_status({"run_id": "sr95-typed"})
sr = st.get("stop_reason")
check("(a) act_status carries stop_reason dict", isinstance(sr, dict), json.dumps(st)[:220])
check("(a) stop_reason.turn_tier == typed", isinstance(sr, dict) and sr.get("turn_tier") == "typed",
      json.dumps(sr))
check("(a) stop_reason.tier_via_node names the node", isinstance(sr, dict) and sr.get("tier_via_node") == "a",
      json.dumps(sr))
check("(a) stop_reason.source is turn_report.tier", isinstance(sr, dict) and sr.get("source") == "turn_report.tier",
      json.dumps(sr))
check("(a) stop_reason.class == cap_exhausted (from the node record)",
      isinstance(sr, dict) and sr.get("class") == "cap_exhausted", json.dumps(sr))
check("(a) legacy turn_report string unchanged", st.get("turn_report") == "typed", json.dumps(st)[:200])
check("(a) never relabels: record status stays failed", rec.get("status") == "failed", str(rec.get("status")))

# ---- (b) untyped report death -> stop_reason typed-shape keys, NO class ----
r = mk("sr95-untyped", [{"id": "b", "type": "agent", "goal": "report without the typed key"}])
wf("sr95-untyped", {"FAKE_MODE": "untyped_report"})
rec = json.loads((r / "nodes" / "b.json").read_text())
check("(b) node record error_class stays unknown (no invention)",
      rec.get("error_class") == "unknown", json.dumps(rec)[:200])
st = door.act_status({"run_id": "sr95-untyped"})
sr = st.get("stop_reason")
check("(b) stop_reason present with tier=untyped", isinstance(sr, dict) and sr.get("turn_tier") == "untyped",
      json.dumps(st)[:220])
check("(b) stop_reason.tier_via_node == b", isinstance(sr, dict) and sr.get("tier_via_node") == "b",
      json.dumps(sr))
check("(b) NO class key invented when the record says unknown",
      isinstance(sr, dict) and "class" not in sr, json.dumps(sr))
check("(b) stop_reason.source is turn_report.tier", isinstance(sr, dict) and sr.get("source") == "turn_report.tier",
      json.dumps(sr))

# ---- (c) prose maxturns death (no report contract): tier=untyped, no class ----
r = mk("sr95-maxturns", [{"id": "c", "type": "agent", "goal": "mt sr95-maxturns", "max_turns": 3}])
wf("sr95-maxturns", {"FAKE_MODE": "maxturns"})
rec = json.loads((r / "nodes" / "c.json").read_text())
check("(c) prose death stays error_class=unknown", rec.get("error_class") == "unknown",
      json.dumps(rec)[:200])
st = door.act_status({"run_id": "sr95-maxturns"})
sr = st.get("stop_reason")
check("(c) stop_reason surfaces the untyped tier so the death is explainable",
      isinstance(sr, dict) and sr.get("turn_tier") == "untyped" and sr.get("tier_via_node") == "c",
      json.dumps(st)[:220])
check("(c) no class invented from prose", isinstance(sr, dict) and "class" not in sr, json.dumps(sr))

# ---- (d) fully successful run -> honest absence: no stop_reason at all ----
r = mk("sr95-ok", [{"id": "d", "type": "agent", "goal": "fine task"}])
wf("sr95-ok")
rec = json.loads((r / "nodes" / "d.json").read_text())
check("(d) run really succeeded", rec.get("status") == "done", str(rec.get("status")))
st = door.act_status({"run_id": "sr95-ok"})
check("(d) NO stop_reason key on success", "stop_reason" not in st, json.dumps(st)[:220])
check("(d) NO turn_report key on success (legacy law preserved)", "turn_report" not in st)

# ---- (e) act_wait rides the SAME one-read path ----
st = door.act_wait({"run_id": "sr95-typed", "timeout": 5})
sr = st.get("stop_reason")
check("(e) act_wait carries the same stop_reason shape",
      isinstance(sr, dict) and sr.get("turn_tier") == "typed" and sr.get("class") == "cap_exhausted"
      and sr.get("source") == "turn_report.tier", json.dumps(st)[:220])

print(("PASS" if fails == 0 else "FAIL") + f" test_stop_reason_status_95 ({fails} failing checks)")
sys.exit(0 if fails == 0 else 1)
