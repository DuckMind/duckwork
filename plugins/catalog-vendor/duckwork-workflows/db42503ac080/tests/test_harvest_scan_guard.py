"""est-gg96: the prose-JSON fallback scan must be size-guarded.

#111 removed the [-200:] candidate cap (correct — the cap caused #111), but it
incidentally bounded scan cost. Measured on unmatched-brace runs: 906KB of
pseudo-JSON with no parseable object takes ~14 s; 400 KB of braces ~53 s.
node timeout wraps communicate(), not parse, so the scan cost is unbounded and
reachable via no-fence child stdout, once per attempt.

Guard law: when the WHOLE text is oversized (len > WF_HARVEST_SCAN_MAX_BYTES,
default 256 KiB) and carries NO decodable fence, skip the fallback scan and take
the honest {result} path — never scan candidates by a COUNT cap (that drops
parents, the #111 law stands). Small and fenced inputs are byte-identical.
"""
import json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import wf  # noqa: E402

FAILS = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)

LIMIT = wf.HARVEST_SCAN_MAX_BYTES

# 1. RED: an oversized no-parseable-object blob must return fast via {result}
big = "}{ \"ok\": tru e, " * 40000          # ~1 MB of unmatched-brace pseudo-JSON
assert len(big) > LIMIT, f"fixture too small: {len(big)}"
t0 = time.monotonic()
obj, err = wf.extract_json(big)
dt = time.monotonic() - t0
check("oversized no-object blob returns {result} (honest fallback)",
      obj == {"result": big.strip()} and err is None, f"obj={str(obj)[:80]} err={err}")
check(f"oversized scan is bounded by guard (took {dt:.3f}s)", dt < 2.0, f"{dt:.3f}s")

# 2. guard limit is a real env-tunable and honest about itself
os.environ["WF_HARVEST_SCAN_MAX_BYTES"] = "1000"
try:
    import importlib
    importlib.reload(wf)
    check("env tunable moves the limit", wf.HARVEST_SCAN_MAX_BYTES == 1000)
    medium = "}{ x, " * 400               # > 1000 bytes, no object
    t0 = time.monotonic()
    obj2, _ = wf.extract_json(medium)
    check("under a lowered cap the scan is skipped -> {result}",
          obj2 == {"result": medium.strip()}, str(obj2)[:80])
finally:
    os.environ.pop("WF_HARVEST_SCAN_MAX_BYTES", None)
    importlib.reload(wf)

# 3. Fenced oversized text still harvests: the fence parse short-circuits the scan
fenced = "noise " * 60000 + "```json\n" + json.dumps({"result": "ok", "n": 7}) + "\n```"
assert len(fenced) > LIMIT
obj3, err3 = wf.extract_json(fenced)
check("oversized but fenced still parses the fence",
      obj3 == {"result": "ok", "n": 7} and err3 is None, f"{str(obj3)[:80]} {err3}")

# 4. regression: small prose-wrapped object still harvested (the #111/#9 law)
obj4, err4 = wf.extract_json('chat chat {"a": 1} trailing prose {oops')
check("small prose-wrapped object still harvested", obj4 == {"a": 1} and err4 is None, str(obj4))

# 5. regression: nested parent not shadowed by child (the #111 law, small input)
obj5, _ = wf.extract_json('x {"outer": {"inner": 1}, "keep": true} y {bad')
check("parent object survives (no count cap)", obj5 == {"outer": {"inner": 1}, "keep": True}, str(obj5))

print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)} ({7 - len(FAILS)}/7)")
sys.exit(1 if FAILS else 0)
