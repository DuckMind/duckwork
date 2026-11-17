#!/usr/bin/env python3
"""est-px11 / PR #122 re-review pin: decoder MemoryError must be CONTAINED.

The #111 rewrite replaced the parent scanner's `except Exception` with
`(ValueError, RecursionError)` at the raw_decode seam. The committee measured
(4/4 on 3.12.13 + 3.14.7) that json's C decoder can also raise MemoryError —
a plain Exception, neither of the two — under an RLIMIT_AS ceiling at parse
entry with an already-resident flat 1M-zero candidate + shallow trailing
{"ok":true}: head died where clean main returned {"ok": true}. The tuple now
carries MemoryError; the pre-#111 containment is restored at the seam.

Honest limits (carried from the committee): pressure-dependent regression,
end-to-end node death not deterministically reproduced through the runner.
This pin therefore runs the SAME pressure deterministically in a spawn
(fixed headroom, no mocks, unmocked decoder), and asserts the containment
property, not a race.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME /opt/duckwork/.venv/bin/python tests/test_px11_memoryerror_containment.py
"""
import os, subprocess, sys, textwrap
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
FAILED = 0

def ok(cond, name, extra=""):
    global FAILED
    print(("PASS" if cond else "FAIL"), name, extra)
    FAILED += 0 if cond else 1

# Deterministic pressure probe: set the RLIMIT_AS ceiling at PARSE ENTRY
# (VM_SIZE headroom, not RSS: RLIMIT_AS counts virtual size), unmocked
# decoder, resident 1M-zero flat candidate + shallow trailing object.
PROBE = textwrap.dedent("""
    import json, resource, sys, os
    sys.path.insert(0, {build!r})
    import wf
    def vsize_kb():
        for l in open(f"/proc/{{os.getpid()}}/status"):
            if l.startswith("VmSize"): return int(l.split()[1])
    cand = '{{"x":[' + ",".join(["0"] * 1_000_000) + ']}} then {{"ok":true}}'
    headroom_mb = int(sys.argv[1])
    ceil = (vsize_kb() + headroom_mb * 1024) * 1024
    resource.setrlimit(resource.RLIMIT_AS, (ceil, resource.RLIM_INFINITY))
    try:
        fn = wf.last_balanced_object if sys.argv[2] == "lbo" else wf.extract_json
        got = fn(cand)
        print("RESULT", repr(got)[:80])
    except BaseException as e:
        print("ESCAPED", type(e).__name__)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY,) * 2)
""")

def run_probe(headroom_mb, which):
    p = subprocess.run(
        [sys.executable, "-c", PROBE.format(build=str(BUILD)), str(headroom_mb), which],
        capture_output=True, text=True, timeout=240)
    return p.stdout.strip()

# T1: the exact measured pressure point (8MB headroom ESCAPED MemoryError at
# the pre-fix tuple; committee's fixture shape) — containment returns the
# trailing shallow object, exactly like clean main.
out = run_probe(8, "lbo")
ok(out.startswith("RESULT") and "{'ok': True}" in out,
   "T1 last_balanced_object contained under 8MB parse-entry pressure", out[:70])

# T2: same candidate through the public entry point (extract_json: the
# prose fallback path the node actually walks).
out2 = run_probe(8, "extract")
ok(out2.startswith("RESULT"), "T2 extract_json contained under same pressure", out2[:70])

# T3: no-pressure semantics unchanged — containment must not have altered
# the #111 laws (last object wins; broken earlier never hides good later).
sys.path.insert(0, str(BUILD))
import wf  # noqa: E402
ok(wf.last_balanced_object('noise {"a":1} ``` {"b":{"c":2}} tail') == {"b": {"c": 2}},
   "T3 last top-level object wins (unchanged #111)")
ok(wf.last_balanced_object('{"broken": [1,2 oops {"good":true} tail') == {"good": True},
   "T4 broken earlier candidate never hides a good later one")
ok(wf.last_balanced_object("no json at all") is None, "T5 no candidate -> None")

# T6: the containment is BEHAVIORAL, not textual — T1/T2 already prove the
# seam swallows the decoder's MemoryError at the measured pressure point
# (red-proof: the pre-fix (ValueError, RecursionError) tuple ESCAPED it 4/4 on
# 3.12.13 + 3.14.7, where clean main returned {"ok": true}). Deleting any
# member of the tuple re-drops T1/T2 to FAIL/ESCAPED, so an assertion that
# READS the production source text here would be theater that could stay
# green over a broken machine gate. Per CONTRIBUTING.md §R6 we pin the
# behavior and leave the bytes alone.
out3 = run_probe(8, "extract")
ok(out3.startswith("RESULT") and "ESCAPED" not in out3,
   "T6 no exception class escapes the public entry under sustained pressure", out3[:70])

print("px11:", "FAIL" if FAILED else "PASS")
sys.exit(1 if FAILED else 0)
