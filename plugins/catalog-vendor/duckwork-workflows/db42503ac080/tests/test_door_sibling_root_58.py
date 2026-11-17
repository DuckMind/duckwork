#!/usr/bin/env python3
"""#58 (door/sibling-root scan for status+wait): a LIVE run must never answer
`unknown run_id` just because the consumer's env resolves a different home.

Issue shape (quartermaster's graph-admission walk, 2026-09-30): dispatch via the
door under DUCKWORK_HOME=profiles/<seat> (the run lands profile-root), then `wait`
from a process whose env resolves the SHARED root -> `unknown run_id` while the
run dir and its events.jsonl are demonstrably alive next door. find_run covers
resolved-root + legacy launch root only; a profile-scoped consumer sees neither.

Fix contract being pinned (issue #58):
  1. status/wait scan the sibling known roots (estate shared root + every
     profile root under the same Duckwork root) BEFORE answering unknown, and
     answer from the hit with a `resolved_via` warning field;
  2. READ paths only — write verbs (amend/release/steer/stop) stay fail-closed
     on the resolved root;
  3. a sibling-resolved wait never spawns a runner from the foreign root;
  4. same-root behavior byte-identical: no resolved_via field, unknown stays
     unknown for a run that exists nowhere.
"""
import importlib.util, json, os, shutil, sys, time
from pathlib import Path

BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
ROOT = BUILD.parent
BASE = BUILD / "home58"
SEAT = BASE / "profiles" / "seat"
shutil.rmtree(BASE, ignore_errors=True)
(BASE / "workflows").mkdir(parents=True)
(SEAT / "workflows").mkdir(parents=True)
(BASE / "config.yaml").write_text("model:\n  default: q\n")
(SEAT / "config.yaml").write_text("model:\n  default: q\n")

os.environ.pop("WF_RUNS_ROOT", None)
os.environ["DUCKWORK_HOME"] = str(SEAT)               # dispatch-side seat view
os.environ["WF_RUNS_ROOT"] = str(SEAT / "workflows")  # #71 r5 env pin — the SAME
                                                     # scratch root DUCKWORK_HOME
                                                     # derives (the pop was a
                                                     # cleanliness step; equal
                                                     # values, pinned)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
FAKE_LOG = BUILD / "fake58.log"
os.environ["FAKE_LOG"] = str(FAKE_LOG)
if FAKE_LOG.exists():
    FAKE_LOG.unlink()
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("hw58", ROOT / "__init__.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  [{detail}]"))
    fails += 0 if cond else 1

def call(**a):
    return json.loads(hw.handle(a))

G = {"name": "sib58", "nodes": [{"id": "a", "type": "agent", "goal": "SLEEP 3 task a"}]}

# ---- 1. same-root baseline: no resolved_via anywhere (byte-identical law) ----
r = call(action="run", graph=G, name="sib58-same")
rid_same = r.get("run_id")
check("S1 same-root run launches", bool(rid_same), json.dumps(r))
check("S1b run dir is under the seat root", (SEAT / "workflows" / rid_same).is_dir())
st = call(action="wait", run_id=rid_same, timeout=60)
check("S2 same-root wait lands done", st.get("status") == "done", json.dumps({k: st.get(k) for k in ("status", "error")}))
check("S2b no resolved_via on a same-root read", "resolved_via" not in st, json.dumps(st.get("resolved_via")))
st = call(action="status", run_id=rid_same)
check("S2c no resolved_via on a same-root status", st.get("status") == "done" and "resolved_via" not in st)

# ---- 2. THE REPRO: dispatch under the seat root, read from the shared root ----
r = call(action="run", graph=G, name="sib58-sibling")
rid = r.get("run_id")
check("X1 sibling run launches", bool(rid), json.dumps(r))
check("X1b run lives under the SEAT root", (SEAT / "workflows" / rid / "graph.json").exists())
# deterministic baseline: let the DISPATCH runner's own child land in the log first
def _log_lines():
    return FAKE_LOG.read_text().count("\n") if FAKE_LOG.exists() else 0
_base = _log_lines()
for _ in range(100):                       # up to ~10 s for the runner's first spawn
    if _log_lines() > _base:
        break
    time.sleep(0.1)
spawns_before = _log_lines()
check("X2 precondition: the run's child was spawned by the dispatch-side runner",
      spawns_before > _base, f"{_base} -> {spawns_before}")

os.environ["DUCKWORK_HOME"] = str(BASE)               # consumer whose env resolves the shared root
os.environ["WF_RUNS_ROOT"] = str(BASE / "workflows")  # #71 r5: flip the env pin WITH
                                                     # the home (iso71 keeps the
                                                     # settings pin locked to this)
check("X2b precondition: resolved root has no such run dir", not (BASE / "workflows" / rid).exists())

st = call(action="status", run_id=rid)
check("X3 status resolves the sibling run (no unknown)", "error" not in st,
      json.dumps(st))
check("X3b status carries resolved_via naming the foreign root",
      st.get("resolved_via") == str(SEAT / "workflows" / rid), json.dumps(st.get("resolved_via")))

# deterministic spawn-guard case: an INTERRUPTED sibling run (no runner) — a local
# wait would respawn; the foreign read-only wait must not.
ORPHAN = BASE / "profiles" / "orphan-seat" / "workflows" / "orphan58"
(ORPHAN / "nodes").mkdir(parents=True)
(ORPHAN / "graph.json").write_text(json.dumps(
    {"name": "orphan", "nodes": [{"id": "a", "type": "agent", "goal": "SLEEP 3"}]}))
(ORPHAN / "run.json").write_text(json.dumps({"name": "orphan"}))
g = call(action="wait", run_id="orphan58", timeout=5)
check("X3c foreign wait on an ownerless run never spawns",
      g.get("status") in ("pending", "interrupted") and g.get("resolved_via") == str(ORPHAN)
      and _log_lines() == spawns_before,
      json.dumps({k: g.get(k) for k in ("status", "error", "resolved_via")}))

w = call(action="wait", run_id=rid, timeout=60)
check("X4 wait resolves the sibling run (no unknown run_id)", w.get("status") == "done" and "error" not in w,
      json.dumps({k: w.get(k) for k in ("status", "error", "note")}))
check("X4b wait carries resolved_via", w.get("resolved_via") == str(SEAT / "workflows" / rid),
      json.dumps(w.get("resolved_via")))
spawns_after = _log_lines()
check("X5 foreign-root wait spawned NO runner child", spawns_after == spawns_before,
      f"{spawns_before} -> {spawns_after}")
check("X5b foreign-root wait created no run dir under the consumer root",
      not (BASE / "workflows" / rid).exists())

# ---- 3. write paths stay fail-closed on the resolved root ----
am = call(action="amend", run_id=rid, graph={"name": "sib58-sibling",
                                             "nodes": [{"id": "a", "type": "agent", "goal": "SLEEP 3 v2"}]})
check("W1 amend stays fail-closed from the foreign root", "unknown run_id" in json.dumps(am), json.dumps(am))
rel = call(action="release", run_id=rid, gate_id="g", answer="y")
check("W2 release stays fail-closed from the foreign root", "unknown run_id" in json.dumps(rel), json.dumps(rel))
stp = call(action="stop", run_id=rid)
check("W3 stop stays fail-closed from the foreign root", "unknown run_id" in json.dumps(stp), json.dumps(stp))

# ---- 4. honest unknown: a run that exists in NO root ----
g = call(action="wait", run_id="ghost58-does-not-exist", timeout=5)
check("U1 ghost wait still unknown", "unknown run_id" in json.dumps(g), json.dumps(g))
check("U1b ghost wait has no resolved_via", "resolved_via" not in g)
g = call(action="status", run_id="ghost58-does-not-exist")
check("U2 ghost status still errors", "error" in g and "resolved_via" not in g, json.dumps(g))

# ---- 5. traversal law preserved on the read path ----
g = call(action="status", run_id="../evil")
check("T1 invalid run_id still rejected on status", "invalid run_id" in json.dumps(g), json.dumps(g))

print("ALL PASS" if not fails else f"{fails} FAILURES PRESENT")
sys.exit(0 if not fails else 1)
