#!/usr/bin/env python3
"""est-6226 test B fixture: a synthetic "caller" (stands in for the gateway
seat) that spawns a runner through the door's OWN spawn seam and announces the
runner pid on stdout, then hangs — so the test can SIGTERM this caller's
process GROUP (the s6 gateway-restart wave shape) and see whether the wave
reaches the runner. Stdlib-only; run by test_gateway_sigterm_detach_6226.py.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

root, run_dir, _log = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, root)
spec = importlib.util.spec_from_file_location("hw6226_parent", Path(root) / "__init__.py")
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)

hw._spawn_runner(run_dir)
# announce the runner pid once the runner self-stamped (admission won)
import time
deadline = time.time() + 25
pid = None
while time.time() < deadline:
    try:
        pid = int((run_dir / "wf.pid").read_text().strip())
        if pid:
            break
    except (OSError, ValueError):
        time.sleep(0.05)
print(pid, flush=True)
try:
    with open(_log, "w") as f:
        json.dump({"spawned": pid}, f)
except OSError:
    pass
# hang as the caller — the test SIGTERMs our GROUP; a correct spawn means the
# runner is in its own session and this death cannot take it.
time.sleep(600)
