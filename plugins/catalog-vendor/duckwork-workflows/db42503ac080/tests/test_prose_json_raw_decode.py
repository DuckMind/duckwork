"""#111 (audit WF-01): prose-wrapped JSON must never silently promote a nested
item to the whole result. The last_balanced_object fallback now attempts
json.JSONDecoder.raw_decode at each '{' candidate and resumes at the consumed
end position, so an accepted parent swallows its children and the [-200:]
candidate cap is gone.
Style: plain asserts, PASS/FAIL lines, exit 0/1 (test_door.py / C2-prompt).
"""
import importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

spec = importlib.util.spec_from_file_location("hwf_111", BUILD / "wf.py")
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

# (a) the regression: 199/200/201/500 nested objects under prose must survive whole
for n in (199, 200, 201, 500):
    expected = {"items": [{"i": i} for i in range(n)]}
    actual, error = W.extract_json("Result follows\n" + json.dumps(expected))
    check(f"#111 n={n} nested-object stream preserved intact",
          actual == expected and error is None,
          f"got {'full result' if actual == expected else repr(actual)[:60]} err={error}")

# (b) escaped quotes/braces inside strings
p, e = W.extract_json('answer: {"s": "has { brace } inside"} end')
check("#111 braces inside strings parsed by the decoder",
      p == {"s": "has { brace } inside"} and e is None, f"{p} {e}")

# (c) multiple complete top-level results -> last wins (existing #9 law)
p, _ = W.extract_json('first {"a": 1} then {"b": 2} tail')
check("#111 two top-level objects -> LAST one wins", p == {"b": 2}, p)

# (d) malformed earlier candidate never hides a valid later one
p, _ = W.extract_json('prose {not json at all} tail {"ok": true}')
check("#111 invalid candidate skipped, later valid one extracted", p == {"ok": True}, p)

# (e) broken json fence followed by a valid object -> the object (not {result} fallback)
p, _ = W.extract_json("noise\n```json\n{broken,,\n```\nbut here is my real answer:\n{\"k\": \"v\"}\ndone")
check("#111 broken fence + valid trailing object -> object extracted", p == {"k": "v"}, p)

# (f) no braces -> unchanged {result} fallback
p, e = W.extract_json("truly no braces here at all")
check("#111 no object anywhere -> unchanged {result} fallback",
      p == {"result": "truly no braces here at all"} and e is None, f"{p} {e}")

# (g) empty -> unchanged (None, err)
p, e = W.extract_json("")
check("#111 empty stdout -> unchanged (None, err)",
      p is None and e == "no json fence found", f"{p} {e}")

# (h) nested + stray trailing brace tolerated (existing #9 law)
p, _ = W.extract_json('{"outer": {"inner": 1}} trailing}')
check("#111 nested object extracted; stray trailing brace tolerated",
      p == {"outer": {"inner": 1}}, p)

sys.exit(0 if ok else 1)
