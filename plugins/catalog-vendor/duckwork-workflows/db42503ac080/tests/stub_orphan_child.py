#!/usr/bin/env python3
"""Stub duckwork_bin for test_orphan_adopt_790c6ad — the live-orphan repro child.

Prints its pid to $FAKE_LOG (one line per spawn; the test counts lines to
prove NO re-spawn happened), keeps the session title token in its OWN argv
(the runner passes `--continue <skey>#a<n>` — that is the PID-reuse guard the
adoption law verifies), flushes a progress line, then sleeps, then prints the
fenced answer and exits 0 — a child that outlives its runner and finishes on
its own, exactly the waveA3 shape.
"""
import os, sys, time

args = sys.argv[1:]
q = ""
if "--query-file" in args:
    try:
        q = open(args[args.index("--query-file") + 1]).read()
    except OSError:
        q = ""
with open(os.environ.get("FAKE_LOG", os.devnull), "a") as f:
    f.write(str(os.getpid()) + "\n")
print("stub child cooking", flush=True)          # log exists -> not a silent spawn
time.sleep(float(os.environ.get("STUB_SLEEP", "6")))
item = ""
for line in (q or "").splitlines():
    if line.strip():
        item = line.strip()[:80]
        break
print("```json\n" + "{\"result\": \"done:" + item.replace('"', "'") + "\", \"goal\": \"" + item.replace('"', "'") + "\"}\n```")
sys.exit(0)
