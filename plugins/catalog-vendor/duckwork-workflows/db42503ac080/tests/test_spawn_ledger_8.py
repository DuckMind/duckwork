#!/usr/bin/env python3
"""#8 (P0, remaining half): the admitted runner registers its spawn tree in
<run>/spawn-ledger.jsonl so an EXTERNAL reaper can see what a workflow child is.

Issue item 1's observable half: runner + children vanish under an out-of-band
process sweep because nothing legible says "this pid is a workflow runner /
workflow child — reapers must not kill it". The plugin cannot change core's
process_registry (outside this repo); it CAN make the tree legible: every
admitted runner appends a `role:runner` row right after its own ready_stamp
(SOLE-OWNER stamp law — the door never writes ownership, so the door writes
this file NEVER), every spawn-recorded child appends a `role:child` row
(node/index/skey/pid), and each child's judgment closes it with `role:child_end`.

Rows: {ts, pid, role: runner|child|child_end, node, index, skey, purpose:
'workflow-runner'}. Append-only, best-effort: a ledger failure never touches a
spawn (same never-fatal law as the reaper's log match).

RED on origin/main: the file is never written — every check below that reads
spawn-ledger.jsonl fails (missing file / no rows).
"""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

HOME = Path(tempfile.mkdtemp(prefix="wf-ledger8-", dir=ROOT / "tests"))
RUNS = HOME / "workflows"
RUNS.mkdir(parents=True)
FAKE = str(ROOT / "tests" / "fake")
ok = True
check_count = 0
fail_count = 0

def check(label, cond, detail=""):
    global check_count, fail_count
    check_count += 1
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        fail_count += 1
        ok = False

def load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
os.environ["WF_RUNS_ROOT"] = str(RUNS)   # #71 r5 env pin
door = load("ledger8_door", ROOT / "__init__.py")
import wf_test_isolation as _iso71_ledger8
_iso71_ledger8.install(door)             # #71 r5: pin settings.runs_root too

run_id = "t-ledger-8"
r = RUNS / run_id
r.mkdir(parents=True)
(r / "nodes").mkdir()
(r / "gates").mkdir()
items = ["alpha", "beta"]
graph = {"name": run_id, "nodes": [
    {"id": "fan", "type": "agent",
     "fanout": {"items": items, "goal": "do the thing for {item}"}}]}
(r / "graph.json").write_text(json.dumps(graph))
(r / "run.json").write_text(json.dumps({"duckwork_bin": FAKE, "concurrency": 1,
                                        "node_timeout": 60}))

ledger = r / "spawn-ledger.jsonl"
pid_log = HOME / "fake_pids.log"
os.environ["FAKE_PID_LOG"] = str(pid_log)
os.environ["FAKE_LOG"] = str(HOME / "fake.log")

# door-side setup wrote NOTHING ownership-shaped: the ledger is the runner's
# alone (SOLE-OWNER stamp law — the door never writes wf.pid or the ledger).
check("door writes no spawn-ledger during setup", not ledger.exists())
check("door writes no wf.pid during setup", not (r / "wf.pid").exists())

env = dict(os.environ, DUCKWORK_WF_DUCKWORK_BIN=FAKE)
runner = subprocess.Popen([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                          env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)
try:
    out = runner.communicate(timeout=120)[0]
except subprocess.TimeoutExpired:
    runner.kill()
    out = runner.communicate(timeout=10)[0]
check("run completed", "WORKFLOW_DONE" in out, out.strip()[-300:])

rows = []
try:
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
except FileNotFoundError:
    check("spawn-ledger.jsonl exists after a real run", False, "file missing")
except OSError as exc:
    check("spawn-ledger.jsonl readable", False, repr(exc))

runner_rows = [x for x in rows if x.get("role") == "runner"]
child_rows = [x for x in rows if x.get("role") == "child"]
end_rows = [x for x in rows if x.get("role") == "child_end"]

if rows:
    check("every row carries the exemption purpose a reaper must honour",
          all(x.get("purpose") == "workflow-runner" for x in rows),
          json.dumps(rows[:2]))
    check("every row carries ts/pid/role",
          all(isinstance(x.get("ts"), str) and "pid" in x and "role" in x for x in rows),
          json.dumps(rows[:2]))

wfpid = int((r / "wf.pid").read_text())
check("exactly one runner row for the admitted runner",
      len(runner_rows) == 1, f"{len(runner_rows)} rows")
check("runner row: pid == wf.pid, purpose workflow-runner",
      bool(runner_rows) and runner_rows[0].get("pid") == wfpid
      and runner_rows[0].get("purpose") == "workflow-runner",
      json.dumps(runner_rows[:1]))

fake_pids = []
try:
    fake_pids = [int(l) for l in pid_log.read_text().split() if l.strip()]
except FileNotFoundError:
    pass
check("setup: fake children actually spawned (FAKE_PID_LOG)",
      len(fake_pids) >= len(items), f"{fake_pids}")
check("one child row per fanout spawn, each with node/index/skey/pid",
      len(child_rows) == len(items) and all(
          x.get("node") == "fan" and x.get("index") in (0, 1)
          and isinstance(x.get("skey"), str) and x.get("skey")
          and isinstance(x.get("pid"), int) for x in child_rows),
      json.dumps(child_rows))
check("child row pids are the actual fake-duckwork pids",
      sorted(x.get("pid") for x in child_rows) == sorted(fake_pids[:len(items)]),
      f"{sorted(x.get('pid') for x in child_rows)} vs {sorted(fake_pids)}")
check("every child row closed by a child_end row (same pid/skey)",
      len(end_rows) == len(child_rows) and
      {(x.get("pid"), x.get("skey")) for x in end_rows} ==
      {(x.get("pid"), x.get("skey")) for x in child_rows},
      json.dumps(end_rows))

# rows are append-ordered: the runner row precedes every child row (registration
# happens right after ready_stamp, before any spawn is recorded).
if rows and child_rows:
    check("registration order: runner row precedes every child row",
          rows.index(runner_rows[0]) < min(rows.index(x) for x in child_rows))

# ledger is additive only — the run's committed truths are untouched shapes:
check("node records still exist (ledger never replaced them)",
      any((r / "nodes").glob("fan*.json")))

shutil.rmtree(HOME, ignore_errors=True)
print(f"\n{check_count - fail_count}/{check_count} checks passed")
sys.exit(0 if fail_count == 0 else 1)
