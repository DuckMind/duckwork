#!/usr/bin/env python3
"""Lane C1-defaults: #8 run-level `defaults:` wired at the door (validated + baked
before graph.json so runner/fingerprints see ONE resolved truth), #11 shape presets
(closed list at the door, preset fills max_turns/timeout when unset, explicit keys
win) + extend-not-kill (one 50% extension when the child's log shows a recent tool
event; kill on the second expiry), #13 echo node (commits `output` verbatim, no
spawn, replay-skip by fingerprint, `after` honoured).
Style of tests/test_engine.py: plain asserts, PASS/FAIL lines, exit 0 green.
"""
import importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_c1"
RUNS = HOME / "workflows"
if RUNS.exists(): shutil.rmtree(RUNS)   # hermetic: never trust leftovers
env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(HOME / "workflows"), FAKE_LOG=str(BUILD / "fake_c1.log"))
FAKE = str(BUILD / "fake")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = FAKE
sys.path.insert(0, str(BUILD.parent))
import wfcommon

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and cond

def sh(*cmd):
    return subprocess.run(cmd, env=env, capture_output=True, text=True)

def mk(run_id, nodes, meta_extra=None, name="c1"):
    r = RUNS / run_id
    if r.exists(): shutil.rmtree(r)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    meta = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}
    meta.update(meta_extra or {})
    (r / "run.json").write_text(json.dumps(meta))
    return r

def wf(run_id):
    p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                       env=env, capture_output=True, text=True, timeout=120)
    return p.stdout.strip()

# ---- door (loaded by path, like test_door.py) ----
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
_spec = importlib.util.spec_from_file_location("hw_c1", BUILD.parent / "__init__.py")
hw = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
def call(**a):
    return json.loads(hw.handle(a))

(BUILD / "fake_c1.log").write_text("")

# ---------- #8/#11 door: defaults baked into graph.json before write ----------
G = {"name": "c1-defaults", "defaults": {"max_turns": 40, "timeout": 600,
                                         "context": "HARD RULES: commit first.",
                                         "reasoning": "low"},
     "nodes": [
         {"id": "plain", "type": "agent", "goal": "LIST: go"},
         {"id": "explicit", "type": "agent", "goal": "LIST: go", "after": ["plain"],
          "max_turns": 7, "timeout": 99, "context": "node own ctx",
          "reasoning": "high"},
         {"id": "shaped", "type": "agent", "goal": "LIST: go", "after": ["plain"],
          "shape": "recon", "timeout": 1200},
     ]}
r = call(action="run", graph=json.loads(json.dumps(G)))
rid = r.get("run_id")
check("run with defaults launches", bool(rid), r)
baked = json.loads((RUNS / rid / "graph.json").read_text())
bn = {n["id"]: n for n in baked["nodes"]}
check("defaults fill unset keys", bn["plain"].get("max_turns") == 40
      and bn["plain"].get("timeout") == 600 and bn["plain"].get("reasoning") == "low", bn["plain"])
check("explicit node keys win over defaults", bn["explicit"].get("max_turns") == 7
      and bn["explicit"].get("timeout") == 99 and bn["explicit"].get("reasoning") == "high", bn["explicit"])
check("defaults.context prepended once, node ctx follows",
      bn["explicit"].get("context") == "HARD RULES: commit first.\n\nnode own ctx", bn["explicit"].get("context"))
check("node without own context gets preamble only",
      bn["plain"].get("context") == "HARD RULES: commit first.", bn["plain"].get("context"))
check("#11 shape fills unset budget from preset",
      bn["shaped"].get("max_turns") == wfcommon.SHAPE_PRESETS["recon"]["max_turns"], bn["shaped"])
check("#11 explicit key still beats shape preset", bn["shaped"].get("timeout") == 1200, bn["shaped"])
st = call(action="wait", run_id=rid, timeout=90)
check("defaults run reaches done", st.get("status") == "done", st.get("status"))
# replay-skip integrity: the FINGERPRINTS come from the baked graph (one resolved truth)
check("defaults block survives on the frozen graph", baked.get("defaults") == G["defaults"])

# ---------- #8 idempotent: re-applying the baked graph changes nothing ----------
once = wfcommon.apply_graph_defaults(json.loads(json.dumps(baked)))
twice = wfcommon.apply_graph_defaults(json.loads(json.dumps(once)))
check("apply_graph_defaults idempotent (context prepended once)",
      json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True))
check("no double-preamble", once["nodes"][1]["context"].count("HARD RULES") == 1,
      once["nodes"][1]["context"])

# ---------- #8/#11 door rejects invalid defaults/shape with field paths ----------
bad = call(action="run", graph={
    "name": "bad-d", "defaults": {"max_turns": 0, "bogus": 1},
    "nodes": [{"id": "a", "type": "agent", "goal": "x"}]})
fl = [(e.get("field"), e.get("node")) for e in bad.get("errors", [])]
check("invalid defaults.max_turns rejected at the door", ("defaults.max_turns", None) in fl, bad)
check("unknown defaults key rejected with field path", ("defaults.bogus", None) in fl, bad)
bad2 = call(action="run", graph={
    "name": "bad-s", "nodes": [{"id": "a", "type": "agent", "goal": "x", "shape": "wat"}]})
fl2 = [(e.get("field"), e.get("node")) for e in bad2.get("errors", [])]
check("invalid shape rejected at the door with field path", ("shape", "a") in fl2, bad2)
bad3 = call(action="run", graph={
    "name": "bad-p", "defaults": "not-an-object",
    "nodes": [{"id": "a", "type": "agent", "goal": "x"}]})
check("non-object defaults rejected", "defaults" in json.dumps(bad3), bad3)

# amend also bakes before the write (resolved truth on both paths)
rid2 = call(action="run",
            graph={"name": "c1-amend", "nodes": [{"id": "a", "type": "agent", "goal": "LIST: go"}]}
            ).get("run_id")
call(action="wait", run_id=rid2, timeout=60)
am = call(action="amend", run_id=rid2, graph={"name": "c1-amend",
        "defaults": {"timeout": 500},
        "nodes": [{"id": "a", "type": "agent", "goal": "LIST: go v2"}]})
check("amend with defaults accepted", am.get("ok"), am)
am_baked = {n["id"]: n for n in json.loads((RUNS / rid2 / "graph.json").read_text())["nodes"]}
check("amend bakes defaults before graph.json", am_baked["a"].get("timeout") == 500, am_baked["a"])

# ---------- #13 echo node: echo-only graph runs to done, no spawn, after honoured ----------
n_before = len((BUILD / "fake_c1.log").read_text().splitlines())
r = mk("c1-echo", [
    {"id": "fact", "type": "echo", "output": {"version": "1.2.3", "notes": "fixed json"}},
    {"id": "more", "type": "echo", "after": ["fact"], "output": {"joined": True}},
], name="echo-only")
out = wf("c1-echo")
check("echo-only graph ends done", out.startswith("WORKFLOW_DONE c1-echo"), out)
check("echo commits output verbatim",
      json.loads((r / "nodes/fact.json").read_text())["output"] == {"version": "1.2.3", "notes": "fixed json"})
check("echo honours after (ordered commit)",
      json.loads((r / "nodes/more.json").read_text())["output"] == {"joined": True})
check("echo spawns NO child",
      len((BUILD / "fake_c1.log").read_text().splitlines()) == n_before)
ev = (r / "events.jsonl").read_text()
check("node.done logged for echo", '"event": "node.done"' in ev and '"echo": true' in ev, ev[-300:])
# replay-skip by fingerprint: re-run commits nothing new, no re-log
ev_lines_before = len(ev.splitlines())
out2 = wf("c1-echo")
check("echo replay-skip: second run done with no new node.done",
      out2.startswith("WORKFLOW_DONE c1-echo")
      and (r / "events.jsonl").read_text().count('"node.done"') == 2,
      (r / "events.jsonl").read_text()[ev_lines_before:])
# echo feeds downstream inputs
r = mk("c1-echo-feed", [
    {"id": "fact", "type": "echo", "output": {"items": ["x", "y"]}},
    {"id": "user", "type": "agent", "after": ["fact"], "goal": "LIST: go", "inputs": ["fact.items"]},
], name="echo-feed")
out = wf("c1-echo-feed")
check("agent downstream of echo consumes its output", out.startswith("WORKFLOW_DONE c1-echo-feed"), out)

# ---------- #11 extend-not-kill ----------
# active at the wall (early flushed log write, then still cooking) -> ONE extension, node.extended logged
r = mk("c1-extend", [{"id": "a", "type": "agent", "goal": "SLOW", "timeout": 2}],
       name="extend")
env_ext = dict(env, FAKE_MODE="early", FAKE_EARLY_SLEEP="2.5")
p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", "c1-extend"],
                   env=env_ext, capture_output=True, text=True, timeout=120)
out = p.stdout.strip()
ev = (r / "events.jsonl").read_text()
check("active child extended past the wall and finished done", out.startswith("WORKFLOW_DONE c1-extend"), out)
check("node.extended logged with extra_s", '"event": "node.extended"' in ev and '"extra_s": 1' in ev, ev[-400:])
check("extension is ONE 50% grant", ev.count('"node.extended"') == 1, ev[-400:])

# silent hang at the wall (no log activity after spawn) -> NO extension, killed at the wall
r = mk("c1-noextend", [{"id": "a", "type": "agent", "goal": "HANG", "timeout": 2}],
       name="noextend")
env_hang = dict(env, FAKE_MODE="hang", FAKE_HANG_SEC="30")
t0 = time.time()
p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", "c1-noextend"],
                   env=env_hang, capture_output=True, text=True, timeout=120)
out = p.stdout.strip()
elapsed = time.time() - t0
ev = (r / "events.jsonl").read_text()
rec = json.loads((r / "nodes/a.json").read_text())
check("silent hang killed at the wall (no extension)", "node.extended" not in ev, ev[-300:])
check("timeout death is error_class timeout", rec.get("error_class") == "timeout", rec)
check("killed near the wall, not wall+50%", elapsed < 8, f"elapsed={elapsed:.1f}s")

# second expiry after an extension -> kill (error_class timeout), extension was only ONE grant
r = mk("c1-kill2", [{"id": "a", "type": "agent", "goal": "SLOW", "timeout": 2}],
       name="kill2")
env_k = dict(env, FAKE_MODE="hang", FAKE_HANG_SEC="30", FAKE_MODE_KEEP="")
# hang prints nothing; use 'early' with a sleep beyond wall+50% to get activity THEN a death:
env_k = dict(env, FAKE_MODE="early", FAKE_EARLY_SLEEP="30")
p = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", "c1-kill2"],
                   env=env_k, capture_output=True, text=True, timeout=120)
ev = (r / "events.jsonl").read_text()
rec = json.loads((r / "nodes/a.json").read_text())
check("extended child that never finishes is killed on the second expiry",
      rec.get("error_class") == "timeout", rec)
check("exactly one extension granted", ev.count('"node.extended"') == 1, ev[-400:])

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
