#!/usr/bin/env python3
"""census-fanout example gate (Core-10 authoring contract).

The template's teaching law is a DETERMINISTIC TALLY: every dispatched item is
answered or NAMED missing, computed from the machine record — never from prose.
That law is only real if the graph structure makes it enforced, so this stdlib
script asserts the shape that makes it so (the PR #108 cold-reader lesson:
synth/judge nodes must DECLARE inputs + a schema and must READ all_results —
never recite a baked-in roster). Run directly: prints PASS lines, exits non-zero
on the first broken contract.
"""
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

GRAPH = ROOT / "examples" / "build" / "census-fanout.workflow.json"

# --- scrub mirror: run scripts/make_public.py's OWN merged audit pattern (built-in
# + committed scripts/scrub-list.txt) over the shipped bytes, so a future edit that
# smuggles estate vocab or a vendor model name fails HERE, at the change that
# introduced it, not at the publish build. Import, never duplicate the pattern.
# Loaded by FILE LOCATION, not a bare `import make_public`: the packaging gate's
# import-closure probe resolves modules only from root/tests/dashboard, and
# scripts/ deliberately does not ride along (test_packaging.py:133-136).
import importlib.util as _ilu
_mp_spec = _ilu.spec_from_file_location("make_public", ROOT / "scripts" / "make_public.py")
assert _mp_spec and _mp_spec.loader, "scripts/make_public.py must exist"
make_public = _ilu.module_from_spec(_mp_spec)
_mp_spec.loader.exec_module(make_public)
SCRUB = make_public.load_scrub_list(ROOT)

ok = 0


def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1
    print(f"PASS {msg}")


g = json.loads(GRAPH.read_text(encoding="utf-8"))

# model-naming + scrub law on the shipped bytes (model resolution rides seat defaults)
check(SCRUB.search(GRAPH.read_text(encoding="utf-8")) is None,
      "shipped bytes carry zero scrub hits (no estate vocab, no vendor/estate model names)")
blob = json.dumps(g)
check(not any("model" in n for n in g["nodes"]) and "model" not in g.get("defaults", {}),
      "no node pins a model: every child rides the seat default")
check(g.get("grammar") == "wf/1" and g.get("name") == "census-fanout",
      "wf/1 grammar, name census-fanout")

nodes = {n["id"]: n for n in g["nodes"]}

# the roster echo carries the MASTER LIST — the machine record the tally counts against
check(nodes["census-roster"]["type"] == "echo",
      "census-roster is an echo node (a constant travels as echo, never an agent spawn)")
roster = nodes["census-roster"]["output"]
master = roster["master"]
names = [it["item"] for it in roster["items"]]
check(isinstance(master, list) and 4 <= len(master) <= 6,
      f"master list is 4-6 generic items (got {len(master)})")
check(sorted(master) == sorted(names),
      "master list and dispatched items are the same names (the tally's count has one source of truth)")
check("battery-gauge" in master,
      "the designed dead gauge is IN the master list (the tally must surface it, never silently drop it)")
check("quorum" not in nodes["audit"].get("fanout", {}),
      "the audit fan-out sets NO quorum — a census is a barrier, nobody gets cancelled into silence")
check(nodes["audit"]["fanout"]["items_from"] == "census-roster.items",
      "items flow from the roster record (items_from), not a duplicated baked list")
fs = nodes["audit"]["fanout"]["schema"]
check(fs.get("required") == ["item", "observed", "ok"],
      "each item answers the per-item contract {item, observed, ok}")

# PR #108 cold-reader law: synth nodes DECLARE inputs + schema and READ the record
t = nodes["tally"]
check(sorted(t["inputs"]) == sorted(["census-roster.master", "audit.all_results"]),
      "tally declares inputs: the master roster AND the fan-out machine record")
check(t["schema"].get("required") == ["dispatched", "committed", "missing", "rows", "verdict"],
      "tally output schema makes the tally machine-checkable")
check("all_results" in t["goal"] and "do not assume it" in t["goal"],
      "tally goal orders the child to READ the dispatched set from all_results — never recite a baked roster")
check("battery-gauge" in t["goal"] and "alive" in t["goal"],
      "tally goal names the dead gauge AND its inversion (an ok:true on it is a red row)")

r = nodes["report"]
check(r.get("after_partial") is True and r["inputs"] == ["tally"],
      "report opts into the tally harvest (after_partial) so a damaged tally cannot darken the census")
check("verbatim" in r["goal"] and "never" in r["goal"].lower(),
      "report copies the machine tally verbatim and is forbidden from upgrading an unfinished census")

# budgets ride explicit small numbers like the sibling templates; nothing pins a model/tier
baked = wfcommon.apply_graph_defaults(copy.deepcopy(g))["nodes"]
check(all("model" not in n and "tier" not in n and "provider" not in n for n in baked),
      "baked graph resolves no explicit model: seat defaults own routing")

# every fan-out child prompt can actually interpolate its fields: template placeholders
# resolve against the item dicts the roster dispatches (fmt_goal contract).
import wf  # noqa: E402
for i, it in enumerate(roster["items"]):
    rendered = wf.fmt_goal(nodes["audit"]["fanout"]["goal"], it, i)
    check("{" not in rendered or not wf._dangling_placeholders(rendered, it),
          f"item {i} ({it['item']}) template renders with zero dangling placeholders")

print(f"OK census-fanout: {ok} checks passed")
