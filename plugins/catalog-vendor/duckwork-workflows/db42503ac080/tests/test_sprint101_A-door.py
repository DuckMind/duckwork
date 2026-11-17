"""SPRINT-101 Lane A-door: the door validates (model, provider, reasoning) from the
route tables and rejects every known 0-execution crash graph at submit.
  #1 provider INHERITED from the model alias; reasoning validated PER ROUTE
     (agent.reasoning_effort.route_supported_efforts) with the supported list and the
     nearest level in the error — never a silent downgrade; unknown alias → near-miss.
  #2 full-graph submit validation: closed gate/agent key sets (wait.every_s/timeout_s
     allowed INSIDE wait), gate options non-empty, when syntax, after refs,
     fanout.items_from head must be an ancestor.
Hermetic: no network, no spawn, core import guarded. Stdlib only; exit 0 green."""
import importlib, atexit, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-adoor-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
tmp = tmp_dir.name
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = tmp
os.environ["WF_RUNS_ROOT"] = str(Path(tmp) / "workflows")
door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
import wfcommon

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

class Ctx:
    def __init__(self, tiers=None): self.t = tiers or {}
    def get_config(self, k, d=None): return self.t if k == "models" else d

SEAT = {"default": "seat-default", "aliases": {
    "sol": "openai-codex/gpt-5.3-codex",          # provider-qualified alias
    "plain": "qwen38-next",                        # bare alias — no provider to inherit
    "codexmax": "openai-codex/gpt-5.6",            # codex gpt-5.6 family
}}
door._CTX = Ctx({"worker": "qwen38-next", "codex-tier": "openai-codex/gpt-5.3-codex"})
door._seat_model_cfg = lambda: SEAT

V = lambda nodes: wfcommon.validate_graph_errors(nodes)

# ---------- #1b reasoning validated PER ROUTE ----------
# 'minimal' is in the GLOBAL set (so the old global check passed) but codex legacy
# routes reject it → the door must reject with the supported list + nearest suggestion.
err, table, routes = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "sol", "reasoning": "minimal"}])
check("door rejects 'minimal' on a codex route", err is not None and "minimal" in str(err)
      and "supported:" in str(err), err)
check("per-route error carries the supported list", err is not None
      and "none" in str(err) and "low" in str(err) and "xhigh" in str(err), err)
check("per-route error suggests the nearest level (no silent downgrade)",
      err is not None and "nearest supported level" in str(err) and "low" in str(err), err)

# a valid level for the resolved route passes at the door
err, table, routes = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "sol", "reasoning": "high"}])
check("door accepts a route-supported level", err is None, err)
# 'max' exists globally; gpt-5.6 codex supports it, legacy codex does not
err, _, _ = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "codexmax", "reasoning": "max"}])
check("gpt-5.6 codex route accepts 'max'", err is None, err)
err, _, _ = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "sol", "reasoning": "max"}])
check("legacy codex route rejects 'max' with suggestion", err is not None and "xhigh" in str(err), err)
# no model at all → seat default route unknown to the door → global-set fallback
err, _, _ = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "reasoning": "minimal"}])
check("unset model keeps the global-set fallback", err is None, err)
# explicit provider routes the same check (openai-codex + legacy model)
err, _, _ = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "gpt-5.3-codex",
     "provider": "openai-codex", "reasoning": "minimal"}])
check("explicit provider + model validated per route", err is not None and "minimal" in str(err), err)
# 'none' is supported everywhere on these routes
err, _, _ = door._resolve_models([
    {"id": "a", "type": "agent", "goal": "x", "model": "sol", "reasoning": "none"}])
check("'none' passes on codex legacy route", err is None, err)

# ---------- #1a provider INHERITED from the alias ----------
n = {"id": "a", "type": "agent", "goal": "x", "model": "sol"}
err, table, routes = door._resolve_models([n])
check("provider inherited: node def carries it", err is None and n.get("provider") == "openai-codex", (err, n))
check("routes show the resolved provider", routes and routes["a"]["resolved"]["provider"] == "openai-codex"
      and routes["a"]["requested"]["provider"] is None, routes)
check("inherited route still validates reasoning", err is None, err)
# bare alias (no provider in the target) → provider stays unset (seat default)
n2 = {"id": "b", "type": "agent", "goal": "x", "model": "plain"}
err, _, routes = door._resolve_models([n2])
check("bare alias inherits no provider", err is None and "provider" not in n2
      and routes["b"]["resolved"]["provider"] is None, (err, n2))
# tier with provider-qualified target inherits too
n3 = {"id": "c", "type": "agent", "goal": "x", "model": "codex-tier", "reasoning": "high"}
err, _, routes = door._resolve_models([n3])
# tier resolves to its target verbatim (base law: no prefix strip without an author-
# explicit provider); provider is INHERITED and the route validates reasoning per route.
check("tier target inherits provider", err is None and n3.get("provider") == "openai-codex"
      and n3["model"] == "openai-codex/gpt-5.3-codex" and n3.get("tier") == "codex-tier", (err, n3))
# explicit provider wins over inheritance
n4 = {"id": "d", "type": "agent", "goal": "x", "model": "plain", "provider": "groq"}
err, _, _ = door._resolve_models([n4])
check("explicit provider never overridden", err is None and n4["provider"] == "groq", (err, n4))

# ---------- #1c unknown alias → near-miss suggestions ----------
err, _, _ = door._resolve_models([{"id": "a", "type": "agent", "goal": "x", "model": "sol1"}])
check("unknown alias suggests a near-miss", err is not None and "did you mean" in err
      and "sol" in err, err)
err, _, _ = door._resolve_models([{"id": "a", "type": "agent", "goal": "x", "model": "workr"}])
check("unknown tier suggests a near-miss", err is not None and "worker" in err, err)
err, _, _ = door._resolve_models([{"id": "a", "type": "agent", "goal": "x", "model": "zzz-qqq-xxx"}])
check("far-off name: no bogus suggestion, still fails closed", err is not None
      and "unknown model" in err and "did you mean" not in err, err)

# ---------- #1d tool description says per-route ----------
desc = door.WORKFLOW_PARAMS["properties"]["graph"]["description"]
check("tool description: per-route validation", "validated PER ROUTE" in desc, desc[:120])
check("tool description: provider inheritance", "INHERITED" in desc, desc[:120])

# ---------- #2 closed key sets + the three crash graphs ----------
# every_s/timeout_s ARE allowed inside wait{} (gen-pilot-3's shape) — verified open...
check("wait.every_s/timeout_s allowed in wait{}", V([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "q",
     "wait": {"until_argv": ["true"], "every_s": 60, "timeout_s": 3600}}]) == [])
# ...and rejected at gate TOP level with the gate's allowed list (gen-pilot-3 crash shape)
e = V([{"id": "lane_gate", "type": "gate", "after": ["a"], "question": "q",
        "every_s": 60, "timeout_s": 3600},
       {"id": "a", "type": "agent", "goal": "x"}])
check("gen-pilot-3 shape: top-level every_s is a door error",
      any(x["node"] == "lane_gate" and x["field"] == "every_s" and "unknown key" in x["msg"]
          and '"question"' in x["msg"] for x in e), e)

# torture-gate-grammar: invented gate key + on_skip without when
e = V([{"id": "a", "type": "agent", "goal": "x"},
       {"id": "g", "type": "gate", "after": ["a"], "question": "q",
        "on_skip": "prune", "veto": True}])
check("torture-gate-grammar shape: invented gate key + on_skip-without-when at door",
      any(x["field"] == "veto" and "unknown key" in x["msg"] for x in e)
      and any(x["field"] == "on_skip" and "when" in x["msg"] for x in e), e)

# prune-proof: malformed when expression is a door error, never a runner crash
e = V([{"id": "j", "type": "agent", "goal": "x"},
       {"id": "g", "type": "gate", "after": ["j"], "question": "q",
        "when": "out.judge.verdict == " }])
check("prune-proof shape: malformed when rejected at door",
      any(x["field"] == "when" for x in e), e)
check("when well-formed passes", V([{"id": "j", "type": "agent", "goal": "x"},
       {"id": "g", "type": "gate", "after": ["j"], "question": "q",
        "when": "out.j.verdict == 'ship'", "on_skip": "prune"}]) == [])

# gate options must be non-empty list of strings when present
e = V([{"id": "a", "type": "agent", "goal": "x"},
       {"id": "g", "type": "gate", "after": ["a"], "question": "q", "options": []}])
check("empty gate options rejected", any(x["field"] == "options" for x in e), e)
e = V([{"id": "a", "type": "agent", "goal": "x"},
       {"id": "g", "type": "gate", "after": ["a"], "question": "q", "options": ["ok", "  "]}])
check("blank-string gate option rejected", any(x["field"] == "options" for x in e), e)
check("gate without options still valid (free-form answer)", V([
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "q"}]) == [])

# after refs exist; fanout.items_from head must be an ancestor
e = V([{"id": "f", "type": "agent", "goal": "x", "fanout": {"items_from": "ghost.items", "goal": "i"}}])
check("items_from head must be an after-ancestor",
      any(x["field"] == "fanout.items_from" and "ancestor" in x["msg"].lower() for x in e), e)
e = V([{"id": "p", "type": "agent", "goal": "x"},
       {"id": "f", "type": "agent", "after": ["p"], "fanout": {"items_from": "p.items", "goal": "i"}}])
check("items_from from a real ancestor passes", e == [], e)
e = V([{"id": "p", "type": "agent", "goal": "x"},
       {"id": "f", "type": "agent", "fanout": {"items_from": "p.items", "goal": "i"}}])
check("items_from without after is a door error",
      any(x["field"] == "fanout.items_from" for x in e), e)
check("after ref to unknown node is a door error",
      any(x["field"] == "after" and "unknown" in x["msg"] for x in
          V([{"id": "a", "type": "agent", "goal": "x", "after": ["nope"]}])))

# door end-to-end: graph-level defects return errors:[{node,field,msg}] and no run dir
root = Path(tmp) / "workflows"
before = set(p.name for p in root.glob("*")) if root.exists() else set()
out = door.act_run({"graph": {"name": "bad", "nodes": [
    {"id": "a", "type": "agent", "goal": "x"},
    {"id": "g", "type": "gate", "after": ["a"], "question": "q", "every_s": 60}]}})
after = set(p.name for p in root.glob("*")) if root.exists() else set()
check("act_run: graph invalid → errors[{node,field,msg}] list",
      "error" in out and any(set(e0) >= {"node", "field", "msg"} for e0 in out.get("errors", [])), out)
check("act_run fail-closed, no run dir", before == after, (before, after))
out = door.act_run({"graph": {"name": "rsn", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "model": "sol", "reasoning": "minimal"}]}})
check("act_run rejects per-route reasoning before spawn",
      "error" in out and "not supported by route" in out.get("error", ""), out)
after2 = set(p.name for p in root.glob("*")) if root.exists() else set()
check("reasoning reject left no run dir", after == after2, (after, after2))

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
