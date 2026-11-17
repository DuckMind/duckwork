"""est-wr0p: validate_graph must reject a baked-empty literal fanout.items == [].

Class (est-077y vacuous replay): wfcommon's fanout block only rejected fanout
when `items` was None AND no items_from — a baked literal `items: []` passed
validation and the node committed with zero children: a vacuous pass, not a
fan-out. The runtime already fails `fanout resolved to no items`
(error_class fanout_empty) but the DOOR must refuse the shape at submit so
every consumer is safe, not just the QM admission gate
(scripts_curate/admission_check.py fanout_vacuous covers the shelf only).

Fix law: reject when isinstance(items, list) and len(items) == 0 with
"fanout.items must be a non-empty literal or use items_from". items_from
resolution stays untouched (dynamic count is unknown at admit).

Regression fixtures mirror the d5e-s4s6 preimages
(work/zap-build/wf-quartermaster/preimages/
 dual-adjudicator.json.d5e-s4s6-20261007T023830Z  -> node 'lanes' items:[]
 probe-verify-remediate.json.d5e-s4s6-20261007T023901Z -> probe/verify/remediate).

Runnable two ways (repo convention): `python3 tests/test_fanout_empty_items_0p.py`
prints PASS/FAIL lines, exit 0 = green; pytest can also collect test_*.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import wfcommon  # noqa: E402

FAILS = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)

def V(nodes):  # the SUBMIT-door rules (R10: admission=True is door-only)
    return wfcommon.validate_graph_errors(nodes, admission=True)
MSG = "fanout.items must be a non-empty literal or use items_from"

# 1. baked-empty literal rejected (the est-077y class)
g = [{"id": "lanes", "type": "agent", "goal": "g",
      "fanout": {"items": [], "goal": "attack {item} from your lens"}}]
errs = V(g)
check("items:[] rejected at the door",
      any(e["field"] == "fanout.items" and MSG in e["msg"] for e in errs), errs)

# 2. exact error text pinned (downstream tools match on it)
hits = [e for e in V(g) if e["field"] == "fanout.items"]
check("exact message verbatim",
      len(hits) == 1 and hits[0]["msg"] == MSG, hits)

# 3. items:[] WITH items_from still rejected — the runner takes the literal
#    (`items is None` gates the resolve_ref fallback) so a baked [] beside
#    items_from is the SAME vacuous class; the door refuses it too.
g3 = [{"id": "seed", "type": "agent", "goal": "emit items"},
      {"id": "lanes", "type": "agent", "after": ["seed"],
       "fanout": {"items": [], "items_from": "seed.items", "goal": "go {item}"}}]
errs3 = V(g3)
check("items:[] alongside items_from still rejected",
      any(e["field"] == "fanout.items" and MSG in e["msg"] for e in errs3), errs3)

# 4. items_from alone stays legal (dynamic count unknown at admit)
g4 = [{"id": "seed", "type": "agent", "goal": "emit items"},
      {"id": "lanes", "type": "agent", "after": ["seed"],
       "fanout": {"items_from": "seed.items", "goal": "go {item}"}}]
check("items_from alone not tripped", V(g4) == [], V(g4))

# 5. non-empty literal stays legal (no behavior change under the fix)
g5 = [{"id": "lanes", "type": "agent",
       "fanout": {"items": ["alpha", "beta"], "goal": "audit {item}"}}]
check("non-empty items not tripped", V(g5) == [], V(g5))

# 6. regression fixture mirroring preimage dual-adjudicator.json.d5e-s4s6
#    (node lanes: fanout.items=[], goal template present — the exact shipped shape)
dual = [{"id": "lanes", "type": "agent", "model": "seat", "max_turns": 40,
         "fanout": {"items": [],
                    "goal": "Attack DECISION_Q from your assigned lens."}},
        {"id": "adj_sol", "type": "agent", "after": ["lanes"],
         "goal": "INDEPENDENT adjudicator: rank the lane tables."}]
check("dual-adjudicator preimage shape rejected",
      any(e["node"] == "lanes" and MSG in e["msg"] for e in V(dual)), V(dual))

# 7. regression fixture mirroring preimage probe-verify-remediate.json.d5e-s4s6
#    (three baked-empty fan-out nodes: probe, verify, remediate — every one named)
pvr = [{"id": n, "type": "agent", "goal": "g",
        "fanout": {"items": [], "goal": "work {item}"}} for n in ("probe", "verify", "remediate")]
named = {e["node"] for e in V(pvr) if MSG in e["msg"]}
check("all three probe-verify-remediate nodes named",
      named == {"probe", "verify", "remediate"}, named)

# 8. R10 (PR #280 review): the guard is SUBMIT-door only. A persisted, in-flight
#    graph whose items:[] node was legitimately pruned must still be releasable
#    (__init__._release_core) and restartable (wf.py validate_graph seam).
#    Repro: echo go=false -> conditional gate on_skip=prune prunes the empty
#    fanout agent; an independent human gate is held and gets released.
import importlib.util, json, os, tempfile  # noqa: E402
PERSISTED = {"nodes": [
    {"id": "e", "type": "echo", "output": {"go": False}},
    {"id": "cond", "type": "gate", "after": ["e"], "when": "out.e.go",
     "on_skip": "prune", "wait": {"wait_s": 1}},
    {"id": "empty", "type": "agent", "after": ["cond"],
     "fanout": {"items": [], "goal": "work {item}"}},
    {"id": "human", "type": "gate", "question": "ship?", "options": ["yes", "no"]}]}
check("restart seam (wf.py validate_graph) accepts the persisted pruned graph",
      wfcommon.validate_graph(PERSISTED["nodes"]) is None,
      wfcommon.validate_graph(PERSISTED["nodes"]))
os.environ.setdefault("WF_RUNS_ROOT", tempfile.mkdtemp(prefix="wr0p-r10-"))
_spec = importlib.util.spec_from_file_location("door_wr0p", HERE.parent / "__init__.py")
door = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # noqa: E402  #71 pin
rd = Path(tempfile.mkdtemp(prefix="wr0p-run-"))
(rd / "graph.json").write_text(json.dumps(PERSISTED))
rel = door._release_core(rd, "human", "yes")
check("gate release on persisted pruned-empty run succeeds (R10)",
      rel.get("ok") is True and (rd / "gates" / "human.json").exists(), rel)
bad = door._validation_error(PERSISTED)
check("submit door still refuses the same graph as a NEW run",
      bool(bad) and MSG in json.dumps(bad), bad)

def test_fanout_empty_items_reject():
    """pytest entry point: the est-077y core rejection, re-run standalone."""
    errs = V([{"id": "lanes", "type": "agent", "goal": "g",
               "fanout": {"items": [], "goal": "attack {item}"}}])
    assert any(e["field"] == "fanout.items" and MSG in e["msg"] for e in errs), errs


if __name__ == "__main__":
    print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)
