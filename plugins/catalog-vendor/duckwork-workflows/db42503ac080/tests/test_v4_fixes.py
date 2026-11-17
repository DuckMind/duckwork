#!/usr/bin/env python3
"""Regression suite for sign-off-v3 must-file items (v4): each test must FAIL on
the pre-v4 code. Sandbox: WF_TEST_BUILD/DUCKWORK_HOME under tests/home4, fake launcher.
Run from the tests dir with plain python3."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home4"
RUNS = HOME / "workflows"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD.parent))
import wfcommon

env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(BUILD / "fake4.log"))
FAKE = str(BUILD / "fake")
ok = True

def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

def mk(run_id, nodes, name="t", **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": name, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf(run_id):
    return subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=120).stdout.strip()

shutil.rmtree(HOME, ignore_errors=True)
(BUILD / "fake4.log").write_text("")

# W1: when-expression must be validated value-INDEPENDENTLY — a trailing ')' after a
# comparison whose runtime raises TypeError must be rejected at VALIDATION, and must
# never let the gate silently skip at runtime.
import wfcommon as W
err = W.when_expr_ok("out.a.result > 'z')")
check("W1a validation catches trailing ) regardless of data", err is not None, str(err))
try:
    skips = W.when_true({"when": "out.a.result > 'z')"}, {"a": {"result": "ok"}})
    held = skips is True  # a bool return must be the hold branch, never a skip
except ValueError:
    held = True  # raises -> wf.py call-site catches to HOLD + gate.when_error
check("W1b runtime never False-skips a broken when", held)

# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
# W2: legacy def_hash records must NOT resurrect after an ancestor re-runs.
# a -> b(legacy stamp) -> g(legacy gate answer). Amend a, run: a re-runs and gains
# efp; b and the gate answer must go stale (chain no longer all-legacy).
nodes = [{"id": "a", "type": "agent", "goal": "LIST: go"},
         {"id": "b", "type": "agent", "after": ["a"], "goal": "mid"},
         {"id": "g", "type": "gate", "after": ["b"], "question": "q"},
         {"id": "z", "type": "agent", "after": ["g"], "goal": "end"}]
r = mk("w2", nodes)
wf("w2")                                     # holds at g
# rewrite a,b records to legacy stamps (drop efp, own def_hash only), answer gate with legacy _def
recs = {}
for nid in ("a", "b"):
    p = r / "nodes" / f"{nid}.json"
    rec = json.loads(p.read_text()); rec.pop("efp", None)
    rec["def_hash"] = W.def_hash({n["id"]: n for n in nodes}[nid]) if False else W.def_hash(next(n for n in nodes if n["id"] == nid))
    p.write_text(json.dumps(rec)); recs[nid] = rec
gnode = next(n for n in nodes if n["id"] == "g")
(r / "gates/g.json").write_text(json.dumps({"answer": "legacy-yes", "_def": W.def_hash(gnode)}))
st_b, _ = W.node_rec(r, next(n for n in nodes if n["id"] == "b"), {n["id"]: n for n in nodes})
check("W2a pure-legacy chain validates as done", st_b == "done", st_b)
ans = W.gate_answer_valid(r, gnode, {n["id"]: n for n in nodes})
check("W2b both-rule-matching unstamped gate answer validates (F5, 2026-09-28)", ans is not None and ans["answer"] == "legacy-yes", str(ans))
# now amend a and resume: a re-runs -> gains efp -> b legacy chain broken -> b pending
g = json.loads((r / "graph.json").read_text())
g["nodes"][0]["goal"] = "LIST: go CHANGED"
(r / "graph.json").write_text(json.dumps(g))
out = wf("w2")
brec = json.loads((r / "nodes/b.json").read_text())
check("W2c amended ancestor forces legacy-stamped b to re-run (has efp now)",
      "efp" in brec and "CHANGED" not in json.dumps(brec), json.dumps(brec)[:120])
tail = (r / "events.jsonl").read_text().split('"run.resumed"')[-1]
check("W2d legacy gate answer did NOT auto-pass after upstream rerun — re-held",
      '"gate.released"' not in tail and '"gate.held"' in tail, tail[:160])

# W3: admission — two concurrent runners, exactly one proceeds
r = mk("w3", [{"id": "a", "type": "agent", "goal": "SLEEP 3"}])
p1 = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "w3"], env=env,
                      stdout=subprocess.PIPE, text=True)
time.sleep(0.7)
p2 = subprocess.run([sys.executable, str(BUILD.parent / "wf.py"), "run", "w3"], env=env,
                    capture_output=True, text=True, timeout=30)
p1.wait(timeout=60)
out1 = p1.stdout.read().strip()
check("W3 second runner refused (BUSY), first owns the run",
      "WORKFLOW_BUSY" in p2.stdout and "WORKFLOW_DONE w3" in out1,
      f"p1={out1[:60]} p2={p2.stdout.strip()[:60]}")
# lock survives exit cleanly: a third run of the same id re-runs to done via replay-skip
out = wf("w3")
check("W3b flock released at exit — respawn reaches DONE", out.startswith("WORKFLOW_DONE w3"), out)

# W4: stop during a fanout must prevent REMAINING launches (queued work cancelled)
(BUILD / "fake4.log").write_text("")
r = mk("w4", [{"id": "f", "type": "agent", "fanout": {"items": ["a", "b", "c", "d", "e", "f"],
                                                      "goal": "SLEEP 2 item {item}", "quorum": 1}}],
         item_concurrency=2)
p = subprocess.Popen([sys.executable, str(BUILD.parent / "wf.py"), "run", "w4"], env=env,
                     stdout=subprocess.PIPE, text=True)
time.sleep(0.5)
(r / "stop.request").write_text("1")
out = p.communicate(timeout=90)[0].strip()
spawned = len([l for l in (BUILD / "fake4.log").read_text().splitlines() if "SLEEP 2" in l])
check("W4 stop emitted WORKFLOW_STOPPED", "WORKFLOW_STOPPED" in out, out[:80])
check("W4 queued fanout items did not all launch after stop", spawned < 6, f"spawned={spawned}")

# W5 (desktop): register() must NOT bypass the api() wrapper — static assertion on source
src = (BUILD.parent / "desktop" / "plugin.js").read_text()
check("W5 register assigns ctxRest, never overwrites api",
      "ctxRest = (path, opts) => ctx.rest" in src and "api = (path, opts) => ctx.rest" not in src)

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
