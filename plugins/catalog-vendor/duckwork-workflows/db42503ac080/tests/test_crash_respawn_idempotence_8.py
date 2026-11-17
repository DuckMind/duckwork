#!/usr/bin/env python3
"""#8 fix-law item 3 — crash-respawn idempotence (attempt-N preamble +
reconcile-don't-redo), per the maintainer incident-class-split comment on #8
(STILL OPEN item 3: 'Idempotence (#8 fix-law item 3: attempt-N preamble +
reconcile-don't-redo on crash-respawn) — not in this diff').

A blind ladder respawn over uncounted prior generations re-runs side effects
(the firehose shape: a respawned build lane pushes the branch / opens the PR a
second time). The respawned runner must:
  (a) write an attempt-N PREAMBLE RECORD when it boots over a run whose prior
      runner died (events.jsonl already exists — the resume path);
  (b) RECONCILE the committed side-effect records (the run-dir journal
      side_effects.jsonl) against the current graph — a row whose node is
      gone or amended (efp mismatch) is orphaned/stale, never a fact;
  (c) NOT re-execute already-completed side effects: every respawned spawn
      carries a machine preamble naming the committed effects so the child
      reconciles instead of redoing (same prompt-side law as lane hygiene),
      and the external ledger (FAKE_EFFECT_FILE) gains exactly ONE line for
      an effect committed before the crash.

The child side writes its journal row through the env pin the runner sets at
spawn (DUCKWORK_WF_EFFECTS_FILE, the SIDECAR-pin law); the test additionally
seeds the pin itself so the RED run is a pure engine-side red (no journal
writer, no preamble, effect re-executed twice).

Standalone, stdlib-only, estate shelf untouched:
  PYTHONPATH=<clone> python3 tests/test_crash_respawn_idempotence_8.py
"""
import json, os, shutil, signal, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE.parent)
HOME = HERE / "home-crashrespawn8"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(RUNS)
sys.path.insert(0, str(BUILD))

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

def spawn_wf(run_id, extra_env=None):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS),
               FAKE_LOG=str(HOME / ("fake_" + run_id + ".log")),
               DUCKWORK_WF_EFFECTS_FILE=str(RUNS / run_id / "side_effects.jsonl"),
               **(extra_env or {}))
    return subprocess.Popen([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)

def child_pids(run_id, log_name):
    """Pids the fake children appended to their FAKE_PID_LOG (one per spawn)."""
    p = HOME / log_name
    try:
        return [int(l) for l in p.read_text().split() if l.strip()]
    except (FileNotFoundError, ValueError):
        return []

def alive(pid):
    """Repo idiom (test_wfpid_owner_8): os.kill 0 + /proc state — a zombie the
    estate's subreaper ancestor has not waited yet is DEAD, not live."""
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    try:
        st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return not st.startswith("Z")
    except OSError:
        return True

def kill_tree(run_id, log_name):
    """SIGKILL the runner, then its recorded fake children (the child owns its
    pgid — start_new_session — so it SURVIVES the runner's death, which is
    exactly the crash-respawn shape the boot sweep must then handle)."""
    for pid in child_pids(run_id, log_name):
        if alive(pid):
            try: os.kill(pid, signal.SIGKILL)
            except OSError: pass

def events(r):
    try:
        return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
    except FileNotFoundError:
        return []

def wait_for(pred, timeout=40, tick=0.1):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(tick)
    return False

SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}
RUN_ID = "cr8-respawn"

shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()

# ---------------------------------------------------------------- seed a run
# node SEED executes an external side effect (one line into FAKE_EFFECT_FILE +
# one journal row into the effects file); node AFTER rides after it. FAKE_MODE
# effect_once honors the reconcile-don't-redo law: if the spawn's prompt names
# its key under the machine preamble's committed list, it does NOT redo it.
run = RUNS / RUN_ID
(run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
nodes = [
    {"id": "seed", "type": "agent", "goal": "side-effect work EFFECTKEY=EFF-A",
     "schema": SCHEMA},
    {"id": "after", "type": "agent", "goal": "follow-on work", "after": ["seed"],
     "schema": SCHEMA},
]
(run / "graph.json").write_text(json.dumps({"name": RUN_ID, "nodes": nodes}))
(run / "run.json").write_text(json.dumps(
    {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}))
effect_ledger = HOME / "effect_ledger.txt"          # the EXTERNAL effect ledger
prompt_ledger = HOME / "prompts.log"

base_env = {"FAKE_MODE": "effect_once",
            "FAKE_EFFECT_FILE": str(effect_ledger),
            "FAKE_EFFECT_HOLD": "1.2",              # stay alive so we can crash mid-attempt
            "FAKE_PID_LOG": str(HOME / "pids_cr8-respawn.txt"),
            "FAKE_PROMPT_LOG": str(prompt_ledger)}

# ---- attempt 1: crash the runner AFTER the side effect is committed ----
p1 = spawn_wf(RUN_ID, base_env)
if not wait_for(lambda: effect_ledger.exists() and (run / "nodes" / "seed.json").exists(), 30):
    p1.kill(); p1.wait(); kill_tree(RUN_ID, "pids_cr8-respawn.txt")
    check("1 setup: seed committed its effect journal record", False, "never appeared")
    print("RESULT FAIL (setup)"); sys.exit(1)
# the effect row + journal row landed but the node has NOT committed (fake is
# holding its answer); SIGKILL the runner: the exact crash-respawn shape.
os.kill(p1.pid, signal.SIGKILL)
p1.wait()
seed_rec_1 = json.loads((run / "nodes" / "seed.json").read_text())
check("1 setup: crash left the spawn record non-terminal (status=running)",
      seed_rec_1.get("status") == "running", str(seed_rec_1.get("status")))
check("1 setup: the side effect committed exactly once before the crash",
      len(effect_ledger.read_text().splitlines()) == 1, effect_ledger.read_text())
# the crashed attempt's child owns its own pgid and outlived the runner. Kill
# it dead and prove death BEFORE the respawn, so the boot starts from a
# proven-dead tree (the #61c quarantine law, exercised by its own suite, is
# not what we test here) and no re-drive races the ledger read below.
wait_for(lambda: len(child_pids(RUN_ID, "pids_cr8-respawn.txt")) >= 1, 5)
kill_tree(RUN_ID, "pids_cr8-respawn.txt")
check("1 setup: the crashed attempt's child proven dead before respawn",
      wait_for(lambda: not any(alive(p) for p in child_pids(RUN_ID, "pids_cr8-respawn.txt")), 10))

# ---- attempt 2: respawn over the dead runner (the reaper's revival) ----
p2 = spawn_wf(RUN_ID, base_env)
out2, _ = p2.communicate(timeout=90)
evs = events(run)

# (a) attempt-N preamble RECORD on the respawn boot
pre = [e for e in evs if e.get("event") == "runner.attempt_preamble"]
check("a respawn boot wrote an attempt-N preamble record",
      len(pre) >= 1 and pre[-1].get("attempt") == 2,
      json.dumps(pre[-1] if pre else {})[:160])

# (b) reconcile of the committed side-effect records against the graph
rec_ev = [e for e in evs if e.get("event") == "run.respawn_reconcile"]
check("b respawn reconciled the committed side-effect records (1 reconciled, 0 orphaned)",
      len(rec_ev) == 1 and rec_ev[0].get("reconciled") == 1
      and rec_ev[0].get("orphaned") == 0,
      json.dumps(rec_ev[0] if rec_ev else {})[:200])
# reconcile verdict is a durable record, not just an event
rc = run / "side_effects.reconcile.json"
check("b the reconcile verdict is durable (side_effects.reconcile.json)",
      rc.exists() and json.loads(rc.read_text()).get("reconciled") == 1,
      rc.read_text()[:160] if rc.exists() else "<missing>")

# (c) reconcile-don't-redo: the effect ran EXACTLY once across the crash
lines = effect_ledger.read_text().splitlines()
check("c the committed side effect was NOT re-executed by the respawn (one ledger line)",
      lines == ["EFF-A"], repr(lines))
check("c the journal still carries exactly one row for the effect",
      len([json.loads(l) for l in (run / "side_effects.jsonl").read_text().splitlines()
           if l.strip()]) == 1, (run / "side_effects.jsonl").read_text()[:200])
# the respawned spawn SAW the committed-effect inventory (that is how (c) holds)
prompt2 = [b for b in prompt_ledger.read_text().split("\n=====PROMPT=====\n")
           if "EFFECTKEY=EFF-A" in b]
check("c the respawned seed spawn carried the machine preamble naming key=EFF-A",
      any("Already committed side effects" in b and "key=EFF-A" in b for b in prompt2),
      (prompt2[-1][:200] if prompt2 else "<no prompts>"))
# and the first (pre-crash) spawn carried NO committed-effects preamble
check("c the first attempt carried no committed-effects preamble (nothing committed yet)",
      len(prompt2) == 2 and "Already committed side effects" not in prompt2[0],
      f"{len(prompt2)} seed prompts")

# the run must still close done
rec2 = json.loads((run / "nodes" / "seed.json").read_text())
check("run closed done after the respawn (seed committed)",
      rec2.get("status") == "done", str(rec2)[:160])
check("run closed done (after node)",
      (run / "nodes" / "after.json").exists()
      and json.loads((run / "nodes" / "after.json").read_text()).get("status") == "done")
check("second runner exited 0", p2.returncode == 0, f"rc={p2.returncode} {out2[-200:]}")

# ---------------------------------------------------------------- unit: (b)
# stale rows (amended node / unknown node) reconcile as orphans, never facts.
import importlib.util
spec = importlib.util.spec_from_file_location("wf_cr8", str(BUILD / "wf.py"))
wf = importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)
u = RUNS / "cr8-unit"
shutil.rmtree(u, ignore_errors=True)
(u / "nodes").mkdir(parents=True); (u / "gates").mkdir()
un = [{"id": "n1", "type": "agent", "goal": "g1", "schema": SCHEMA},
      {"id": "n2", "type": "agent", "goal": "g2", "after": ["n1"], "schema": SCHEMA}]
(u / "graph.json").write_text(json.dumps({"name": "cr8-unit", "nodes": un}))
from wfcommon import efp, FP_RULE_VERSION
byid = {n["id"]: n for n in un}
(u / "nodes" / "n1.json").write_text(json.dumps(   # committed fact for n1
    {"status": "done", "output": {"result": "ok"},
     "efp": efp(byid, byid["n1"]), "fp_rule_version": FP_RULE_VERSION}))
(u / "side_effects.jsonl").write_text("\n".join([
    json.dumps({"node": "n1", "kind": "push", "key": "K1", "evidence": "sha", "spawn": 0,
                "node_efp": efp(byid, byid["n1"])}),
    json.dumps({"node": "ghost", "kind": "pr", "key": "K2", "evidence": "x", "spawn": 0}),
]) + "\n")
verd = wf.reconcile_effects(u, byid)
check("b unit: live row reconciles, ghost node orphans",
      verd.get("reconciled") == 1 and verd.get("orphaned") == 1, json.dumps(verd)[:200])
# an amended n1 (efp mismatch) makes its row stale, never a committed fact
un[0]["goal"] = "g1 amended"
byid2 = {n["id"]: n for n in un}
verd2 = wf.reconcile_effects(u, byid2)
check("b unit: amended node -> row is stale/orphaned, never a fact",
      verd2.get("reconciled") == 0 and verd2.get("orphaned") == 2, json.dumps(verd2)[:200])
# a torn line (writer mid-append) is skipped, never a crash and never a fact
(u / "side_effects.jsonl").write_text(
    json.dumps({"node": "n1", "kind": "push", "key": "K1", "evidence": "s", "spawn": 0,
                "node_efp": efp(byid, byid["n1"])})
    + "\n{\"node\": \"n1\", \"kind\": \"push\", \"key\": \"TOR")
verd3 = wf.reconcile_effects(u, byid)
check("b unit: torn journal line skipped (1 reconciled, 0 orphaned), no raise",
      verd3.get("reconciled") == 1 and verd3.get("orphaned") == 0, json.dumps(verd3)[:200])

print(("RESULT PASS" if ok else "RESULT FAIL"))
sys.exit(0 if ok else 1)
