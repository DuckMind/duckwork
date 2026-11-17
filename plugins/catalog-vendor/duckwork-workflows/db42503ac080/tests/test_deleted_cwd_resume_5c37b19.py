#!/usr/bin/env python3
"""5c37b19 — deleted-cwd runner killers (fb 5c37b19109179eab, run 20260926-061429).

One family: the runner must DEGRADE, not die ENOENT, when a directory it writes
to is gone mid-flight.
 1. _resume_preamble survives a deleted runner cwd (guard 1 — the bare
    Path.cwd() killer on the bounded-retry re-drive; the solo path has no worker
    try/except, so pre-fix the raise escaped run_agent_node, passed the loop's
    ex.map and died in the __main__ BaseException net: runner_exit
    'crashed: FileNotFoundError').
 2. End-to-end shape of that death: solo agent node dies once transport-with-
    tool-progress (fake 'retry_progress'), the runner's cwd is rmdir'd DURING
    the 5 s bounded-retry backoff — the re-drive's _resume_preamble runs with a
    live-deleted cwd. Post-fix the runner survives (rc 0) and the re-drive
    lands. Per the check's refutation the node assertion is done-or-failed
    (run_agent_node never raises); the hard assertions are runner-survival and
    no 'crashed: FileNotFoundError'.
 3. __main__ startup self-recovery (guard 2): launched FROM a deleted dir, the
    runner chdirs to HERE (durable — the dir __init__.py pins as the spawn cwd)
    and reaches its normal verdict instead of dying with FileNotFoundError.
 4. THE OBSERVED KILLER (run 20260926-061429 runner.log): the when-skip write
    into a gates/ subtree deleted mid-loop. Deterministic shape: a seeded-answer
    human gate short-circuits the hold, the loop reaches the when-false skip
    while a patched when_true rmtree's <run>/gates at the exact moment — pre-fix
    FileNotFoundError killed loop() -> main() -> the runner; the mkdir-before-
    write fix recreates gates/ + gates/<id>.json and the run closes done.

Run: python3 tests/test_deleted_cwd_resume_5c37b19.py   (exit 0 = green)
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import json, os, shutil, subprocess, sys, time, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent                                  # source of record: wf.py lives here
HOME = HERE / "home5c37"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def load_wf(name):
    spec = importlib.util.spec_from_file_location(name, str(BUILD / "wf.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def mk(run_id, nodes, gates_seed=None, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}; m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    for gid, ans in (gates_seed or {}).items():     # efp-stamped machine answer
        byid = {n["id"]: n for n in nodes}
        (r / "gates" / f"{gid}.json").write_text(
            json.dumps({"answer": ans, "_def": wfcommon.efp(byid, byid[gid]), "fp_rule_version": wfcommon.FP_RULE_VERSION}))
    return r

def spawn_wf(run_id, extra_env=None, cwd=None):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / ("fake_" + run_id + ".log")), **(extra_env or {}))
    return subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=(str(cwd) if cwd else None))

def rec_of(r, nid):
    return json.loads((r / "nodes" / f"{nid}.json").read_text())

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

def runner_exit_of(r):
    p = r / "runner_exit.json"
    return json.loads(p.read_text()) if p.exists() else None

def spawns_of(r):
    return len(list((r / "logs").glob("*.log")))

def wait_for(pred, timeout=30, tick=0.1):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(tick)
    return False

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

# ---- 1: _resume_preamble survives a deleted cwd (guard 1, unit) ---------------
wfmod = load_wf("wf_under_test_5c37b19")
dead1 = HOME / "dying1"; shutil.rmtree(dead1, ignore_errors=True); dead1.mkdir()
os.chdir(dead1); dead1.rmdir()
try:
    pre = wfmod._resume_preamble({"status": "failed", "error_class": "transport",
                                  "final": "line1\nline2", "skey": "s", "raw": ""})
    raised = None
except FileNotFoundError as e:
    pre, raised = None, e
finally:
    os.chdir(HOME)
check("1 _resume_preamble returns under a deleted cwd (no FileNotFoundError)",
      raised is None, f"{type(raised).__name__}: {raised}" if raised else "")
check("1 preamble still carries error_class + death tail + RESUME_LINE",
      pre is not None and "error_class=transport" in pre
      and wfmod.RESUME_LINE in pre and "line2" in pre, str(pre)[:120])

# ---- 2: solo bounded-retry re-drive does not kill the runner (e2e, guard 1) ----
# The cwd goes AFTER startup (guard 2 must NOT fire) and BEFORE the re-drive:
# the fake's first attempt dies transport with tool progress, the bounded retry
# backs off 5 s — the rmdir lands inside that window, so _resume_preamble runs
# with a live-deleted cwd. Pre-fix: FileNotFoundError escaped run_agent_node,
# the __main__ net wrote 'crashed: FileNotFoundError' and rc != 0.
r = mk("t2-solo-redrive", [{"id": "a", "type": "agent", "goal": "RESUME t2-solo-redrive",
                            "schema": SCHEMA}])
shutil.rmtree(HOME / "att_t2", ignore_errors=True)
gone2 = HOME / "gone2"; shutil.rmtree(gone2, ignore_errors=True); gone2.mkdir()
p2 = spawn_wf("t2-solo-redrive", {"FAKE_MODE": "retry_progress",
                                  "FAKE_ATTEMPT_DIR": str(HOME / "att_t2")}, cwd=gone2)
started = wait_for(lambda: any(e.get("event") == "node.started" for e in events(r)), timeout=25)
check("2 runner booted and started the node (precondition)", started)
gone2.rmdir()                                        # runner's cwd now deleted
out2 = p2.communicate(timeout=120)[0].strip()
re2 = rec_of(r, "a")
exit2 = runner_exit_of(r)
check("2 runner process SURVIVES the re-drive from a deleted cwd (rc 0)",
      p2.returncode == 0, f"rc={p2.returncode} out={out2[-200:]} exit={exit2}")
check("2 node reaches done (re-drive landed) — never drags the runner down",
      re2["status"] == "done" and (re2.get("output") or {}).get("result") == "resumed",
      str(re2)[:200])
check("2 exactly one re-drive (2 spawns)", spawns_of(r) == 2, f"spawns={spawns_of(r)}")
check("2 no runner_exit 'crashed: FileNotFoundError'",
      exit2 is None or "FileNotFoundError" not in (exit2.get("reason") or ""),
      str(exit2)[:200])
check("2 the re-drive logged node.retry (resume really went through the guard)",
      any(e.get("event") == "node.retry" for e in events(r)))

# ---- 3: __main__ startup self-recovery (guard 2) ------------------------------
r = mk("t3-startup", [{"id": "a", "type": "agent", "goal": "PLAIN SLEEP 2 t3-startup"}])
gone3 = HOME / "gone3"; shutil.rmtree(gone3, ignore_errors=True); gone3.mkdir()
p3 = spawn_wf("t3-startup", cwd=gone3)
gone3.rmdir()                                        # gone BEFORE python exec's
cwd_seen = set()
deadline = time.time() + 15
while time.time() < deadline:
    try:
        cwd_seen.add(os.readlink(f"/proc/{p3.pid}/cwd"))
    except OSError:
        pass
    if p3.poll() is not None and cwd_seen:
        break
    time.sleep(0.05)
out3 = p3.communicate(timeout=120)[0].strip()
check("3 runner launched FROM a deleted dir survives to its normal verdict (rc 0)",
      p3.returncode == 0 and out3.startswith("WORKFLOW_DONE t3-startup"),
      f"rc={p3.returncode} out={out3[-200:]}")
check("3 recovered into the durable plugin dir (/proc/<pid>/cwd == HERE)",
      str(BUILD) in cwd_seen, str(sorted(cwd_seen))[:200])
check("3 node reaches done", rec_of(r, "a")["status"] == "done", str(rec_of(r, "a"))[:160])

# ---- 4: THE OBSERVED KILLER — when-skip write recreates a deleted gates/ -------
# Deterministic shape of the run-20260926-061429 crash (verdict 'blocked', the
# go-gate's when wants 'ready'): a seeded answer short-circuits the human hold,
# the loop reaches the when-false skip while a patched when_true rmtree's
# <run>/gates at the exact moment BEFORE the skip write. In-process main() so
# the crash (pre-fix) lands here as an exception, not hidden by the __main__ net.
r = mk("t4b-whenskip",
       [{"id": "judge", "type": "agent", "goal": "JSON:{\"verdict\": \"blocked\"}"},
        {"id": "g", "type": "gate", "after": ["judge"], "question": "go?", "options": ["yes"]},
        {"id": "go", "type": "gate", "after": ["judge"],
         "when": "out.judge.verdict == 'ready'", "on_skip": "prune"}],
       gates_seed={"g": "yes"})
wf4 = load_wf("wf_under_test_5c37b19_t4b")
real_when_true = wf4.when_true
deleted = []
def when_true_then_delete(gate, outputs):
    if gate.get("id") == "go" and not deleted:
        deleted.append(True)
        shutil.rmtree(r / "gates", ignore_errors=True)   # mid-loop subtree deletion
    return real_when_true(gate, outputs)
wf4.when_true = when_true_then_delete
try:
    reason4 = wf4.main("t4b-whenskip")
    crash4 = None
except BaseException as e:
    reason4, crash4 = None, e
check("4 precondition: the mid-loop delete really fired", deleted == [True])
check("4 when-skip write survives a deleted gates/ — main() returns 'done', no raise "
      "(pre-fix: FileNotFoundError killed loop() -> main(), the observed runner death)",
      crash4 is None and reason4 == "done",
      f"{type(crash4).__name__}: {crash4}" if crash4 else f"reason={reason4}")
gp = r / "gates" / "go.json"
check("4 gates/ + gates/go.json RECREATED with the skip record",
      (r / "gates").is_dir() and gp.exists()
      and json.loads(gp.read_text()).get("gate") == "skipped",
      str(gp.read_text() if gp.exists() else None)[:160])
check("4 when-false gate node committed (on_skip prune -> skipped), not failed",
      rec_of(r, "go")["status"] == "skipped", str(rec_of(r, "go"))[:160])
check("4 runner_exit is not a crash — the verdict is 'done'",
      (runner_exit_of(r) or {}).get("reason") == "done", str(runner_exit_of(r))[:200])
check("4 run closed done (events)",
      any(e.get("event") == "run.done" for e in events(r)))

print("ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
