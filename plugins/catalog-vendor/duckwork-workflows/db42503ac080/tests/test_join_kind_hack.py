#!/usr/bin/env python3
"""jam-h25 join-kind: a zero-spawn node that commits a deterministic json object of
named parent outputs at the wave boundary, beside echo in the scheduler.
Graph: {id, type:'join', after:[ids], keys:{label:'<node_id>.<dotted.path>'},
wait:'terminal'|'any'}; JOIN_KEYS closed set at validator + door spec.
Style of tests/test_sprint101w2_C1-defaults.py: plain asserts, PASS/FAIL, exit 0 green.
"""
import importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_join"
RUNS = HOME / "workflows"
if RUNS.exists(): shutil.rmtree(RUNS)   # hermetic
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake_join.log"))
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE
sys.path.insert(0, str(BUILD.parent))
import wfcommon

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and cond

def mk(run_id, nodes, name="join"):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
    return r

def wf(run_id):
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=120)
    return p.stdout.strip()

# ---- door (loaded by path, like the C1 test) ----
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — WF_RUNS_ROOT pins runs/library
# and wf_test_isolation neutralises settings.runs_root; without both, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(RUNS)
_spec = importlib.util.spec_from_file_location("hw_join", BUILD.parent / "__init__.py")
hw = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
def call(**a):
    return json.loads(hw.handle(a))

(BUILD / "fake_join.log").write_text("")

# ---------- validator: closed set + key grammar ----------
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "a.result"}, "wait": "any"},
])
check("valid join accepted", errs == [], errs)
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "a.result"}, "goal": "no"},
])
check("unknown join key rejected (closed set {id,type,after,keys,wait})",
      any(e["node"] == "j" and e["field"] == "goal" for e in errs), errs)
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "a.result"}, "wait": "soon"},
])
check("bad join wait rejected", any(e["node"] == "j" and e["field"] == "wait" for e in errs), errs)
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "b.result"}},
])
check("join key ref must name an ancestor", any(e["field"] == "keys.x" for e in errs), errs)
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "j", "type": "join", "after": ["a"]},
])
check("join without keys rejected", any(e["node"] == "j" and e["field"] == "keys" for e in errs), errs)
errs = wfcommon.validate_graph_errors([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "?", "keys": {"x": "a.result"}},
])
check("keys on a non-join rejected", any(e["field"] == "keys" for e in errs), errs)

# ---------- door rejects a bad join at run (errors[], no write) ----------
bad = call(action="run", graph={"name": "bad-join", "nodes": [
    {"id": "a", "type": "agent", "goal": "LIST: go"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "a.result"}, "output": 1}]})
fl = [(e.get("node"), e.get("field")) for e in bad.get("errors", [])]
check("door rejects join.output with field path", ("j", "output") in fl, bad)

# ---------- runner: two agents then a join merges with ZERO extra spawns ----------
n_before = len((BUILD / "fake_join.log").read_text().splitlines())
r = mk("j-merge", [
    {"id": "a", "type": "agent", "goal": "LIST: alpha"},
    {"id": "b", "type": "agent", "goal": "LIST: beta"},
    {"id": "j", "type": "join", "after": ["a", "b"],
     "keys": {"beta_out": "b.result", "alpha_out": "a.result", "alpha_first": "a.result.0"}},
], name="merge")
out = wf("j-merge")
check("two-agents-then-join ends done", out.startswith("WORKFLOW_DONE j-merge"), out)
rec = json.loads((r / "nodes/j.json").read_text())
check("join commits merged object of named parent outputs",
      rec["status"] == "done" and rec["output"] ==
      {"alpha_first": "a", "alpha_out": ["a", "b", "c"], "beta_out": ["a", "b", "c"]}, rec)
check("join spawns NO child", len((BUILD / "fake_join.log").read_text().splitlines()) == n_before + 2)
ev = (r / "events.jsonl").read_text()
check("node.done logged with join=True", '"event": "node.done"' in ev
      and '"join": true' in ev, ev[-300:])
check("join commits ms=0 (metrics row stays zero-cost)", rec.get("ms") == 0, rec)

# deterministic byte order: keys committed sorted by label
check("merged object is key-sorted (byte-stable)",
      json.dumps(rec["output"]) == json.dumps(rec["output"], sort_keys=True))

# replay-skip: second run commits nothing new
before = ev.count('"node.done"')
out2 = wf("j-merge")
check("join replay-skip: second run done, no new node.done",
      out2.startswith("WORKFLOW_DONE j-merge")
      and (r / "events.jsonl").read_text().count('"node.done"') == before,
      (r / "events.jsonl").read_text()[len(ev):])

# join output feeds downstream inputs like any done node
r = mk("j-feed", [
    {"id": "a", "type": "agent", "goal": "LIST: alpha"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"picked": "a.result"}},
    {"id": "c", "type": "agent", "after": ["j"], "goal": "LIST: go", "inputs": ["j.picked"]},
], name="feed")
out = wf("j-feed")
check("agent downstream of join consumes its object", out.startswith("WORKFLOW_DONE j-feed"), out)

# ---------- wait:'terminal' fails the join when a parent failed (loud, not null) ----------
r = mk("j-termfail", [
    {"id": "a", "type": "agent", "goal": "LIST: alpha"},
    {"id": "f", "type": "agent", "goal": "FAILME"},
    {"id": "j", "type": "join", "after": ["a", "f"], "keys": {"x": "a.result", "y": "f.result"}},
], name="termfail")
out = wf("j-termfail")
rec = json.loads((r / "nodes/j.json").read_text())
check("wait:terminal join FAILS when a parent failed (run fails too)",
      out.startswith("WORKFLOW_FAILED j-termfail") and rec["status"] == "failed"
      and rec.get("error_class") == "precondition", (out, rec))

# ---------- wait:'any' quorum flavour: failed leg dropped, join commits ----------
r = mk("j-any", [
    {"id": "a", "type": "agent", "goal": "LIST: alpha"},
    {"id": "f", "type": "agent", "goal": "FAILME"},
    {"id": "j", "type": "join", "after": ["a", "f"], "keys": {"x": "a.result", "y": "f.result"},
     "wait": "any"},
], name="any")
out = wf("j-any")
recj = json.loads((r / "nodes/j.json").read_text()) if (r / "nodes/j.json").exists() else {}
recf = json.loads((r / "nodes/f.json").read_text())
check("wait:any join commits the live leg (dropped failed key)",
      recj.get("status") == "done" and recj.get("output") == {"x": ["a", "b", "c"]}, (recj, recf))

# ---------- author typo: committed parent, missing dotted path -> fails ----------
r = mk("j-typo", [
    {"id": "a", "type": "agent", "goal": "LIST: alpha"},
    {"id": "j", "type": "join", "after": ["a"], "keys": {"x": "a.nope"}},
], name="typo")
out = wf("j-typo")
rec = json.loads((r / "nodes/j.json").read_text())
check("join key typo fails the node (inputs law)",
      rec["status"] == "failed" and "no such path" in rec.get("error", ""), rec)

print("OVERALL", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
