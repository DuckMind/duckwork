"""fb 034849a23af94418: an amend must not re-resolve already-committed nodes against the
CURRENT seat. Resolution is idempotent (a node's own tier target is a known model);
nodes that will replay-skip keep their committed bake verbatim; edited / re-running /
pending nodes re-route on the current seat (never on a stale committed route).
Stdlib only; dry_run amends only (no runner spawned); liveness ping stubbed."""
import atexit, copy, importlib, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-rebake-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
home = Path(tmp_dir.name)
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(home / "workflows")  # #71 shelf pin
ALIASES = ("  aliases:\n    fable: anthropic/claude-fable-5.1\n    opus: anthropic/claude-opus-5-5\n"
           "    sol: openai-codex/gpt-6-sol\n")
SEAT_DEFAULT = "model:\n  default: qwen38-next\n" + ALIASES      # default-profile seat
SEAT_FIXER = "model:\n  default: claude-opus-5-5\n" + ALIASES    # fixer-profile seat
TIERS_DEFAULT = {"worker": "qwen38-next", "manager": "fable", "frontier": "sol"}
TIERS_FIXER = {"worker": "qwen38-next", "manager": "opus", "frontier": "sol"}
(home / "config.yaml").write_text(SEAT_DEFAULT)
door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
from wfcommon import efp
door._ping_route_once = lambda p, m: {"liveness": "unknown"}   # no network

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

class Ctx:
    def __init__(self, t): self.t = t
    def get_config(self, k, d=None): return self.t if k == "models" else d

def seat(which):
    (home / "config.yaml").write_text(SEAT_DEFAULT if which == "default" else SEAT_FIXER)
    door._CTX = Ctx(dict(TIERS_DEFAULT if which == "default" else TIERS_FIXER))

def author(extra=False):
    nodes = [{"id": "recon", "type": "agent", "goal": "r", "model": "manager"},
             {"id": "check", "type": "agent", "goal": "c", "model": "manager", "after": ["recon"]},
             {"id": "impl", "type": "agent", "goal": "i", "model": "worker", "after": ["check"]}]
    if extra:
        nodes.append({"id": "tail", "type": "agent", "goal": "t", "model": "manager", "after": ["impl"]})
    return {"name": "probe", "nodes": nodes}

def commit_run(rid, extra=False, pending=()):
    """Commit a run the way act_run does (defaults + resolve) under the DEFAULT seat;
    every node done at its efp except `pending` (no record)."""
    seat("default")
    g = door._common.apply_graph_defaults(author(extra))
    err, _, _ = door._resolve_models(g["nodes"])
    assert err is None, err
    r = home / "workflows" / rid
    (r / "nodes").mkdir(parents=True)
    (r / "graph.json").write_text(json.dumps(g))
    byid = {n["id"]: n for n in g["nodes"]}
    for n in g["nodes"]:
        if n["id"] not in pending:
            (r / "nodes" / f"{n['id']}.json").write_text(json.dumps({"status": "done", "efp": efp(byid, n)}))
    return g

def amend(rid, graph):
    return door.act_amend({"run_id": rid, "graph": graph, "dry_run": True})

def route(out, nid):
    v = ((out.get("routes") or {}).get(nid) or {}).get("resolved") or {}
    return (v.get("provider"), v.get("model"))

g = commit_run("run-A")
check("committed defs are the live shape",
      [(n["id"], n.get("model"), n.get("tier"), n.get("provider")) for n in g["nodes"]]
      == [("recon", "fable", "manager", None), ("check", "fable", "manager", None),
          ("impl", "qwen38-next", "worker", None)])

# 1. same seat, byte-identical COMMITTED graph resubmitted -> nothing re-runs
seat("default")
cg = copy.deepcopy(g)
out = amend("run-A", cg)
check("same seat, committed graph: no error", out.get("error") is None, out.get("error"))
check("same seat, committed graph: changed == []", out.get("changed") == [], out.get("changed"))
check("same seat, committed graph: unchanged == [recon,check,impl]",
      out.get("unchanged") == ["recon", "check", "impl"], out.get("unchanged"))
check("same seat, committed graph: recon/check carry no provider (resolved route)",
      route(out, "recon") == (None, "fable") and route(out, "check") == (None, "fable"),
      [route(out, "recon"), route(out, "check")])

# 2. cross seat (fixer: default claude-opus-5-5, manager->opus), committed graph -> no error
seat("fixer")
out = amend("run-A", copy.deepcopy(g))
check("cross seat, committed graph: no 'unknown model' error", out.get("error") is None, out.get("error"))
check("cross seat, committed graph: changed == []", out.get("changed") == [], out.get("changed"))

# 3. idempotence: tier '5' -> bare 'o-huge' resolves twice
seat("default")
door._CTX = Ctx({"5": "o-huge"})
nodes = [{"id": "x", "type": "agent", "goal": "g", "model": "5"}]
e1, _, _ = door._resolve_models(nodes)
e2, _, _ = door._resolve_models(nodes)
check("idempotence: first resolve of tier '5'->'o-huge' ok", e1 is None, e1)
check("idempotence: resolve(resolve()) ok", e2 is None, e2)

# E1-E3: genuine edits on the SAME (default) seat still re-run exactly as base
seat("default")
a = author(); a["nodes"][1]["goal"] = "c2"
out = amend("run-A", a)
check("E1 goal edit on check: will_rerun == [check,impl]", out.get("will_rerun") == ["check", "impl"], out.get("will_rerun"))
a = author(); a["nodes"][2]["model"] = "frontier"
out = amend("run-A", a)
check("E2 impl worker->frontier: will_rerun == [impl]", out.get("will_rerun") == ["impl"], out.get("will_rerun"))
check("E2 impl resolved model 'sol'", route(out, "impl")[1] == "sol", route(out, "impl"))
a = author(); a["nodes"][0]["model"] = "opus"
out = amend("run-A", a)
check("E3 recon manager->opus: will_rerun == [recon,check,impl]",
      out.get("will_rerun") == ["recon", "check", "impl"], out.get("will_rerun"))
check("E3 recon provider 'anthropic'", route(out, "recon")[0] == "anthropic", route(out, "recon"))

# E4-E6: fixer seat — edited / re-running nodes route on the CURRENT seat, never the stale bake
seat("fixer")
a = author(); a["nodes"][1]["goal"] = "c EDITED"
out = amend("run-A", a)
check("E4 fixer seat, author graph, check goal edited: will_rerun == [check,impl]",
      out.get("will_rerun") == ["check", "impl"], out.get("will_rerun"))
check("E4 check routes (None,'opus'), not 'fable'", route(out, "check") == (None, "opus"), route(out, "check"))
c = copy.deepcopy(g); c["nodes"][1]["goal"] = "c EDITED"
out = amend("run-A", c)
check("E5 fixer seat, committed graph, check goal edited: no error", out.get("error") is None, out.get("error"))
check("E5 will_rerun == [check,impl]", out.get("will_rerun") == ["check", "impl"], out.get("will_rerun"))
check("E5 check routes (None,'opus'), no provider='anthropic'", route(out, "check") == (None, "opus"), route(out, "check"))
check("E5 unedited recon keeps its committed bake", route(out, "recon") == (None, "fable"), route(out, "recon"))
out = amend("run-A", author())
check("E6 fixer seat, author graph unchanged: will_rerun == []", out.get("will_rerun") == [], out.get("will_rerun"))
check("E6 unchanged == [recon,check,impl]", out.get("unchanged") == ["recon", "check", "impl"], out.get("unchanged"))

# pending (record-less) node present in both graphs re-resolves on the current seat
g2 = commit_run("run-P", extra=True, pending=("tail",))
seat("fixer")
out = amend("run-P", copy.deepcopy(g2))
check("pending node, committed graph: no error", out.get("error") is None, out.get("error"))
check("pending node re-resolves on current seat (None,'opus')", route(out, "tail") == (None, "opus"), route(out, "tail"))
check("pending node: done nodes still unchanged", out.get("unchanged") == ["recon", "check", "impl"], out.get("unchanged"))
out = amend("run-P", author(extra=True))
check("pending node, author graph: routes (None,'opus')", route(out, "tail") == (None, "opus"), route(out, "tail"))
check("pending node, author graph: done nodes unchanged", out.get("unchanged") == ["recon", "check", "impl"], out.get("unchanged"))

# F2 (deep review #26): a committed, alive-proved node def re-submitted VERBATIM
# still un-bakes (keeps the committed literal, re-resolves the tier). The proof
# annotation must NOT participate in the "def unchanged" comparison — the author's
# copy arrives without it (popped pre-submit), so requiring equality would disable
# idempotence for every alive-proved node. Mutation-visible: put route_verified
# back into _ROUTE_MATCH_KEYS and this row goes red.
seat("default")
committed_n = {"id": "x", "type": "agent", "goal": "g", "tier": "manager",
               "model": "fable", "route_verified": "anthropic/fable"}
node = copy.deepcopy(committed_n)
err, _, _ = door._resolve_models([node], committed={"x": committed_n})
check("F2: alive-proved committed def re-submitted un-bakes to the live shape",
      err is None and node.get("model") == "fable" and node.get("tier") == "manager"
      and "provider" not in node,
      f"{err} {node}")

print(f"\n{'ALL PASS' if not fails else f'{fails} FAIL'}")
sys.exit(1 if fails else 0)
