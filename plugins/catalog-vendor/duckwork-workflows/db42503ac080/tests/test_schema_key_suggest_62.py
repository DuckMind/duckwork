#!/usr/bin/env python3
"""est-2ek.1.62 - validate() names the fuzzy sibling-key rename on missing-required
so the typed-correction retry CONVERGES instead of re-emitting the same shape.

Repro class (from the report): a node whose JSON was complete and correct FAILED schema
because it used sibling key names (mean_ranking vs mean_rank). The engine's
only feedback was the bare "missing required \'<r>\'" (wf.py:1017 at the base
SHA), so the -Q child re-emitted the same shape and the node died
error_class=schema.

Observable contract (plan spec):
  * when the object carries EXTRA keys the schema doesn't name, and one is
    close to the missing required name, the error names the rename explicitly:
    "missing required 'id' (you wrote 'proposal'? the schema needs 'id')"
    (the plan's own worked example - a pure difflib ratio never fires for the
    id/proposal pair, ratio 0.0, so the closeness rule adds containment: a
    short required name that is a substring of the extra key; get_close_matches
    n=1 cutoff 0.6 covers the mean_rank/mean_ranking class);
  * the SAME error string flows verbatim into the existing typed-correction
    retry prompt - no new retry or spawn-path edit;
  * non-suggestion error strings stay BYTE-IDENTICAL to today's form:
    missing with unrelated extras => unchanged; no extras => unchanged;
  * type-consistency guard: a close-name whose value type CONTRADICTS the
    required property's declared type gets NO suggestion - never recommend a
    rename that would still fail the type check. When the schema declares no
    type for the required property, any sibling value is consistent.

Pure-function test: no spawn, no network, stdlib only (R4). validate()-only
change - callers (spawn sites, _harvest_cancelled) pass the strings through.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
os.environ.setdefault("DUCKWORK_HOME", str(HERE / ".suite-home"))
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402  (wf.py is stdlib-only and importable)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  << {detail}"))
    ok = ok and bool(cond)

BARE = "$: missing required 'id'"

# 1. THE rename case - the worked example: missing 'id', extra 'proposal'
#    (same value type: schema wants string, the sibling value is a string).
#    The error must name BOTH keys so the retry can converge.
schema_id = {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}
errs = wf.validate({"proposal": "adopt the retry"}, schema_id)
check("missing 'id' with extra 'proposal' names BOTH keys",
      len(errs) == 1
      and "missing required 'id'" in errs[0]
      and "proposal" in errs[0] and "id" in errs[0],
      errs)
check("the rename reads as a rename: 'you wrote 'proposal'?' ... \"needs 'id'\"",
      len(errs) == 1
      and "you wrote 'proposal'" in errs[0] and "needs 'id'" in errs[0],
      errs)
check("suggestion is APPENDED - the base error string is a prefix, unchanged",
      len(errs) == 1 and errs[0].startswith(BARE), errs)

# 1b. the mean_ranking class - difflib fires at cutoff 0.6 (ratio ~0.86)
schema_rank = {"type": "object", "required": ["mean_rank"],
               "properties": {"mean_rank": {"type": "number"}}}
errs = wf.validate({"mean_ranking": 2.5}, schema_rank)
check("missing 'mean_rank' with extra 'mean_ranking' names both keys",
      len(errs) == 1
      and "missing required 'mean_rank'" in errs[0]
      and "you wrote 'mean_ranking'" in errs[0] and "needs 'mean_rank'" in errs[0],
      errs)

# 2. BYTE-IDENTICAL non-suggestion paths (the #107 byte-stability law).
classic = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
check("no extras => byte-identical to today's form",
      wf.validate({}, classic) == ["$: missing required 'answer'"],
      wf.validate({}, classic))
check("missing with UNRELATED extras => byte-identical to today's form",
      wf.validate({"summary": "s", "rationale": "r"}, classic)
      == ["$: missing required 'answer'"],
      wf.validate({"summary": "s", "rationale": "r"}, classic))
check("close-name that is a KEY THE SCHEMA NAMES (unfilled property) => no suggestion",
      wf.validate({"verdict": "x"},
                  {"type": "object", "required": ["answer"],
                   "properties": {"answer": {"type": "string"},
                                  "verdict": {"type": "string"}}})
      == ["$: missing required 'answer'"],
      wf.validate({"verdict": "x"},
                  {"type": "object", "required": ["answer"],
                   "properties": {"answer": {"type": "string"},
                                  "verdict": {"type": "string"}}}))

# 3. TYPE-CONSISTENCY GUARD - never recommend a rename that would still fail.
#    Required 'id' is typed string; the sibling 'idd' carries an INT: renaming
#    it would pass required and die on the type check, so stay silent.
schema_typed = {"type": "object", "required": ["id"],
                "properties": {"id": {"type": "string"}}}
errs = wf.validate({"idd": 7}, schema_typed)
check("close name whose value type CONTRADICTS the required property's type => no suggestion",
      errs == [BARE], errs)
errs = wf.validate({"idd": "text"}, schema_typed)
check("same sibling once the value type MATCHES => suggestion appears",
      len(errs) == 1 and "you wrote 'idd'" in errs[0], errs)
# boolean is not a number for schema purposes (#113 law reused here)
errs = wf.validate({"idd": True}, {"type": "object", "required": ["id"],
                                   "properties": {"id": {"type": "number"}}})
check("bool value never 'matches' a number-typed required (no suggestion)",
      errs == [BARE], errs)
# no declared type for the required property => any sibling value is consistent
errs = wf.validate({"idd": {"deep": 1}}, {"type": "object", "required": ["id"]})
check("undeclared required type => suggestion allowed (nothing left to contradict)",
      len(errs) == 1 and "you wrote 'idd'" in errs[0], errs)

# 4. nested path: required missing inside an array item names the rename too
schema_nested = {"type": "array", "items": {"type": "object", "required": ["id"],
                                            "properties": {"id": {"type": "string"}}}}
errs = wf.validate([{"id": "a"}, {"proposal": "b"}], schema_nested)
check("nested item rename suggestion carries the indexed path",
      len(errs) == 1 and errs[0].startswith("$[1]: missing required 'id'")
      and "you wrote 'proposal'" in errs[0], errs)

# 5. multiple missing requireds: only the ones with a close sibling get a
#    suggestion; the others stay byte-identical, and order follows `required`.
schema_two = {"type": "object", "required": ["id", "verdict"],
              "properties": {"id": {"type": "string"}, "verdict": {"type": "string"}}}
errs = wf.validate({"idd": "x"}, schema_two)
check("two missing, one close sibling => one suggestion + one bare error, byte-identical",
      len(errs) == 2
      and "you wrote 'idd'" in errs[0] and errs[0].startswith(BARE)
      and errs[1] == "$: missing required 'verdict'",
      errs)

print()
if ok:
    print("ALL PASS")
else:
    print("FAILURES PRESENT")
    sys.exit(1)
