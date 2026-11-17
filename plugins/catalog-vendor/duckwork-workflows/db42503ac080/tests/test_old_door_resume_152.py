#!/usr/bin/env python3
"""#152 — the gate answer must never be consumed by a door that cannot honor it.

The field shape (fully reproduced at e1c16ae with a v1.1.2 worktree): a run is
held at a human gate; the runner is SIGKILLed; the release lands from an OLD
door whose bundled wf.py predates the committed graph's grammar. The old door
writes gates/<id>.json and auto-resumes; the respawned OLD runner revalidates
the committed graph.json, refuses the new grammar ('node a: unknown key'),
records runner_exit 'crashed: graph invalid', and the run lands failed with the
answer CONSUMED — a second release answers 'gate already answered (current
graph)'. The human answer is unrecoverable and the lap must be re-walked.

Two durable shapes, both required:
  T1 door-side: release runs the respawner's OWN validator over the committed
     graph BEFORE writing anything; a refused grammar => ok:false +
     'cannot drive this graph', NO gate file, NO respawn, hold intact.
  T2 runner-side: an admission graph-invalid death un-consumes a pending-gate
     answer — gates/<id>.json -> gates/<id>.json.unconsumed (evidence kept),
     event gate.answer_unconsumed (carrying the prior answer's 'at'), NO
     runner_exit written so the run reads 'interrupted' (resumeable), and a
     later release from a capable door re-lands the answer and the run lands
     done.
  T3 the already-committed-answer law + stopped/unknown-gate/unknown-run
     refusals stay byte-identical (test-locked strings).
  T4 golden-solo EMPTY: no skew => the normal release path (auto_resumed
     included) behaves exactly as before.

Standalone, stdlib-only:
  PYTHONPATH=<clone> python3 tests/test_old_door_resume_152.py
"""
import importlib.util, json, os, shutil, signal, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE)
ROOT = BUILD.parent   # the repo root (tests/ lives under it)
HOME = HERE / "home-old-door-152"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
sys.path.insert(0, str(BUILD))
sys.path.insert(0, str(BUILD.parent))

def fresh_door(tag):
    spec = importlib.util.spec_from_file_location("hw152_" + tag, ROOT / "__init__.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import wf_test_isolation as _iso71; _iso71.install(m)  # #71 r5 pin
    return m

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def call(door, **a):
    return json.loads(door.handle(a))

def events(run):
    try:
        return [json.loads(l) for l in (run / "events.jsonl").read_text(errors="replace").splitlines() if l.strip()]
    except FileNotFoundError:
        return []

def wait_for(pred, timeout=40, tick=0.1):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(tick)
    return False

G = {"name": "old-door-152", "nodes": [
    {"id": "a", "type": "agent", "goal": "LIST: go"},
    {"id": "g1", "type": "gate", "after": ["a"], "question": "ship?", "options": ["yes", "no"]},
    {"id": "b", "type": "agent", "after": ["g1"], "goal": "combine"},
]}
# The skew key must be REJECTED by the current validator (the v1.1.2 probe used
# on_fail; that key shipped in v1.3.0, so the shape is pinned with a key no
# grammar version has ever known).
SKEW_KEY = "zz_not_in_any_grammar_152"
SKEW = json.loads(json.dumps(G)); SKEW["nodes"][0][SKEW_KEY] = True

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

os.environ.update(DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), DUCKWORK_WF_DUCKWORK_BIN=FAKE)

# sanity pin: the injected key really is an admission-refused unknown key
_probe = __import__("wfcommon").validate_graph_errors(SKEW["nodes"])
check("pin: injected skew key is refused by the validator itself",
      _probe and any(SKEW_KEY in (e.get("field") or "") for e in _probe), _probe)

# ================================================================ T1 door-side
door = fresh_door("t1")
FAKE_PID_LOG_1 = str(HOME / "pids-t1.txt")
os.environ["FAKE_PID_LOG"] = FAKE_PID_LOG_1
r1 = call(door, action="run", graph=G)
rid1 = r1.get("run_id"); check("T1 setup: run launches", bool(rid1), r1)
st = call(door, action="wait", run_id=rid1, timeout=90)
check("T1 setup: lands held at g1", st.get("status") == "held",
      json.dumps({k: st.get(k) for k in ("status", "gate", "note")}))

# the held runner exits at the hold (the release-respawn shape); make sure it
# is truly dead (SIGKILL the survivor if the kernel kept it — the field crash
# shape) before the release drives the respawn path
try:
    pid = int((RUNS / rid1 / "wf.pid").read_text().strip())
    if door.runner_alive(RUNS / rid1):
        os.kill(pid, signal.SIGKILL)
except (FileNotFoundError, ValueError, ProcessLookupError):
    pass
check("T1 setup: runner dead", wait_for(lambda: not door.runner_alive(RUNS / rid1), 15))

# inject the skew: committed graph.json carries a key the respawner's admission
# validator refuses — byte-equivalent to the probe's on_fail@v1.1.2 skew.
(RUNS / rid1 / "graph.json").write_text(json.dumps(SKEW))
prior_pids = Path(FAKE_PID_LOG_1).read_text().split() if Path(FAKE_PID_LOG_1).exists() else []
rel = call(door, action="release", run_id=rid1, gate_id="g1", answer="yes")
check("T1 RED->GREEN: release refuses a graph it cannot honor",
      rel.get("ok") is False and "cannot drive this graph" in rel.get("error", ""), rel)
check("T1: no gate answer written (hold intact for a capable door)",
      not (RUNS / rid1 / "gates" / "g1.json").exists())
_now_pids = Path(FAKE_PID_LOG_1).read_text().split() if Path(FAKE_PID_LOG_1).exists() else []
check("T1: no respawn (no new fake child pid)", not (set(_now_pids) - set(prior_pids)), str(_now_pids))
st2 = call(door, action="status", run_id=rid1)
check("T1: gate node still pending (the hold survives the refused release)",
      (st2.get("nodes", {}).get("g1") or {}).get("status") == "pending",
      json.dumps(st2.get("nodes", {}).get("g1")))

# ============================================== T2 runner-side un-consume
# A capable door launches the run; the runner (subprocess) is monkeypatched at
# admission to refuse the committed graph — the field-old-runner shape (an old
# wf.py that no longer ships cannot be taught the door check; the runner leg
# covers it). A pending-gate answer on record must survive the death.
door2 = fresh_door("t2")
runner_src = (ROOT / "wf.py").read_text()
_seam = 'err = validate_graph(jload(run / "graph.json")["nodes"])'
assert _seam in runner_src, "admission validator seam moved — update the shim"
patched = runner_src.replace(_seam,
    "err = 'node a: unknown key'  # T2 shim: the old respawner's admission refusal", 1)
RUNNER152 = HOME / "wf152-patched.py"
RUNNER152.write_text(patched)

FAKE_PID_LOG_2 = str(HOME / "pids-t2.txt")
def spawn_patched(rid):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               DUCKWORK_WF_DUCKWORK_BIN=FAKE, FAKE_PID_LOG=FAKE_PID_LOG_2,
               PYTHONPATH=str(ROOT))
    return subprocess.Popen([sys.executable, str(RUNNER152), "run", rid],
                            cwd=str(ROOT),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

run2 = RUNS / "old152-t2"
run2.mkdir(parents=True); (run2 / "nodes").mkdir(); (run2 / "gates").mkdir()
(run2 / "graph.json").write_text(json.dumps(G))
(run2 / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
_byid = {n["id"]: n for n in G["nodes"]}
(run2 / "gates" / "g1.json").write_text(json.dumps({
    "answer": "yes", "_def": door2.efp(_byid, _byid["g1"]),
    "fp_rule_version": door2._common.FP_RULE_VERSION,
    "at": "2026-10-05T00:00:00+00:00"}))
p2 = spawn_patched("old152-t2")
out2 = p2.communicate(timeout=60)[0]
check("T2 setup: patched runner dies at admission graph-invalid", "graph invalid" in out2, out2[-200:])
check("T2 RED->GREEN: answer un-consumed to .unconsumed (never deleted)",
      not (run2 / "gates" / "g1.json").exists() and (run2 / "gates" / "g1.json.unconsumed").exists(),
      str(sorted(p.name for p in (run2 / "gates").iterdir())))
uc = [e for e in events(run2) if e.get("event") == "gate.answer_unconsumed"]
check("T2: gate.answer_unconsumed names the gate + the prior answer's 'at'",
      any(e.get("gate") == "g1" and e.get("answer_at") == "2026-10-05T00:00:00+00:00" for e in uc), str(uc))
st3 = call(door2, action="status", run_id="old152-t2")
check("T2: run stays interrupted-resumeable, not failed",
      st3.get("status") == "interrupted", json.dumps({k: st3.get(k) for k in ("status", "runner_exit")}))
rel2 = call(door2, action="release", run_id="old152-t2", gate_id="g1", answer="yes")
check("T2: release from a capable door lands the answer", bool(rel2.get("ok")), rel2)
st4 = call(door2, action="wait", run_id="old152-t2", timeout=90)
check("T2: run completes after the un-consume", st4.get("status") == "done",
      json.dumps({k: st4.get(k) for k in ("status", "done", "total", "runner_exit")}))

# ============================================================ T3 locked strings
door3 = fresh_door("t3")
os.environ["FAKE_PID_LOG"] = str(HOME / "pids-t3.txt")
r3 = call(door3, action="run", graph=G)
rid3 = r3["run_id"]
call(door3, action="wait", run_id=rid3, timeout=90)  # land on held
call(door3, action="release", run_id=rid3, gate_id="g1", answer="yes")
wait_for(lambda: ((door3._common.jload(RUNS / rid3 / "nodes" / "g1.json") or {})
                  .get("status") in ("done", "skipped")), 60)
rel_again = call(door3, action="release", run_id=rid3, gate_id="g1", answer="no")
check("T3: consumed answer stays consumed — exact string",
      rel_again.get("ok") is False and rel_again.get("error") == "gate already answered (current graph)",
      rel_again)
badg = call(door3, action="release", run_id=rid3, gate_id="nope", answer="x")
check("T3: unknown-gate error byte-identical",
      badg.get("error") == "no such gate node in this run", badg)
unk = call(door3, action="release", run_id="no-such-run-152", gate_id="g1", answer="x")
check("T3: unknown-run error byte-identical", unk.get("error") == "unknown run_id", unk)
r3b = call(door3, action="run", graph=G)
time.sleep(0.4)
call(door3, action="stop", run_id=r3b["run_id"]); time.sleep(1.5)
stopped_rel = call(door3, action="release", run_id=r3b["run_id"], gate_id="g1", answer="yes")
check("T3: stopped-run refusal byte-identical",
      stopped_rel.get("error") == "run is stopped/stop pending — answer refused; amend or re-run to continue",
      stopped_rel)

# ================================================================ T4 golden solo
os.environ["FAKE_PID_LOG"] = str(HOME / "pids-t4.txt")
door4 = fresh_door("t4")
r4 = call(door4, action="run", graph=G)
rid4 = r4.get("run_id"); check("T4: run launches", bool(rid4), r4)
st5 = call(door4, action="wait", run_id=rid4, timeout=90)
check("T4: held at g1", st5.get("status") == "held", st5.get("status"))
rel4 = call(door4, action="release", run_id=rid4, gate_id="g1", answer="yes")
check("T4: normal release byte-identical incl auto_resumed", rel4.get("ok") and rel4.get("auto_resumed"), rel4)
st6 = call(door4, action="wait", run_id=rid4, timeout=90)
check("T4: run done, all 3 nodes", st6.get("status") == "done" and st6.get("done") == 3,
      json.dumps({k: st6.get(k) for k in ("status", "done", "total")}))
check("T4: no unconsumed residue on the clean path",
      not list((RUNS / rid4 / "gates").glob("*.unconsumed")))

print("RESULT " + ("ALL PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
