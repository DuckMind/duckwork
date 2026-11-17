"""Feedback #72: schemas may declare type "boolean".
(1) validate_graph_errors accepts a boolean-typed property in a node schema
    (top-level, nested in properties, and in items) — no "unsupported schema type".
(2) wf.validate accepts real JSON bools true/false for a boolean-typed property.
(3) a string like "true" does NOT coerce-pass; neither do 0/1.
(4) a MISSING required boolean fails wf.validate.
(5) a non-boolean value anywhere else still keeps its own error (no regressions).
"""
import importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1; print("PASS", msg)

V = lambda nodes: wfcommon.validate_graph_errors(nodes)

# load the runner module by path (same style as the engine tests)
spec = importlib.util.spec_from_file_location("wf72", BUILD / "wf.py")
wf = importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)

BOOL_SCHEMA = {"type": "object", "required": ["clean"],
               "properties": {"clean": {"type": "boolean"}, "notes": {"type": "string"}}}

# --- (1) pre-validation accepts boolean-typed schemas ---
node = {"id": "a", "type": "agent", "goal": "g", "schema": BOOL_SCHEMA}
check(V([node]) == [], "node schema with boolean property pre-validates", V([node]))
nested = {"type": "object", "properties": {
            "verdict": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            "flags": {"type": "array", "items": {"type": "boolean"}}}}
check(V([{"id": "a", "type": "agent", "goal": "g", "schema": nested}]) == [],
      "boolean accepted nested in properties and in items", V([{"id": "a", "type": "agent", "goal": "g", "schema": nested}]))
check(V([{"id": "a", "type": "agent", "goal": "g",
          "schema": {"type": "object", "properties": {"x": {"type": "booleanish"}}}}])
     and any(e["field"].endswith("properties.x.type") and "unsupported schema type" in e["msg"]
             for e in V([{"id": "a", "type": "agent", "goal": "g",
                          "schema": {"type": "object", "properties": {"x": {"type": "booleanish"}}}}])),
      "still-rejected nonsense type keeps its error")
check(V([{"id": "a", "type": "agent", "goal": "g",
          "schema": {"type": "object", "properties": {}}}]) == [],
      "clean object schema still validates (sanity)")

# --- (2) child emitting real bools validates ---
check(wf.validate({"clean": True, "notes": "n"}, BOOL_SCHEMA) == [],
      "child emitting true validates", wf.validate({"clean": True, "notes": "n"}, BOOL_SCHEMA))
check(wf.validate({"clean": False}, BOOL_SCHEMA) == [],
      "child emitting false validates", wf.validate({"clean": False}, BOOL_SCHEMA))

# --- (3) no coercion: 'true' string is rejected, not coerced ---
e = wf.validate({"clean": "true"}, BOOL_SCHEMA)
check(any("expected boolean" in x for x in e), "string 'true' does NOT coerce-pass", e)
e = wf.validate({"clean": "false"}, BOOL_SCHEMA)
check(any("expected boolean" in x for x in e), "string 'false' rejected too", e)
e = wf.validate({"clean": 1}, BOOL_SCHEMA)
check(any("expected boolean" in x for x in e), "int 1 rejected (no truthy coercion)", e)
e = wf.validate({"clean": 0}, BOOL_SCHEMA)
check(any("expected boolean" in x for x in e), "int 0 rejected (no falsy coercion)", e)

# --- (4) missing required boolean fails ---
e = wf.validate({"notes": "n"}, BOOL_SCHEMA)
check(any("missing required 'clean'" in x for x in e), "missing required boolean fails", e)
e = wf.validate({}, BOOL_SCHEMA)
check(any("missing required 'clean'" in x for x in e), "empty object fails required boolean", e)

# --- (5) no regressions on the other types ---
check(wf.validate({"clean": True, "notes": 5}, BOOL_SCHEMA)
      == ["$.notes: expected string"], "string error still reported beside boolean ok",
      wf.validate({"clean": True, "notes": 5}, BOOL_SCHEMA))
NUM = {"type": "object", "required": ["n"], "properties": {"n": {"type": "integer"}}}
check(wf.validate({"n": 3}, NUM) == [], "integer still validates")
check(wf.validate({"n": "3"}, NUM) == ["$.n: expected number"], "integer string still rejected")
BOOLARRAY = {"type": "object", "properties": {"flags": {"type": "array", "items": {"type": "boolean"}}}}
check(wf.validate({"flags": [True, False]}, BOOLARRAY) == [],
      "array of booleans validates", wf.validate({"flags": [True, False]}, BOOLARRAY))
check(wf.validate({"flags": [True, "yes"]}, BOOLARRAY) == ["$.flags[1]: expected boolean"],
      "array item string rejected at its index", wf.validate({"flags": [True, "yes"]}, BOOLARRAY))
check(wf.validate({"clean": "True"}, {"type": "object",
                                     "properties": {"clean": {"type": "boolean"}}})
      == ["$.clean: expected boolean"], "non-required boolean property still type-checked")

print(f"\nALL PASS ({ok})")
