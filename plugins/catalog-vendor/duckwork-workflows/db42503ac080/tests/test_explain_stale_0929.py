"""why-rerun (jam-h27) acceptance: wfcommon.explain_stale — one-line 'why is this
committed node re-running' verdict for an efp-stale node, attributed to the
earliest amend that changed the nearest changed ancestor, plus the
stale_because surfacing in node_facts and the door's status payload.

Hand-built run dir (records stamped the way wf.py's save_node commits them).
Stdlib only; the door is loaded with child_metrics stubbed so the gate needs
no state.db and no HTTP client."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

HOME = Path(tempfile.mkdtemp(prefix="home-why-rerun-", dir=str(ROOT)))
os.environ["DUCKWORK_HOME"] = str(HOME)
R = HOME / "workflows" / "why-rerun"
(R / "nodes").mkdir(parents=True)

ok = 0
def check(cond, msg, extra=None):
    global ok
    assert cond, msg + (" | " + str(extra) if extra else "")
    ok += 1; print("PASS", msg)

BASE = {"name": "why", "nodes": [
    {"id": "a", "type": "agent", "goal": "recon"},
    {"id": "b", "type": "agent", "goal": "build", "after": ["a"]},
    {"id": "c", "type": "agent", "goal": "review", "after": ["b"]}]}
byid = {n["id"]: n for n in BASE["nodes"]}

def put(recname, nid, node):
    """Commit nodes/<recname>.json the way wf.py save_node does."""
    (R / "nodes" / f"{recname}.json").write_text(json.dumps(
        {"status": "done", "output": {"r": 1},
         "efp": wfcommon.efp(byid, node), "fp_rule_version": wfcommon.FP_RULE_VERSION}))

def fresh():
    import shutil
    if R.exists():
        shutil.rmtree(R)
    (R / "nodes").mkdir(parents=True)
    (R / "graph.json").write_text(json.dumps(BASE))
    for nid in ("a", "b", "c"):
        put(nid, nid, byid[nid])

def amend(old_graph, new_graph, at):
    with (R / "amends.jsonl").open("a") as f:
        f.write(json.dumps({"at": at, "old": old_graph, "new": new_graph}) + "\n")

# ---------- 1: amended ancestor -> one-line verdict attributing the ancestor ----------
fresh()
newG = json.loads(json.dumps(BASE))
next(n for n in newG["nodes"] if n["id"] == "b")["goal"] = "build DIFFERENT"
amend(BASE, newG, "2026-09-29T10:00:00+00:00")
(R / "graph.json").write_text(json.dumps(newG))
new_byid = {n["id"]: n for n in newG["nodes"]}
verdict = wfcommon.explain_stale(R, "c")
check(verdict == "stale because b: goal changed at 2026-09-29T10:00:00+00:00",
      "ancestor attribution: c's staleness names b's goal change + amend ts", verdict)
check(wfcommon.explain_stale(R, "b") == verdict,
      "the amended node itself reports its own field change", wfcommon.explain_stale(R, "b"))
check(wfcommon.explain_stale(R, "a") is None,
      "a still-valid committed record is never explained (None)")
nf = wfcommon.node_facts(R, "c")
check(isinstance(nf, dict) and nf.get("stale_because") == verdict,
      "node_facts carries stale_because beside the efp hex", nf and nf.get("stale_because"))
nf_a = wfcommon.node_facts(R, "a")
check(isinstance(nf_a, dict) and "stale_because" not in nf_a,
      "node_facts on a CURRENT record ships no stale_because (byte-identical)")

# ---------- 2: definition drift (graph moved, no amend on record) ----------
fresh()
drift = json.loads(json.dumps(BASE))
next(n for n in drift["nodes"] if n["id"] == "a")["goal"] = "recon EDITED BY HAND"
(R / "graph.json").write_text(json.dumps(drift))
check(wfcommon.explain_stale(R, "c") == "stale: definition drift (no amend on record)",
      "no amend matching the mismatch = definition drift", wfcommon.explain_stale(R, "c"))

# ---------- 3: budget-only amend is NOT work (replay-skip law mirrored) ----------
fresh()
budg = json.loads(json.dumps(BASE))
next(n for n in budg["nodes"] if n["id"] == "b")["max_turns"] = 190
amend(BASE, budg, "2026-09-29T11:00:00+00:00")
(R / "graph.json").write_text(json.dumps(budg))
check(wfcommon.explain_stale(R, "c") is None,
      "budget-only amend keeps records valid — nothing to explain")

# ---------- 4: earliest matching amend wins, attribution skips later noise ----------
fresh()
g1 = json.loads(json.dumps(BASE))
next(n for n in g1["nodes"] if n["id"] == "b")["goal"] = "build v2"
g2 = json.loads(json.dumps(g1))
next(n for n in g2["nodes"] if n["id"] == "a")["context"] = "extra preamble"
amend(BASE, g1, "2026-09-29T09:00:00+00:00")
amend(g1, g2, "2026-09-29T09:30:00+00:00")   # c's commit predates neither? it predates both
(R / "graph.json").write_text(json.dumps(g2))
v2 = wfcommon.explain_stale(R, "c")
check(v2 == "stale because b: goal changed at 2026-09-29T09:00:00+00:00",
      "earliest amend that the commit predates wins (nearest chain first, then amend order)", v2)

# ---------- 5: fan-out item record resolves through its parent def ----------
fresh()
newG = json.loads(json.dumps(BASE))
next(n for n in newG["nodes"] if n["id"] == "b")["goal"] = "build OTHER"
amend(BASE, newG, "2026-09-29T12:00:00+00:00")
(R / "graph.json").write_text(json.dumps(newG))
put("c.0", "c", byid["c"])   # item record, parent def
check(wfcommon.explain_stale(R, "c", 0)
      == "stale because b: goal changed at 2026-09-29T12:00:00+00:00",
      "fan-out item record gets the verdict via its parent node def",
      wfcommon.explain_stale(R, "c", 0))

# ---------- 6: door status payload carries stale_because (child_metrics stubbed) ----------
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
door = load("why_rerun_door", ROOT / "__init__.py")
door._common.child_metrics = lambda run_id, home=None: {}   # no state.db in the gate
(R / "run.json").write_text(json.dumps({"name": "why", "duckwork_bin": "/bin/true"}))
st = door.act_status({"run_id": "why-rerun"})
check(st["nodes"]["c"].get("status") == "pending"
      and st["nodes"]["c"].get("stale_because", "").startswith("stale because b:"),
      "status payload: efp-stale pending node ships stale_because", st["nodes"]["c"])
check("stale_because" not in st["nodes"]["a"],
      "status payload: a still-valid node ships no stale_because", st["nodes"]["a"])

print(f"\n{ok} checks passed")
