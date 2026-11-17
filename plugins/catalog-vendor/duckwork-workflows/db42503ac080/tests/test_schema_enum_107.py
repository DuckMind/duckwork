#!/usr/bin/env python3
"""#107 — the door ADMITS and the runner ENFORCES schema `enum`.

Closed vocabulary for verdict fields. Before this issue the door rejected
`enum` outright ("unsupported schema keyword"), so a misspelled verdict
("passedd", "Merge") committed as valid output and flowed silently into gate
`when` expressions and downstream joins. The old design comment — "never
accept a constraint such as enum that cannot be enforced" — was a correct
principle applied backwards: the fix is to ENFORCE it, not to keep rejecting it.

Law: the subset stays CLOSED. `enum` is the ONLY new keyword; the runner's
harvest validator enforces it with the EXISTING typed-retry mechanism (the
same path a `type` violation uses: one attempt_note retry naming the defect,
then `error_class:"schema"`), and `schema_prompt_block` already dumps the
whole schema dict, so the allowed set reaches the child's prompt for free.

Covers:
  1. door accepts a well-formed enum (list of non-empty strings) at top level,
     nested inside `properties`, and inside `items`;
  2. door rejects malformed enums with typed {node, field, msg} errors
     (non-list, empty list, non-string members, empty-string member) and
     REJECTS enum on a non-string-typed schema — the stricter choice, kept
     consistent with the subset philosophy: the harvest rule admits only a
     string-membered enum, so an enum it would refuse at harvest must not
     pass the door ("never accept a constraint that cannot be enforced");
  3. harvest-time: an out-of-set string value is refused via the same typed
     retry the type violations use, the retry prompt names the allowed set,
     the second attempt with an in-set value commits `done`; a persistent
     violation ends the node exactly like other schema violations
     (`error_class:"schema"`);
  4. prompt-side: `schema_prompt_block` output for an enum-carrying schema
     contains the enum literals (it dumps the whole dict — asserted here);
  5. no-new-keywords law: `patternProperties` still gets the unsupported-
     keyword error whose supported list now includes `enum`; and a
     non-enum-carrying schema keeps byte-identical door/validator behavior.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
os.environ.pop("WF_RUNS_ROOT", None)
HOME = HERE / "home107"
RUNS = HOME / "workflows"
FAKE = str(HERE / "fake")

sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402
import wf  # noqa: E402  (wf.py is stdlib-only and importable)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)

V = wfcommon.validate_graph_errors

def agent_node(schema, goal="verdict 107"):
    return [{"id": "a", "type": "agent", "goal": goal, "schema": schema}]

VERDICT = {"type": "object", "required": ["verdict"],
           "properties": {"verdict": {"type": "string",
                                       "enum": ["merge", "changes", "decision"]}}}

# ============ 1. door admits well-formed enum ============
check("door accepts enum at top level", V(agent_node(
    {"type": "string", "enum": ["a", "b"]})) == [],
    json.dumps(V(agent_node({"type": "string", "enum": ["a", "b"]}))))
check("door accepts enum on a string property (verdict-shape repro)",
      V(agent_node(VERDICT)) == [], json.dumps(V(agent_node(VERDICT))))
check("door accepts enum inside items", V(agent_node(
    {"type": "array", "items": {"type": "string", "enum": ["x", "y"]}})) == [],
    json.dumps(V(agent_node({"type": "array", "items": {"type": "string", "enum": ["x", "y"]}}))))
check("door accepts a deep-nested enum (object > properties > array > items)",
      V(agent_node({"type": "object", "properties": {
          "rows": {"type": "array", "items": {"type": "object", "properties": {
              "sev": {"type": "string", "enum": ["low", "high"]}}}}}})) == [])
_fan_enum = [{"id": "f", "type": "agent", "goal": "g",
              "fanout": {"items": ["i"], "schema": {"type": "object", "properties": {
                  "v": {"type": "string", "enum": ["yes", "no"]}}}}}]
check("door accepts enum on fanout.schema too (same schema_check runs there)",
      V(_fan_enum) == [], json.dumps(V(_fan_enum)))

# ============ 2. door rejects malformed enum with typed errors ============
def enum_err(bad_schema):
    return [e for e in V(agent_node(bad_schema))
            if e["node"] == "a" and e["field"].endswith(".enum")]

for bad in ("merge", {"v": 1}, 7):
    errs = enum_err({"type": "string", "enum": bad})
    check(f"enum {bad!r} rejected as non-list", errs and "must be a non-empty list" in errs[0]["msg"],
          json.dumps(errs))
errs = enum_err({"type": "string", "enum": ["merge", 5]})
check("non-string member rejected as bad members (it IS a list)",
      errs and "enum members must be a list of non-empty strings" in errs[0]["msg"],
      json.dumps(errs))
errs = enum_err({"type": "string", "enum": []})
check("empty enum rejected at validate time", errs and "must be a non-empty list" in errs[0]["msg"],
      json.dumps(errs))
errs = enum_err({"type": "string", "enum": ["merge", ""]})
check("empty-string member rejected", errs and "list of non-empty strings" in errs[0]["msg"],
      json.dumps(errs))
errs = enum_err({"type": "string", "enum": ["merge", None]})
check("null member rejected", errs and "list of non-empty strings" in errs[0]["msg"],
      json.dumps(errs))
errs = enum_err({"type": "string", "enum": ["a", ["b"]]})
check("nested-list member rejected", errs and "list of non-empty strings" in errs[0]["msg"],
      json.dumps(errs))
errs = enum_err({"type": "boolean", "enum": ["a", "b"]})
check("enum on a non-string-typed schema REJECTED (stricter choice: the harvest rule"
      " only enforces string-membered enums, so the door admits nothing it cannot enforce)",
      any(e["node"] == "a" and e["field"] == "schema.enum" and "only legal on" in e["msg"]
          for e in V(agent_node({"type": "boolean", "enum": ["a", "b"]}))),
      json.dumps(V(agent_node({"type": "boolean", "enum": ["a", "b"]}))))
check("enum on a schema with OMITTED type REJECTED (same enforceability law)",
      any("only legal on" in e["msg"] for e in V(agent_node({"enum": ["a"]}))))
errs = [e for e in V(agent_node({"type": "object", "properties": {
        "v": {"type": "string", "enum": "nope"}}})) if e["field"].endswith(".enum")]
check("malformed nested enum names its full dotted path", errs and
      any(e["field"] == "schema.properties.v.enum" for e in errs), json.dumps(errs))
errs = [e for e in V(agent_node(
        {"type": "array", "items": {"type": "string", "enum": [1]}})) if e["field"].endswith(".enum")]
check("malformed enum inside items names its dotted path",
      errs and errs[0]["field"] == "schema.items.enum", json.dumps(errs))

# ============ 2b. no-new-keywords law: the subset stays closed ============
errs = V(agent_node({"type": "object", "patternProperties": {}}))
kw_err = [e for e in errs if "unsupported schema keyword" in e["msg"]]
check("patternProperties still refused — the subset stays closed", bool(kw_err), json.dumps(errs))
check("the supported list names enum now (and only adds enum; #96 added minItems/minLength)",
      kw_err and kw_err[0]["msg"].endswith(
          "supported: type, required, properties, items, description, enum, minItems, minLength"),
      kw_err[0]["msg"] if kw_err else "no keyword error")

# ============ 4. prompt-side: enum literals reach the child's prompt ============
block = wf.schema_prompt_block(VERDICT)
check("schema_prompt_block carries every enum literal",
      all(lit in block for lit in ("\"merge\"", "\"changes\"", "\"decision\"")), block[:200])
check("schema_prompt_block non-enum behavior byte-stable",
      wf.schema_prompt_block(VERDICT) == wf.schema_prompt_block(json.loads(json.dumps(VERDICT))))
plain = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
check("non-enum schema prompt block unchanged (golden prompt path)",
      wf.schema_prompt_block(plain) == wf.schema_prompt_block(plain))

# ============ 3. harvest-time enforcement (real runner + fake children) ============
shutil.rmtree(HOME, ignore_errors=True)
HOME.mkdir(parents=True); RUNS.mkdir()
(HOME / "fake.log").write_text("")

def mk(run_id, nodes, **meta):
    r = RUNS / run_id
    shutil.rmtree(r, ignore_errors=True)
    (r / "nodes").mkdir(parents=True); (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
    m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 60}
    m.update(meta)
    (r / "run.json").write_text(json.dumps(m))
    return r

def wf_run(run_id, extra_env=None, timeout=180):
    env = dict(os.environ, DUCKWORK_HOME=str(HOME), WF_RUNS_ROOT=str(RUNS), FAKE_LOG=str(HOME / "fake.log"),
               **(extra_env or {}))
    return subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run_id],
                          env=env, capture_output=True, text=True, timeout=timeout).stdout.strip()

def rec_of(r, nid):
    p = r / "nodes" / f"{nid}.json"
    return json.loads(p.read_text()) if p.exists() else {}

def events_of(r):
    p = r / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

def exit_reason(r):
    p = r / "runner_exit.json"
    return json.loads(p.read_text()).get("reason", "") if p.exists() else ""

ENUM_SCHEMA = {"type": "object", "required": ["verdict"],
               "properties": {"verdict": {"type": "string",
                                          "enum": ["ship", "hold"]}}}

# 3a. out-of-set first answer -> typed retry naming the allowed set -> retry commits
r = mk("e107-retry", [{"id": "j", "type": "agent", "goal": "ENUMTEST e107-retry",
                       "schema": ENUM_SCHEMA}])
(HOME / "fake.log").write_text("")
out = wf_run("e107-retry", {"FAKE_MODE": "enum_out_then_in"})
rec = rec_of(r, "j")
check("harvest: out-of-set first answer is retried and the in-set retry commits done",
      rec.get("status") == "done" and rec.get("output") == {"verdict": "ship"}, json.dumps(rec)[:200])
n_j = (HOME / "fake.log").read_text().count("e107-retry")
check("exactly two spawns (first refused, retry committed)", n_j == 2, f"spawns={n_j}")
prompts = sorted((r / "logs").glob("j.a*.prompt.md"), key=lambda p: p.name)
check("retry prompt names the enum violation AND the allowed set",
      len(prompts) == 2 and "schema validation" in prompts[1].read_text()
      and "$.verdict: not an allowed value" in prompts[1].read_text()
      and "'ship'" in prompts[1].read_text() and "'hold'" in prompts[1].read_text(),
      prompts[1].read_text()[-300:] if len(prompts) == 2 else f"prompts={len(prompts)}")
check("first attempt's prompt carried the enum literals (schema_prompt_block)",
      prompts and "\"ship\"" in prompts[0].read_text() and "\"hold\"" in prompts[0].read_text())

# 3b. persistent violation ends the node like every other schema violation
r = mk("e107-persist", [{"id": "k", "type": "agent", "goal": "verdict e107-persist",
                         "schema": ENUM_SCHEMA}])
out = wf_run("e107-persist", {"FAKE_MODE": "enum_always_bad"})
rec = rec_of(r, "k")
check("harvest: persistent out-of-set answer ends the node error_class=schema (same as type violations)",
      rec.get("status") == "failed" and rec.get("error_class") == "schema"
      and "schema validation" in rec.get("error", "") and "$.verdict: not an allowed value" in rec.get("error", ""),
      json.dumps(rec)[:220])
n_k = (HOME / "fake.log").read_text().count("e107-persist")
check("persistent violation used exactly the two attempts the type-violation path uses",
      n_k == 2, f"spawns={n_k}")
check("run blocked on the failed node (same shape as the bad_schema class)",
      exit_reason(r) == "blocked by failed k", exit_reason(r))

# 3c. an in-set first answer commits immediately — no retry, no extra spawn
r = mk("e107-clean", [{"id": "c", "type": "agent", "goal": "verdict e107-clean",
                       "schema": ENUM_SCHEMA}])
(HOME / "fake.log").write_text("")
out = wf_run("e107-clean", {"FAKE_MODE": "enum_always_good"})
rec = rec_of(r, "c")
check("harvest: in-set answer commits on the first attempt",
      rec.get("status") == "done" and rec.get("output") == {"verdict": "hold"}
      and (HOME / "fake.log").read_text().count("e107-clean") == 1, json.dumps(rec)[:160])

# 3d. the DIRECT validator: enum enforced at every position, and the
# error string carries the allowed set the retry prompt reuses.
errs = wf.validate({"verdict": "shipp"}, ENUM_SCHEMA)
check("validate(): out-of-set string refused naming path + allowed set",
      len(errs) == 1 and errs[0].startswith("$.verdict: not an allowed value")
      and "'ship'" in errs[0] and "'hold'" in errs[0], json.dumps(errs))
check("validate(): in-set string passes", wf.validate({"verdict": "ship"}, ENUM_SCHEMA) == [])
check("validate(): wrong-typed value keeps the type error (no double-report)",
      wf.validate({"verdict": 5}, ENUM_SCHEMA) == ["$.verdict: expected string"])
check("validate(): enum enforced inside items",
      wf.validate(["a", "zz"], {"type": "array", "items": {"type": "string",
                                                           "enum": ["a", "b"]}})
      == ["$[1]: not an allowed value (allowed: 'a', 'b')"])
check("validate(): enum enforced on the top-level string itself",
      wf.validate("nope", {"type": "string", "enum": ["yes", "no"]})
      == ["$: not an allowed value (allowed: 'yes', 'no')"])
# 5. byte-identical behavior for non-enum schemas: the classic type/required
# errors are character-for-character what they were.
classic = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
check("validate(): missing-required message byte-stable",
      wf.validate({}, classic) == ["$: missing required 'answer'"])
check("validate(): type-violation message byte-stable",
      wf.validate({"answer": 3}, classic) == ["$.answer: expected string"])
check("validate(): no schema => no errors (unchanged)", wf.validate({"a": 1}, None) == [])
check("validate(): a schema WITHOUT enum behaves exactly as before",
      wf.validate({"verdict": "anything-goes"},
                  {"type": "object", "required": ["verdict"],
                   "properties": {"verdict": {"type": "string"}}}) == [])

# non-enum door behavior byte-stable: the whole pre-existing schema grammar
check("door: legacy grammar untouched (type/required/properties/items/description all clean)",
      V(agent_node({"type": "object", "required": ["ok"], "description": "x",
                    "properties": {"ok": {"type": "boolean"},
                                   "tags": {"type": "array", "items": {"type": "string"}}}})) == [])
check("door: legacy unsupported-keyword refusal keeps its exact field naming"
      " (#96 re-pin: minItems/minLength are admitted+enforced now — maxItems is the"
      " still-unsupported keyword proving the subset stays closed)",
      any(e["node"] == "a" and e["field"] == "schema.maxItems"
          and "unsupported schema keyword" in e["msg"]
          for e in V(agent_node({"type": "array", "maxItems": 2}))))

print()
if ok:
    print("ALL PASS")
else:
    print("FAILURES PRESENT")
    sys.exit(1)
