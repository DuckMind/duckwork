#!/usr/bin/env python3
"""#113 — validate() must split integer from number and reject booleans.

Before the fix the single predicate at wf.py:315 treated the two admitted
numeric type names as one: `t in ("number", "integer") and not isinstance(v,
(int, float))`. Consequences, all observed from the production function at
main tip a4a5266: 1.5 passed as an integer, and True/False passed as EITHER
numeric type (Python bools are int subclasses). The types are advertised
constraints — wfcommon's schema admission accepts both names — so the
enforcement is wrong, not merely loose.

Contract asserted here (per the issue, per modern JSON Schema):
  * `integer` accepts int and INTEGRAL-VALUED float — 1.0 is a valid integer,
    the same contract json-schema.org documents ("1.0 is an integer");
    fractional floats (1.5) are rejected;
  * `number` accepts int and float but NOT bool — True is never a number;
  * no coercion: "3" stays rejected for both;
  * every error names the key path (dotted for properties, indexed for items);
  * the harvested fake-child path refuses an invalid typed answer: the retry
    names the defect, a persistent violation ends the node error_class=schema
    and the answer NEVER commits done.

Minimal-fix law (#113): no jsonschema, no framework, the type names stay
admitted at the door; the fix is the one predicate.
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
HOME = HERE / "home113"
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

# ============ 0. the issue's exact repro: the PRODUCTION validate() ============
# Bind the shipped production function directly (wf is imported above; same
# function the runner's harvest uses). CONTRIBUTING.md R6: tests call the
# production API — no reading wf.py as source text / exec'ing an AST excerpt.
_prod_validate = wf.validate

for value, kind in [(1.5, "integer"), (True, "integer"),
                    (True, "number"), (False, "number")]:
    check(f"repro: {value!r} as {kind!r} is REJECTED (was [] before the fix)",
          _prod_validate(value, {"type": kind}) != [],
          f"validate({value!r}, {{'type': {kind!r}}}) = {_prod_validate(value, {'type': kind})}")

# ============ 1. integer: int and integral-valued float, no fractional ============
INT = {"type": "integer"}
check("integer: plain int stays valid (no over-tightening)",
      wf.validate(1, INT) == [])
check("integer: integral-valued float 1.0 is a valid integer (modern JSON Schema "
      "contract — '1.0 is an integer' per json-schema.org; rejecting it would be "
      "an unnecessary semantic restriction)",
      wf.validate(1.0, INT) == [], wf.validate(1.0, INT))
check("integer: fractional float 1.5 rejected naming the path",
      wf.validate(1.5, INT) == ["$: expected number"], wf.validate(1.5, INT))
check("integer: negative fractional float rejected too",
      wf.validate(-2.5, INT) == ["$: expected number"], wf.validate(-2.5, INT))
check("integer: integral negative float accepted",
      wf.validate(-3.0, INT) == [])

# ============ 2. number: int and float, never bool ============
NUM = {"type": "number"}
check("number: int stays valid", wf.validate(1, NUM) == [])
check("number: fractional float stays valid (2.5 as number — no over-tightening)",
      wf.validate(2.5, NUM) == [])
check("number: True rejected", wf.validate(True, NUM) == ["$: expected number"],
      wf.validate(True, NUM))
check("number: False rejected", wf.validate(False, NUM) == ["$: expected number"],
      wf.validate(False, NUM))

# ============ 3. no coercion: strings never numeric-pass ============
check("integer: numeric string still rejected (control)",
      wf.validate("3", INT) == ["$: expected number"], wf.validate("3", INT))
check("number: numeric string still rejected (control)",
      wf.validate("2.5", NUM) == ["$: expected number"], wf.validate("2.5", NUM))

# ============ 4. nested: dotted property paths, indexed item paths ============
check("nested properties: violation names the dotted path",
      wf.validate({"count": 1.5},
                  {"type": "object", "properties": {"count": INT}})
      == ["$.count: expected number"],
      wf.validate({"count": 1.5}, {"type": "object", "properties": {"count": INT}}))
check("nested properties: bool violation names the dotted path",
      wf.validate({"count": True},
                  {"type": "object", "properties": {"count": INT}})
      == ["$.count: expected number"],
      wf.validate({"count": True}, {"type": "object", "properties": {"count": INT}}))
check("array items: violation names the indexed path",
      wf.validate([1.5], {"type": "array", "items": INT}) == ["$[0]: expected number"],
      wf.validate([1.5], {"type": "array", "items": INT}))
check("array items: valid ints + integral floats pass, fractional item refused at index",
      wf.validate([1, 2.0, 1.5], {"type": "array", "items": INT}) == ["$[2]: expected number"],
      wf.validate([1, 2.0, 1.5], {"type": "array", "items": INT}))

# ============ 5. the door still admits both type names (subset unchanged) ====
def agent_node(schema):
    return [{"id": "a", "type": "agent", "goal": "g", "schema": schema}]
check("door: integer/number stay admitted (no admission change per the minimal-fix law)",
      V(agent_node({"type": "object", "properties": {
          "i": {"type": "integer"}, "n": {"type": "number"}}})) == [],
      json.dumps(V(agent_node({"type": "object", "properties": {
          "i": {"type": "integer"}, "n": {"type": "number"}}}))))

# ============ 6. fake-child contract: an invalid typed answer never commits ==
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

def exit_reason(r):
    p = r / "runner_exit.json"
    return json.loads(p.read_text()).get("reason", "") if p.exists() else ""

COUNT_SCHEMA = {"type": "object", "required": ["count"],
                "properties": {"count": {"type": "integer"}}}

# 6a. 1.5-as-integer first answer is REFUSED, retry names the defect, fixed
# answer commits — the invalid answer must never commit as done.
r = mk("e113-retry", [{"id": "j", "type": "agent", "goal": "NUMTEST e113-retry",
                       "schema": COUNT_SCHEMA}])
(HOME / "fake.log").write_text("")
wf_run("e113-retry", {"FAKE_MODE": "num_out_then_in"})
rec = rec_of(r, "j")
check("harvest: fractional answer to an integer field is refused; only the corrected "
      "retry commits done",
      rec.get("status") == "done" and rec.get("output") == {"count": 2},
      json.dumps(rec)[:200])
n_j = (HOME / "fake.log").read_text().count("e113-retry")
check("exactly two spawns (first refused, retry committed)", n_j == 2, f"spawns={n_j}")
prompts = sorted((r / "logs").glob("j.a*.prompt.md"), key=lambda p: p.name)
check("retry prompt names the violation and its path",
      len(prompts) == 2 and "failed schema validation" in prompts[1].read_text()
      and "$.count: expected number" in prompts[1].read_text(),
      prompts[1].read_text()[-300:] if len(prompts) == 2 else f"prompts={len(prompts)}")

# 6b. persistent violation ends the node exactly like every other schema violation
r = mk("e113-persist", [{"id": "k", "type": "agent", "goal": "NUMTEST e113-persist",
                         "schema": COUNT_SCHEMA}])
wf_run("e113-persist", {"FAKE_MODE": "num_always_bad"})
rec = rec_of(r, "k")
check("harvest: a persistently invalid typed answer ends the node error_class=schema, "
      "never done",
      rec.get("status") == "failed" and rec.get("error_class") == "schema"
      and "failed schema validation" in rec.get("error", "")
      and "$.count: expected number" in rec.get("error", ""),
      json.dumps(rec)[:220])
n_k = (HOME / "fake.log").read_text().count("e113-persist")
check("persistent violation used exactly the two attempts the type path uses",
      n_k == 2, f"spawns={n_k}")
check("run blocked on the failed node (same shape as the enum/bad_schema classes)",
      exit_reason(r) == "blocked by failed k", exit_reason(r))

# 6c. bool-as-integer harvest refusal: True is never an accepted integer answer
r = mk("e113-bool", [{"id": "m", "type": "agent", "goal": "NUMTEST e113-bool",
                      "schema": COUNT_SCHEMA}])
wf_run("e113-bool", {"FAKE_MODE": "num_bool_always_bad"})
rec = rec_of(r, "m")
check("harvest: a bool answer to an integer field never commits done (error_class=schema)",
      rec.get("status") == "failed" and rec.get("error_class") == "schema"
      and "$.count: expected number" in rec.get("error", ""),
      json.dumps(rec)[:220])

# 6d. a valid first answer commits on the first attempt — no extra spawn
r = mk("e113-clean", [{"id": "c", "type": "agent", "goal": "NUMTEST e113-clean",
                       "schema": COUNT_SCHEMA}])
(HOME / "fake.log").write_text("")
wf_run("e113-clean", {"FAKE_MODE": "num_always_good"})
rec = rec_of(r, "c")
check("harvest: valid integer commits on the first attempt",
      rec.get("status") == "done" and rec.get("output") == {"count": 3}
      and (HOME / "fake.log").read_text().count("e113-clean") == 1,
      json.dumps(rec)[:160])

print()
if ok:
    print("ALL PASS")
else:
    print("FAILURES PRESENT")
    sys.exit(1)
