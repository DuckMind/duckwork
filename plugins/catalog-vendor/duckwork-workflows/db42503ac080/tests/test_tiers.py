"""Model tiers: node.model accepts a literal id OR a key of the owner's dict
(plugins.entries.duckwork-workflows.settings.models). Resolution at run/amend bakes
the literal into the node def (fingerprint-visible), unknown keys fail closed.
Stdlib only; no children spawned (duckwork_bin=/bin/true-ish stub never reached
because we stop before the runner does work)."""
import atexit, importlib, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-tiers-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
tmp = tmp_dir.name
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = tmp
os.environ["WF_RUNS_ROOT"] = str(Path(tmp) / "workflows")
(Path(tmp) / "config.yaml").write_text("model:\n  default: seat-default\n  aliases:\n    fable: anthropic/x\n")
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

door._CTX = Ctx({"worker": "qwen38-next", "manager": "fable", "5": "openai/o-huge"})

# 1. tier key -> literal, tier recorded, table echoes both
nodes = [{"id": "a", "type": "agent", "model": "worker"}, {"id": "b", "type": "agent", "model": "5"},
         {"id": "c", "type": "agent"}, {"id": "g", "type": "gate"}]
err, table = door.resolve_models(nodes)
check("tier keys resolve", err is None and nodes[0]["model"] == "qwen38-next" and nodes[1]["model"] == "openai/o-huge", err)
check("tier name kept on node", nodes[0].get("tier") == "worker" and nodes[1].get("tier") == "5")
check("table shows literal + tier", table["a"] == "qwen38-next  (worker)" and table["c"] == "(seat default)", table)
check("gate untouched", "g" not in table and "model" not in nodes[3])

# 2. literal provider/model bakes the provider the seat routes through (est-2ek.1.46); seat alias and default pass through unchanged
nodes = [{"id": "a", "type": "agent", "model": "anthropic/claude-z"}, {"id": "b", "type": "agent", "model": "fable"},
         {"id": "c", "type": "agent", "model": "seat-default"}]
err, table = door.resolve_models(nodes)
check("literal bakes provider; alias + default pass through", err is None and [(n.get("provider"), n["model"]) for n in nodes] == [("anthropic", "claude-z"), ("anthropic", "fable"), (None, "seat-default")], err)
check("literal table row keeps the full route", table["a"] == "anthropic/claude-z", table)
check("no tier stamped on literals", all("tier" not in n for n in nodes))

# 3. unknown key fails closed, names the valid tiers
err, _ = door.resolve_models([{"id": "a", "type": "agent", "model": "genius"}])
check("unknown key rejected", err is not None and "genius" in err and "worker" in err and "manager" in err, err)

# 4. fingerprint: same graph with tier vs literal must hash identically AFTER resolution
#    (replay determinism) and differ from a different tier.
from wfcommon import efp
g1 = [{"id": "a", "type": "agent", "goal": "x", "model": "worker"}]
g2 = [{"id": "a", "type": "agent", "goal": "x", "model": "qwen38-next", "tier": "worker"}]
g3 = [{"id": "a", "type": "agent", "goal": "x", "model": "manager"}]
for g in (g1, g3): door.resolve_models(g)
fp = lambda g: efp({n["id"]: n for n in g}, g[0])
check("resolved tier == literal fingerprint", fp(g1) == fp(g2))
check("different tier => different fingerprint", fp(g1) != fp(g3))

# 5. no tiers configured: bare keys that are not aliases/literals are rejected, literals fine
door._CTX = Ctx({})
err, _ = door.resolve_models([{"id": "a", "type": "agent", "model": "worker"}])
check("no tiers: 'worker' is unknown", err is not None)
err, t = door.resolve_models([{"id": "a", "type": "agent", "model": "fable"}, {"id": "b", "type": "agent"}])
check("no tiers: alias + unset fine", err is None and t == {"a": "fable", "b": "(seat default)"}, (err, t))

# 6. act_run rejects before creating a run dir (fail-closed leaves no litter)
door._CTX = Ctx({"worker": "qwen38-next"})
before = set(p.name for p in (Path(tmp) / "workflows").glob("*")) if (Path(tmp) / "workflows").exists() else set()
out = door.act_run({"graph": {"name": "bad", "nodes": [{"id": "a", "type": "agent", "goal": "x", "model": "nope"}]}})
after = set(p.name for p in (Path(tmp) / "workflows").glob("*")) if (Path(tmp) / "workflows").exists() else set()
check("act_run fail-closed, no run dir", "error" in out and before == after, out)

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
