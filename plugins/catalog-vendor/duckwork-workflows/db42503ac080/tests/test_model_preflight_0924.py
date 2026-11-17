"""FEEDBACK #43: model preflight at run/amend submit time, before the first wave.
A node pinning an alias/tier that resolves to NOTHING is rejected at submit (never
after N spawn failures); literal ids pass through — preflight proves RESOLUTION,
not liveness, and the error text says exactly that. Pure function + one call site
(tail of _resolve_models), so this test never spawns a runner. Stdlib only."""
import importlib, atexit, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-preflight-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
tmp = tmp_dir.name
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = tmp
os.environ["WF_RUNS_ROOT"] = str(Path(tmp) / "workflows")
door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

class Ctx:
    def __init__(self, tiers): self.t = tiers
    def get_config(self, k, d=None): return self.t if k == "models" else d

door._CTX = Ctx({"worker": "qwen38-next"})
# Same seat shape _seat_model_cfg returns: dead-alias keeps its (empty) target —
# the alias declares itself but resolves to nothing.
door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {
    "sol": "anthropic/gpt-ish", "dead": "", "blank": "   "}}

# 1. pure function: dead alias rejected, sharing nodes listed; literal passes through
err = door.model_preflight([("a", "dead", None), ("b", "dead", None), ("c", "sol", None)],
                           {"worker": "qwen38-next"}, door._seat_model_cfg())
check("pure fn rejects dead alias", err is not None and "'dead'" in err
      and "nodes: a, b" in err and "sol" not in str(err).split(" —")[0], err)
check("error says resolution-not-liveness", err is not None
      and "RESOLUTION, not liveness" in err and "reachability" in err, err)
check("pure fn: literal id passes", door.model_preflight([("a", "some/literal-id", None),
      ("b", "bare-literal", None)], {}, door._seat_model_cfg()) is None)
check("pure fn: tier + known alias + unset pass", door.model_preflight(
      [("a", "worker", None), ("b", "sol", None), ("c", None, None)],
      {"worker": "qwen38-next"}, door._seat_model_cfg()) is None)
check("pure fn: blank-target alias rejected", door.model_preflight(
      [("z", "blank", None)], {}, door._seat_model_cfg()) is not None)

# 2. known alias accepted (no spawn: resolve_models directly)
nodes = [{"id": "a", "type": "agent", "goal": "x", "model": "sol"}]
err, table = door.resolve_models(nodes)
check("known alias accepted", err is None and nodes[0]["model"] == "sol"
      and table["a"] == "sol", err)

# 3. literal id passes through untouched, no liveness claim
nodes = [{"id": "a", "type": "agent", "goal": "x", "model": "totally-made-up/literal"}]
err, table = door.resolve_models(nodes)
check("literal id passes through", err is None and nodes[0]["model"] == "totally-made-up/literal", err)

# 4. dead alias rejected AT RUN (act_run), fail-closed: no run dir litter
root = Path(tmp) / "workflows"
before = set(p.name for p in root.glob("*")) if root.exists() else set()
out = door.act_run({"graph": {"name": "dead", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "model": "dead"},
    {"id": "b", "type": "agent", "goal": "x", "model": "dead"}]}})
after = set(p.name for p in root.glob("*")) if root.exists() else set()
check("act_run rejects dead alias", "error" in out and "RESOLUTION, not liveness" in out.get("error", "")
      and "nodes: a, b" in out.get("error", ""), out)
check("act_run fail-closed, no run dir", before == after, (before, after))

# 5. dead alias rejected at amend too (same call site, before the graph swap)
r = root / "amend-me"; (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
(r / "graph.json").write_text('{"name":"amend-me","nodes":[{"id":"a","type":"agent","goal":"x"}]}')
out = door.act_amend({"run_id": "amend-me", "graph": {"name": "amend-me", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "model": "dead"}]}})
check("act_amend rejects dead alias", "error" in out and "model preflight" in out.get("error", ""), out)
check("amend left the old graph", "dead" not in (r / "graph.json").read_text())

# 6. provider-without-model rejected (validator, ahead of the preflight)
out = door.act_run({"graph": {"name": "pv", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "provider": "openai-codex"}]}})
check("provider-without-model rejected", "error" in out and "provider" in out.get("error", "").lower(), out)

# 7. unknown model name still rejected at run (resolution fail-closed, as before)
out = door.act_run({"graph": {"name": "unk", "nodes": [
    {"id": "a", "type": "agent", "goal": "x", "model": "nope-not-a-tier"}]}})
check("unknown name rejected at run", "error" in out and "nope-not-a-tier" in out.get("error", ""), out)

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
