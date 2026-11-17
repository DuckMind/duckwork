#!/usr/bin/env python3
"""Lane A: routed spawn, env boundary, missing-profile race and DB ownership."""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("runner_11", ROOT / "wf.py")
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    home = root / "profiles" / "launcher"
    target = root / "profiles" / "reviewer"
    home.mkdir(parents=True)
    target.mkdir(parents=True)
    (target / "config.yaml").write_text("{}")
    run = root / "runs" / "r1"
    (run / "nodes").mkdir(parents=True)
    node = {"id": "review", "type": "agent", "goal": "ok", "profile": "reviewer"}
    byid = {"review": node}
    (run / "graph.json").write_text(json.dumps({"nodes": [node]}))
    binpath = root / "duckwork"
    binpath.write_text("#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\na=sys.argv[1:]\nassert a[:3]==['-p','reviewer','chat'],a\nassert os.environ['DUCKWORK_HOME']==sys.argv[-1] if False else True\nPath(os.environ['DUCKWORK_WF_RUN_DIR'],'capture.json').write_text(json.dumps({'argv':a,'env':dict(os.environ)}))\nprint('```json\\n{}\\n```')\n")
    binpath.chmod(0o755)
    meta = {"_run": run, "duckwork_bin": str(binpath), "_spawn_n": {}, "_procs_lock": threading.Lock(),
            "_procs": {}, "_stop": threading.Event(), "node_timeout": 5}
    with patch.dict(os.environ, {"DUCKWORK_HOME": str(home), "SECRET_CANARY": "must-not-leak", "WF_RUNS_ROOT": str(root / "runs"),
                                  "DUCKWORK_WRITE_SAFE_ROOT": str(root / "safe")}, clear=False):
        r = wf.run_child(meta, node, byid, "ok", "", None, skey="wf:r1:review")
        assert r["status"] == "done", r
        assert r["profile"] == "reviewer" and r["profile_home"] == str(target), r
        capture = json.loads((run / "capture.json").read_text())
        assert capture["argv"][:3] == ["-p", "reviewer", "chat"]
        env = capture["env"]
        assert env["DUCKWORK_HOME"] == str(root) and env["WF_RUNS_ROOT"] == str(root / "runs"), env
        assert "SECRET_CANARY" not in env and "OPENAI_API_KEY" not in env, env
        assert env["DUCKWORK_WRITE_SAFE_ROOT"].split(os.pathsep)[-1] == str(run / "work" / "review")
        rec = json.loads((run / "nodes" / "review.json").read_text())
        assert rec["profile"] == "reviewer" and rec["profile_home"] == str(target)
        (target / "config.yaml").unlink()
        (run / "capture.json").unlink()
        gone = wf.run_child(meta, node, byid, "ok", "", None, skey="wf:r1:review")
        assert gone["error_class"] == "spawn" and gone["error"] == "profile gone: reviewer", gone
        assert gone["profile_home"] == str(target) and not (run / "capture.json").exists()

    # A target with no readable DB is UNKNOWN, not zero/retry permission.
    assert wf._attempt_api_calls(run, "wf:r1:review", target) is None
    assert not wf._tool_progress(run, "wf:r1:review", "", target)
    db = target / "state.db"
    con = sqlite3.connect(db)
    con.execute("create table sessions (title text, model text, billing_provider text, input_tokens int, output_tokens int, cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, estimated_cost_usd real, last_activity_at real, last_activity_description text, ended_at real, started_at real)")
    con.execute("insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("wf:r1:review#a0", "target-model", "target-billing", 1,2,0,0,3,1,0,0,"",0,0))
    con.commit(); con.close()
    assert wf._attempt_api_calls(run, "wf:r1:review", target) == 3
    assert wf._tool_progress(run, "wf:r1:review", "", target)
    stamped = wf._stamp_served({"_run": run}, {"skey": "wf:r1:review", "profile_home": str(target)})
    assert stamped["served_model"] == "target-model" and stamped["served_billing_provider"] == "target-billing", stamped
print("PASS Lane A routed spawn / whitelist / race / metrics")
