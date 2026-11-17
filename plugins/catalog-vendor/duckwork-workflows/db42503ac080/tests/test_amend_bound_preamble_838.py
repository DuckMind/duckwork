"""est-2ek.1.838: amending a materialized run whose defaults.context carries a
{run.KEY} reference must NOT prepend the shared preamble a second time.

act_run bakes defaults.context into every agent's context (apply_graph_defaults)
and THEN binds run_context, so the persisted node context starts with the BOUND
preamble while graph.json's defaults.context keeps the {run.KEY} template. The
amend door re-applies apply_graph_defaults to the submitted graph; its
`startswith(pre)` guard compared the unbound template to the bound context, missed,
and prepended the preamble again — new bytes, new efp, completed nodes re-ran
A completed node must retain its original context and fingerprint on amend.
Stdlib only; no runner spawned."""
import atexit, copy, importlib, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-838-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
home = Path(tmp_dir.name)
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(home / "workflows")
door = importlib.import_module("__init__")
import wf_test_isolation as _iso; _iso.install(door)
from wfcommon import apply_graph_defaults, efp

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

PRE = "Shared preamble: parent holds claim {run.task} in {run.store}. Stop on contention."
BIND = {"task": "case-123", "store": "/workspace/tasks"}

def author():
    return {"name": "probe", "defaults": {"context": PRE},
            "nodes": [{"id": "fix", "type": "agent", "goal": "f", "context": "fix own"},
                      {"id": "verify", "type": "agent", "goal": "v", "after": ["fix"]},
                      {"id": "note", "type": "echo", "output": {"x": 1}}]}

# The act_run order: defaults baked first, run_context bound second.
launched = door._bind_run_context(apply_graph_defaults(author()), BIND)
byid = {n["id"]: n for n in launched["nodes"]}
bound_pre = PRE.replace("{run.task}", BIND["task"]).replace("{run.store}", BIND["store"])
check("launch: fix context = bound preamble + own context",
      byid["fix"]["context"] == bound_pre + "\n\nfix own", repr(byid["fix"]["context"]))
check("launch: defaults.context keeps the {run.KEY} template",
      launched["defaults"]["context"] == PRE)

# The amend door: the caller resubmits the persisted graph (+ a new tail node);
# apply_graph_defaults runs again on it.
sub = copy.deepcopy(launched)
sub["nodes"].append({"id": "tail", "type": "agent", "goal": "t", "after": ["verify"]})
amended = apply_graph_defaults(sub)
ab = {n["id"]: n for n in amended["nodes"]}
for nid in ("fix", "verify"):
    check(f"amend: {nid} context unchanged (preamble not prepended twice)",
          ab[nid]["context"] == byid[nid]["context"],
          f"{len(byid[nid]['context'])} -> {len(ab[nid]['context'])} chars")
    check(f"amend: {nid} efp unchanged (completed node replay-skips)",
          efp(ab, ab[nid]) == efp(byid, byid[nid]),
          "fingerprint moved")
    check(f"amend: {nid} carries exactly one preamble copy",
          ab[nid]["context"].count("Shared preamble:") == 1)
check("amend: a NEW node still gets the (template) preamble once",
      ab["tail"]["context"] == PRE and ab["tail"]["context"].count("Shared preamble:") == 1,
      repr(ab["tail"].get("context")))
check("amend: echo node untouched", "context" not in ab["note"])

# Re-apply on the amended graph again: a fixed point.
again = apply_graph_defaults(copy.deepcopy(amended))
check("re-apply is a fixed point", again["nodes"] == amended["nodes"])

# The tolerance is ONLY for {run.KEY} slots: a context whose literal text differs
# from the preamble still gets it prepended (no false 'already baked').
g = {"defaults": {"context": PRE},
     "nodes": [{"id": "a", "type": "agent", "goal": "g",
                "context": "Shared preamble: parent holds claim X in Y. Go on contention."}]}
out = apply_graph_defaults(g)["nodes"][0]["context"]
check("literal mismatch outside {run.KEY} slots still prepends",
      out.startswith(PRE + "\n\n"), repr(out[:60]))
# A changed preamble on amend is still applied (an edit, not a re-bake).
g2 = copy.deepcopy(launched); g2["defaults"]["context"] = "NEW preamble {run.task}"
out2 = {n["id"]: n for n in apply_graph_defaults(g2)["nodes"]}["fix"]["context"]
check("edited preamble on amend is prepended", out2.startswith("NEW preamble {run.task}\n\n"))
# Unbound template (no run_context at launch) stays idempotent as before.
plain = apply_graph_defaults(author())
check("unbound launch: re-apply idempotent",
      apply_graph_defaults(copy.deepcopy(plain))["nodes"] == plain["nodes"])

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
