#!/usr/bin/env python3
"""est-6st - a reply that IS serialized tool-call markup must never coerce.

Field case (feedback ledger row 569586f70e1d1d51): a verify node attempt
ended with its FINAL REPLY as literal serialized tool-call markup,
turn_exit_reason unknown, exit 1. Under the sprint101 #9 tolerance in
extract_json a no-fence reply is coerced json.loads -> last_balanced_object
-> {result: text}: a tool-call-text reply therefore either commits as a
done answer through the {result: ...} shape (false green under any schema
that only requires a result string) or dies as untyped schema noise. The
fix is a typed classifier gate BEFORE all three coercion paths; the
fenced-json path stays byte-identical (fenced-json-first law).

Contracts proven here (RED before the fix):
 C1  a reply that IS serialized tool-call markup does NOT coerce:
     extract_json returns (None, error containing 'tool-call-as-text').
 C2  tool-call markup containing a real fenced json block: the FENCE wins -
     extract_json returns the parsed dict unchanged (fenced-json-first law).
 C3  a normal prose reply still coerces to {result: text} exactly as today
     (solo byte-identity of the sprint101 #9 tolerance).
 C4  a reply that merely mentions the words invoke/parameter in prose
     WITHOUT markup does not trip the classifier.
Style: plain asserts, PASS/FAIL lines, exit 0/1 (test_door.py house style).
Pure-function checks on extract_json - NO run spawns, no children.
"""
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))
import wf as wfmod  # noqa: E402

# Fixture strings are json-quoted literals so the file stays free of raw
# open-tag sequences a reply-serializer could re-parse as a live call.
TOOLCALL_REPLY = "<invoke name=\"terminal\">\n<parameter name=\"command\">{\"cmd\": \"pytest tests/\", \"verdict\": \"pushed\", \"suite\": \"TOTAL 122 FAIL 0\"}</parameter>\n</invoke>"
FENCE = "```json\n{\"verdict\": \"pushed\"}\n```"
TOOLCALL_WITH_FENCE = "<invoke name=\"browser_exec\">\n<parameter name=\"code\">\n```json\n{\"verdict\": \"pushed\"}\n```\n</parameter>\n</invoke>"
PROSE = "Done. The verdict is pushed and the suite is green with no failures."
PROSE_WORDS = "I will invoke the suite and pass the parameter --ci-out to it; the docs mention a function name in prose only."

ok = True
def check(label, cond, detail=""):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {label} {detail}")
    else:
        print(f"PASS {label}")

# ------------------------------------------------------------- C1
# The reply IS the serialized tool call (the model emitted the CALL markup as
# text). The parameter value carries a valid json object - last_balanced_object
# would happily harvest it - the exact false-green shape to refuse.
parsed, err = wfmod.extract_json(TOOLCALL_REPLY)
check("C1 refuses tool-call-as-text reply", parsed is None, f"parsed={parsed!r}")
check("C1 typed error names tool-call-as-text",
      err is not None and 'tool-call-as-text' in err, f"err={err!r}")

# ------------------------------------------------------------- C2
# fenced-json-first law: markup scaffolding that CONTAINS a parseable json
# fence still yields the fenced dict, byte-identical to the pure-fence path.
parsed2, err2 = wfmod.extract_json(TOOLCALL_WITH_FENCE)
check("C2 fenced json wins over markup", parsed2 == {"verdict": "pushed"},
      f"parsed={parsed2!r} err={err2!r}")
check("C2 fenced path error stays None", err2 is None, f"err={err2!r}")
parsed2b, err2b = wfmod.extract_json(FENCE)
check("C2 bare fence parses identically", parsed2 == parsed2b and err2b is None,
      f"bare={parsed2b!r}")

# ------------------------------------------------------------- C3
# solo regression: a normal prose reply still coerces exactly as today.
parsed3, err3 = wfmod.extract_json(PROSE)
check("C3 prose still coerces to result", parsed3 == {"result": PROSE},
      f"parsed={parsed3!r}")
check("C3 prose coercion error stays None", err3 is None, f"err={err3!r}")

# ------------------------------------------------------------- C4
# The words invoke/parameter in ordinary prose must NOT trip the gate.
parsed4, err4 = wfmod.extract_json(PROSE_WORDS)
check("C4 prose mention not tripped", parsed4 is not None and err4 is None,
      f"parsed={parsed4!r} err={err4!r}")

# the pure-function classifier, once present, agrees with the gate
if hasattr(wfmod, "_tool_call_as_text"):
    check("helper flags tool-call reply",
          bool(wfmod._tool_call_as_text(TOOLCALL_REPLY)))
    check("helper ignores prose", not wfmod._tool_call_as_text(PROSE))
    check("helper ignores word-mention prose",
          not wfmod._tool_call_as_text(PROSE_WORDS))

print("RESULT", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
