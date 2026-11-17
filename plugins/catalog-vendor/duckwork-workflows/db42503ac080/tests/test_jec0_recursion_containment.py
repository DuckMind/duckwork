#!/usr/bin/env python3
"""est-jec0 / PR #122 B1 pin: the prose-JSON fallback must never crash the node.

`json.JSONDecoder.raw_decode` raises RecursionError (a RuntimeError, NOT a
ValueError) on pathologically nested candidates. The #111 rewrite narrowed the
containment to `except ValueError` and the committee re-proved the node death
on CI's own 3.12 interpreter. This pin runs the committee's exact fixture and
asserts (a) no exception escapes, (b) containment matches the pre-#111 parent
scanner (later good objects still found), (c) the normal-path semantics of
#111 (last top-level object wins, accepted parents swallow children) hold.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wf import last_balanced_object

FAILED = 0
def ok(cond, name, extra=""):
    global FAILED
    print(("PASS" if cond else "FAIL"), name, extra)
    FAILED += 0 if cond else 1

# --- the committee's exact B1 fixture (wf.py:279-282 shape) ---------------
fixture = 'Result follows\n{"x":' + "[" * 10000 + "0" + "]" * 10000 + '} then {"ok":true}'

try:
    got = last_balanced_object(fixture)
    crashed = None
except RecursionError as e:
    got, crashed = None, e

ok(crashed is None, "T1 pathological nesting does not escape (RecursionError containment)")
ok(got == {"ok": True}, "T2 containment equals pre-#111 parent scanner", f"got={got!r}")

# --- #111 semantics unchanged ----------------------------------------------
ok(last_balanced_object('noise {"a":1} fence ``` {"b":{"c":2}} tail') == {"b": {"c": 2}},
   "T3 last top-level object wins (parent, not nested item)")
ok(last_balanced_object('{"broken": [1,2 oops {"good":true} tail') == {"good": True},
   "T4 broken earlier candidate never hides a good later one")
ok(last_balanced_object("no json at all") is None, "T5 no candidate -> None")
ok(last_balanced_object("") is None and last_balanced_object(None) is None,
   "T6 empty/None input -> None")

# --- nesting that is too deep for CI's 3.12 (raises there, decodes on 3.14) -
# the pin is interpreter-honest: whatever the decoder's headroom, the fallback
# either decodes the candidate or skips it — it never lets an exception escape.
only_bad = '{"x":' + "[" * 20000 + "0" + "]" * 20000 + "}"
try:
    got2 = last_balanced_object(only_bad)
    crashed2 = None
except RecursionError as e:
    got2, crashed2 = None, e
ok(crashed2 is None and (got2 is None or isinstance(got2, dict)),
   "T7 undecodable-under-headroom -> None, decodable -> dict; never a crash")

print("jec0:", "FAIL" if FAILED else "PASS")
sys.exit(1 if FAILED else 0)
