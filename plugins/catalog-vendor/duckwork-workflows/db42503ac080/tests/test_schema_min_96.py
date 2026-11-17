#!/usr/bin/env python3
"""#96 — the door ADMITS and the runner ENFORCES `minItems` / `minLength`.

Harvested from #89: a gate/graph whose answer carries `verify_list: []`,
`[""]` or `["   "]` validated clean, and the door refused `minItems` outright
("unsupported schema keyword"), so the schema could not self-enforce a
non-empty verification list. Follows the #107 law: enforce it, don't keep
rejecting it — admit EXACTLY two new keywords, each ENFORCED at harvest
through the existing typed-retry path, so the door never admits a dead
constraint.

Law:
  minItems  — legal only on type:"array"; non-negative int (bool refused).
              Harvest error: "{path}: expected at least N item(s)".
  minLength — legal only on type:"string"; non-negative int. Counted on
              v.strip() — fail-closed: a whitespace-only probe is not a
              probe (deliberate deviation from JSON Schema, stated here).
              Harvest error: "{path}: expected at least N non-blank char(s)".
  No field-name special-casing of verify_list anywhere in the engine.
  The subset stays CLOSED: `maxItems` still gets the unsupported-keyword
  refusal (the closed-subset law stays tested).

Covers:
  1. door admits minItems/minLength on the right types (top level, nested,
     inside items, on fanout.schema);
  2. door refuses placement/type violations with typed {node, field, msg}
     errors (wrong type, omitted type, negative, float, string, bool);
  3. harvest (wf.validate): the #96 repro — verify_list [], [""], ["   "]
     refused naming $.verify_list / $.verify_list[0]; ["pytest -q"] clean;
     byte-stability of every pre-existing message;
  4. runner: persistent blank list takes the typed retry then
     error_class:"schema" (the #107 harness shape); blank-then-good retries
     into done with exactly two spawns;
  5. the shipped blind-council example: the door accepts its hardened
     synthesis schema and it refuses every blank verify_list.
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
HOME = HERE / "home96"
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

def agent_node(schema, goal="min 96"):
    return [{"id": "a", "type": "agent", "goal": goal, "schema": schema}]

VERIFY_SCHEMA = {"type": "object", "required": ["verify_list"],
                 "properties": {"verify_list": {"type": "array", "minItems": 1,
                                                 "items": {"type": "string",
                                                           "minLength": 1}}}}

# ============ 1. door admits the two keywords on the right types ============
check("door accepts minItems on type:array", V(agent_node(
    {"type": "array", "minItems": 1, "items": {"type": "string"}})) == [],
    json.dumps(V(agent_node({"type": "array", "minItems": 1, "items": {"type": "string"}}))))
check("door accepts minLength on type:string", V(agent_node(
    {"type": "string", "minLength": 1})) == [],
    json.dumps(V(agent_node({"type": "string", "minLength": 1}))))
check("door accepts minItems:0 / minLength:0 (non-negative, not positive)", V(agent_node(
    {"type": "array", "minItems": 0})) == [],
    json.dumps(V(agent_node({"type": "array", "minItems": 0}))))
check("door accepts both nested (verify_list repro shape)", V(agent_node(VERIFY_SCHEMA)) == [],
    json.dumps(V(agent_node(VERIFY_SCHEMA))))
_fan_min = [{"id": "f", "type": "agent", "goal": "g",
             "fanout": {"items": ["i"], "schema": {
                 "type": "object", "properties": {
                     "rows": {"type": "array", "minItems": 1,
                              "items": {"type": "string", "minLength": 1}}}}}}]
check("door accepts them on fanout.schema too (same schema_check runs there)",
      V(_fan_min) == [], json.dumps(V(_fan_min)))

# ============ 2. door refuses dead constraints with typed errors ============
errs = [e for e in V(agent_node({"type": "string", "minItems": 1}))
        if e["field"] == "schema.minItems"]
check("minItems on a NON-array schema REJECTED (enforceability law)",
      errs and "only legal on" in errs[0]["msg"], json.dumps(errs))
errs = [e for e in V(agent_node({"minItems": 1})) if e["field"] == "schema.minItems"]
check("minItems with OMITTED type REJECTED (same law)", bool(errs), json.dumps(errs))
errs = [e for e in V(agent_node({"type": "array", "minLength": 1}))
        if e["field"] == "schema.minLength"]
check("minLength on a NON-string schema REJECTED (mirror law)",
      errs and "only legal on" in errs[0]["msg"], json.dumps(errs))
errs = [e for e in V(agent_node({"minLength": 1})) if e["field"] == "schema.minLength"]
check("minLength with OMITTED type REJECTED (mirror law)", bool(errs), json.dumps(errs))
for bad in (-1, 1.5, "1", True, False, None, [1]):
    fld = "schema.minItems"
    errs = [e for e in V(agent_node({"type": "array", "minItems": bad}))
            if e["field"] == fld]
    check(f"minItems {bad!r} rejected as non-int/non-negative (bool refused)",
          errs and "non-negative integer" in errs[0]["msg"], json.dumps(errs))
    fld = "schema.minLength"
    errs = [e for e in V(agent_node({"type": "string", "minLength": bad}))
            if e["field"] == fld]
    check(f"minLength {bad!r} rejected as non-int/non-negative (bool refused)",
          errs and "non-negative integer" in errs[0]["msg"], json.dumps(errs))
# the subset stays CLOSED: a sibling keyword is still refused, and the
# supported list now names exactly the two new entries.
errs = V(agent_node({"type": "array", "maxItems": 2}))
kw_err = [e for e in errs if "unsupported schema keyword" in e["msg"]]
check("door: maxItems still refused — the subset stays closed", bool(kw_err), json.dumps(errs))
check("the supported list names minItems and minLength now",
      kw_err and kw_err[0]["msg"].endswith(
          "supported: type, required, properties, items, description, enum, minItems, minLength"),
      kw_err[0]["msg"] if kw_err else "no keyword error")

# ============ 3. harvest-time enforcement (wf.validate direct) ============
# The #96 repro, verbatim from the issue: these THREE blanks validated clean
# before the fix; each must now be a typed error naming its path.
e = wf.validate({"verify_list": []}, VERIFY_SCHEMA)
check("validate(): verify_list [] refused naming $.verify_list",
      e == ["$.verify_list: expected at least 1 item(s)"], json.dumps(e))
e = wf.validate({"verify_list": [""]}, VERIFY_SCHEMA)
check("validate(): verify_list [''] refused naming $.verify_list[0]",
      e == ["$.verify_list[0]: expected at least 1 non-blank char(s)"], json.dumps(e))
e = wf.validate({"verify_list": ["   "]}, VERIFY_SCHEMA)
check("validate(): verify_list ['   '] refused — a whitespace-only probe is NOT a probe"
      " (strip-count deviation from JSON Schema, fail-closed)",
      e == ["$.verify_list[0]: expected at least 1 non-blank char(s)"], json.dumps(e))
check("validate(): a real verify_list commits clean",
      wf.validate({"verify_list": ["pytest -q"]}, VERIFY_SCHEMA) == [])
check("validate(): missing required key keeps its exact message (no new error)",
      wf.validate({}, VERIFY_SCHEMA) == ["$: missing required 'verify_list'"],
      json.dumps(wf.validate({}, VERIFY_SCHEMA)))
check("validate(): type violation keeps the type error (no double-report)",
      wf.validate({"verify_list": "pytest"}, VERIFY_SCHEMA) == ["$.verify_list: expected array"])
check("validate(): minItems/minLength IGNORED when the value type is wrong (no pile-on)",
      wf.validate({"answer": 5}, {"type": "object", "required": ["answer"],
                                  "properties": {"answer": {"type": "string",
                                                           "minLength": 3}}})
      == ["$.answer: expected string"])
check("validate(): minLength counts NON-BLANK chars, not raw chars"
      " (' '  x  ' has 1 non-blank < 3)",
      wf.validate("  x  ", {"type": "string", "minLength": 3})
      == ["$: expected at least 3 non-blank char(s)"])
check("validate(): a string at/above the floor passes",
      wf.validate("ab c", {"type": "string", "minLength": 4}) == [])
check("validate(): minItems enforced on the top-level array itself",
      wf.validate([], {"type": "array", "minItems": 1, "items": {"type": "string"}})
      == ["$: expected at least 1 item(s)"])
check("validate(): minItems:0 accepts the empty array (non-negative, not positive)",
      wf.validate([], {"type": "array", "minItems": 0}) == [])
# byte-stability: a schema WITHOUT the new keywords behaves identically to
# before (the classic messages are character-for-character the pre-#96 ones).
classic = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
check("validate(): missing-required message byte-stable",
      wf.validate({}, classic) == ["$: missing required 'answer'"])
check("validate(): type-violation message byte-stable",
      wf.validate({"answer": 3}, classic) == ["$.answer: expected string"])
check("validate(): no schema => no errors (unchanged)", wf.validate({"a": 1}, None) == [])
check("validate(): malformed minItems/minLength in a hand-built schema is IGNORED,"
      " never crashes (forgiving validator — the door is the enforcement point)",
      wf.validate([], {"type": "array", "minItems": "two"}) == []
      and wf.validate("x", {"type": "string", "minLength": True}) == [])

# ============ 4. runner: the typed-retry path, #107 harness shape ============
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

# 4a. persistent blank -> one attempt_note retry, then error_class=schema
r = mk("e96-persist", [{"id": "k", "type": "agent", "goal": "verdict e96-persist",
                        "schema": VERIFY_SCHEMA}])
out = wf_run("e96-persist", {"FAKE_MODE": "min_always_blank"})
rec = rec_of(r, "k")
check("harvest: persistent blank verify_list ends the node error_class=schema (same as enum/type)",
      rec.get("status") == "failed" and rec.get("error_class") == "schema"
      and "schema validation" in rec.get("error", "")
      and "expected at least 1 non-blank char(s)" in rec.get("error", ""),
      json.dumps(rec)[:220])
n_k = (HOME / "fake.log").read_text().count("e96-persist")
check("persistent violation used exactly the two attempts the type-violation path uses",
      n_k == 2, f"spawns={n_k}")

# 4b. blank first answer -> typed retry names the defect -> retry commits done
r = mk("e96-retry", [{"id": "j", "type": "agent", "goal": "MINDANGLER e96-retry",
                       "schema": VERIFY_SCHEMA}])
(HOME / "fake.log").write_text("")
out = wf_run("e96-retry", {"FAKE_MODE": "min_blank_then_good"})
rec = rec_of(r, "j")
check("harvest: blank first answer is retried and the good retry commits done",
      rec.get("status") == "done" and rec.get("output") == {"verify_list": ["pytest -q"]},
      json.dumps(rec)[:200])
n_j = (HOME / "fake.log").read_text().count("e96-retry")
check("exactly two spawns (first refused, retry committed)", n_j == 2, f"spawns={n_j}")
prompts = sorted((r / "logs").glob("j.a*.prompt.md"), key=lambda p: p.name)
check("retry prompt names the min violation verbatim",
      len(prompts) == 2 and "schema validation" in prompts[1].read_text()
      and "expected at least 1 non-blank char(s)" in prompts[1].read_text(),
      prompts[1].read_text()[-300:] if len(prompts) == 2 else f"prompts={len(prompts)}")
check("first attempt's prompt carried the floors (schema_prompt_block dumps the schema dict)",
      prompts and '"minItems"' in prompts[0].read_text()
      and '"minLength"' in prompts[0].read_text())

# ============ 5. the shipped blind-council example refuses a blank list ============
ex = json.load(open(BUILD / "examples" / "review" / "blind-council.workflow.json"))
synth = [n for n in ex["nodes"] if n["id"] == "synthesis"][0]
vl = synth["schema"]["properties"]["verify_list"]
check("blind-council synthesis verify_list carries minItems:1 + item minLength:1",
      vl.get("minItems") == 1 and (vl.get("items") or {}).get("minLength") == 1,
      json.dumps(vl))
check("blind-council: the door accepts the hardened example (whole graph clean)",
      V(ex) == [], json.dumps(V(ex))[:300])
base = {"verdict": "ready", "risks": [], "minimal_fix": "", "seat_divergence": ""}
for blank in ([], [""], ["   "]):
    errs = wf.validate({**base, "verify_list": blank}, synth["schema"])
    check(f"blind-council synthesis refuses verify_list {blank!r} with a typed error",
          bool(errs), json.dumps(errs))
errs = wf.validate({**base, "verify_list": ["pytest -q"]}, synth["schema"])
check("blind-council synthesis accepts a real verify_list", errs == [], json.dumps(errs))

print()
if ok:
    print("ALL PASS")
else:
    print("FAILURES PRESENT")
    sys.exit(1)
