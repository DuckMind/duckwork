"""Papercuts 2026-09-22 (owner feedback, sibling seat):
  1. fan-out items[].goal was silently ignored — fanout.goal was the only template.
  2. tool_describe returned {} for the workflow tool — schema registered as bare JSON-schema,
     registry reads fn["parameters"].
"""
import importlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
wf = importlib.import_module("wf")
wfcommon = importlib.import_module("wfcommon")
door = importlib.import_module("__init__")

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))
    fails += 0 if cond else 1

# ---- 1. per-item goal overrides the template (pure function path) ----
def render(fo, item, i, node_goal=""):
    tmpl = (item.get("goal") if isinstance(item, dict) and isinstance(item.get("goal"), str) and item["goal"].strip()
            else fo.get("goal") or node_goal)
    return wf.fmt_goal(tmpl, item, i)

fo = {"goal": "unused", "items": [{"goal": "audit host A", "verdict_note": "x"}, {"goal": "audit host B"}]}
check("item goal wins over fanout.goal", render(fo, fo["items"][0], 0) == "audit host A")
check("second item keeps its own goal", render(fo, fo["items"][1], 1) == "audit host B")
fo2 = {"goal": "probe {host} #{index}", "items": [{"host": "alpha"}, {"host": "beta"}]}
check("template still renders when items carry no goal", render(fo2, fo2["items"][1], 1) == "probe beta #1")
fo3 = {"goal": "probe {host}", "items": [{"host": "x", "goal": "   "}]}
check("blank item goal falls back to template", render(fo3, fo3["items"][0], 0) == "probe x")

# the live engine path: assert the engine source uses the override (guards against a regression that
# re-inlines fo.get("goal") as the only template)
src = (HERE / "wf.py").read_text()
check("engine reads item['goal'] before the template", 'item.get("goal")' in src and 'fo.get("goal") or node.get("goal", "")' in src)

# ---- 1b. validator ----
def v(nodes): return wfcommon.validate_graph(nodes)
check("validator: items[].goal must be non-empty string",
      "fanout.items[0].goal" in (v([{"id": "f", "type": "agent", "goal": "t", "fanout": {"items": [{"goal": 3}]}}]) or ""))
check("validator: no template + not every item has a goal -> rejected",
      "goal template or a goal on every item" in (v([{"id": "f", "type": "agent", "fanout": {"items": [{"goal": "a"}, {"host": "b"}]}}]) or ""))
check("validator: no template but every item has a goal -> ok",
      v([{"id": "f", "type": "agent", "fanout": {"items": [{"goal": "a"}, {"goal": "b"}]}}]) is None)
check("validator: plain string items with a template -> ok",
      v([{"id": "f", "type": "agent", "fanout": {"goal": "probe {item}", "items": ["a", "b"]}}]) is None)

# ---- 2. registry shape ----
sch = door.WORKFLOW_SCHEMA
check("schema has description", isinstance(sch.get("description"), str) and len(sch["description"]) > 40)
check("schema has parameters object", isinstance(sch.get("parameters"), dict) and sch["parameters"].get("type") == "object")
props = sch["parameters"]["properties"]
check("parameters carry action enum", "run" in props["action"]["enum"] and "amend" in props["action"]["enum"])
check("parameters carry graph + run_id", "graph" in props and "run_id" in props)
check("required = [action]", sch["parameters"].get("required") == ["action"])
check("tool_describe view (fn['parameters']) is non-empty", bool(sch.get("parameters", {}).get("properties")))
check("fanout doc mentions per-item goal override", "item's own `goal` key overrides" in props["graph"]["description"])

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
