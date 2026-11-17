#!/usr/bin/env python3
"""A stop arriving inside an adopted child's liveness probe stays cancelled."""
import json
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf

ok = True
for capture in ("", '```json\n{"result":"answer before stop"}\n```\n'):
    with tempfile.TemporaryDirectory(prefix="wf-adopt-stop-race-") as home:
        run = Path(home)
        (run / "nodes").mkdir()
        lp = run / "child.log"
        lp.write_text(capture)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 start_new_session=True)
        stop = threading.Event()
        meta = {"_run": run, "_stop": stop, "_procs": {},
                "_procs_lock": threading.Lock(), "node_timeout": 30}
        node = {"id": "fan", "type": "agent"}
        rec = {"pid": child.pid, "started": datetime.now(timezone.utc).isoformat(),
               "log_path": str(lp), "status": "running", "attempt": 0,
               "skey": "wf:stop-race:fan:0:test#a0"}
        (run / "nodes" / "fan.0.json").write_text(json.dumps(rec))
        alive = wf._proc_alive

        def stopped_during_probe(pid):
            # The monitor already observed stop=false. The watcher now sets
            # stop and kills its registered child before this probe returns.
            assert pid == child.pid and not stop.is_set()
            assert any(handle.pid == pid for handle in meta["_procs"].values())
            stop.set()
            wf._kill_adopted(pid)
            child.wait(timeout=5)
            return alive(pid)

        try:
            with patch.object(wf, "_proc_alive", side_effect=stopped_during_probe):
                result = wf._adopt_child(meta, node, {"fan": node}, 0, rec,
                                        {"type": "object", "required": ["result"]})
            passed = (result.get("status") == "failed"
                      and result.get("error_class") == "cancelled"
                      and not meta["_procs"]
                      and child.returncode == -signal.SIGKILL)
            print(("PASS " if passed else "FAIL ")
                  + ("buffered answer" if capture else "empty capture")
                  + " stop inside liveness probe is cancelled", result)
            ok = ok and passed
        finally:
            if child.poll() is None:
                wf._kill_adopted(child.pid)
            child.wait(timeout=5)

print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
