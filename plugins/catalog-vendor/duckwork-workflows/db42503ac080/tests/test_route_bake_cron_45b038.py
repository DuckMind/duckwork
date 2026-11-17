#!/usr/bin/env python3
"""45b038: cron's core-less interpreter must still bake a proved pinned route.

The fake launcher owns a sibling Python interpreter, as a venv's bin/ directory
does. Its isolated auxiliary client records the single explicit-route call. No
network or live seat is used. The runner spawn spy reads the committed graph,
proving the bake is on disk before any child could start.
"""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import wf_test_isolation

failures = 0
def check(label, ok, detail=""):
    global failures
    print(("PASS " if ok else "FAIL ") + label + (" " + str(detail) if not ok else ""))
    failures += not ok

with tempfile.TemporaryDirectory(prefix="wf-route-cron-") as scratch:
    home = Path(scratch)
    os.environ["DUCKWORK_HOME"] = str(home)
    os.environ["WF_RUNS_ROOT"] = str(home / "runs")
    bindir = home / "venv" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "python").symlink_to(sys.executable)
    launcher = bindir / "duckwork"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(launcher)
    package = home / "fake-core" / "agent"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "auxiliary_client.py").write_text('''import json, os

def call_llm(*, task, provider, model, messages, max_tokens, timeout, route_info):
    with open(os.environ["WF_FAKE_PING_LOG"], "a") as f:
        f.write(json.dumps(dict(task=task, provider=provider, model=model,
                                messages=messages, max_tokens=max_tokens,
                                timeout=timeout)) + "\\n")
    route_info.update(json.loads(os.environ.get("WF_FAKE_ROUTE") or
                                 json.dumps(dict(provider=provider, model=model))))
    return "pong"
''')
    os.environ["PYTHONPATH"] = str(home / "fake-core") + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["WF_FAKE_PING_LOG"] = str(home / "ping.log")
    door = importlib.import_module("__init__")
    wf_test_isolation.install(door)
    door._CTX = None
    door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {}}
    door._seat_aliases = lambda: []
    door._seat_default = lambda: "seat-default"
    door._import_call_llm = lambda: (_ for _ in ()).throw(ModuleNotFoundError("agent"))
    observed = []
    def spawn(run):
        observed.append(json.loads((run / "graph.json").read_text()))
    door._spawn_runner = spawn
    graph = {"name": "cron-probe", "nodes": [{"id": "a", "type": "agent",
        "goal": "x", "provider": "openai", "model": "m-1"}]}
    answer = door.act_run({"graph": graph})
    check("cron submit launches", bool(answer.get("run_id")), answer)
    check("subprocess proves route alive", answer.get("routes", {}).get("a", {}).get("liveness") == "alive", answer)
    committed = observed[0] if observed else {}
    check("atomic pre-spawn graph bake", committed.get("nodes", [{}])[0].get("route_verified") == "openai/m-1", committed)
    lines = (home / "ping.log").read_text().splitlines() if (home / "ping.log").exists() else []
    calls = [json.loads(line) for line in lines]
    check("one explicit provider+model call", len(calls) == 1 and calls[0]["provider"] == "openai"
          and calls[0]["model"] == "m-1" and calls[0]["max_tokens"] == 1, calls)
    shim = home / "shim" / "duckwork"
    shim.parent.mkdir()
    shim.write_text(f'#!/bin/sh\nexec "{launcher}" "$@"\n')
    shim.chmod(0o755)
    os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(shim)
    via_shim = door.act_run({"graph": graph})
    check("cron shell launcher resolves its actual venv Python", via_shim.get("routes", {}).get("a", {}).get("liveness") == "alive", via_shim)
    os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(launcher)
    os.environ["WF_FAKE_ROUTE"] = json.dumps({"provider": "other", "model": "fallback"})
    wrong = door.act_run({"graph": graph})
    check("different recorded route refused", "FALLBACK LADDER" in wrong.get("error", ""), wrong)
    os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(home / "missing-duckwork")
    offline = door.act_run({"graph": graph})
    check("missing launcher stays unknown and fail-open", bool(offline.get("run_id"))
          and offline["routes"]["a"]["liveness"] == "unknown", offline)
    unpinned = {"name": "solo", "nodes": [{"id": "a", "type": "agent", "goal": "x"}]}
    original = dict(unpinned)
    solo = door.act_run({"graph": unpinned})
    saved = json.loads((home / "runs" / solo["run_id"] / "graph.json").read_text()) if solo.get("run_id") else {}
    check("unpinned graph remains byte-identical to legacy defaults bake",
          saved == door._common.apply_graph_defaults(unpinned)
          and "route_verified" not in saved.get("nodes", [{}])[0], saved)

    # The runner receives EXACTLY the node definition baked before spawn. Core's
    # sessions table is a per-session summary; a --continue can leave the final
    # model correct after a mid-turn fallback. Core's session_model_usage table
    # records every main-loop model (task='') separately, so test that evidence.
    import sqlite3
    import wf
    rid = answer["run_id"]
    run = home / "runs" / rid
    baked = json.loads((run / "graph.json").read_text())["nodes"][0]
    check("runner node is committed definition, not re-resolved copy",
          baked == observed[0]["nodes"][0] and baked.get("route_verified") == "openai/m-1", baked)
    title = f"wf:{rid}:a:abc12345#a1"
    db = sqlite3.connect(home / "state.db")
    db.execute("create table sessions (id text, title text, model text, billing_provider text, "
               "input_tokens int, output_tokens int, cache_read_tokens int, reasoning_tokens int, "
               "api_call_count int, tool_call_count int, estimated_cost_usd real, "
               "last_activity_at real, last_activity_description text, ended_at real, started_at real)")
    db.execute("insert into sessions (id,title,model,billing_provider,api_call_count,started_at) "
               "values (?,?,?,?,?,?)", ("child1", title, "m-1", "openai", 2, 1.0))
    db.execute("create table session_model_usage (session_id text, model text, "
               "billing_provider text, task text, api_call_count int)")
    db.executemany("insert into session_model_usage values (?,?,?,?,?)", [
        ("child1", "aux-fallback", "other", "", 1),
        ("child1", "m-1", "openai", "", 1),
        ("child1", "aux-model", "other", "aux-task", 1)])
    db.commit(); db.close()
    import wfcommon
    cm = wfcommon.child_metrics(rid, home).get(title.split("#a", 1)[0], {})
    check("session summary ends on pinned model", cm.get("model") == "m-1", cm)
    wf.seat_forbidden_models = lambda: []
    db = sqlite3.connect(home / "state.db")
    db.execute("update sessions set model='aux-fallback' where id='child1'")
    db.commit(); db.close()
    wrong_final = wf._stamp_served({"_run": run}, {"skey": title.split("#a", 1)[0],
                                    "status": "done"}, baked)
    check("committed child_metrics off-route model fails the node", wrong_final.get("status") == "failed"
          and wrong_final.get("error_class") == "route_unavailable", wrong_final)
    db = sqlite3.connect(home / "state.db")
    db.execute("update sessions set model='m-1' where id='child1'")
    db.commit(); db.close()
    result = wf._stamp_served({"_run": run}, {"skey": title.split("#a", 1)[0],
                               "status": "done"}, baked)
    check("mid-turn fallback bills off-route => route_unavailable", result.get("status") == "failed"
          and result.get("error_class") == "route_unavailable", result)
    # est-2ek.1.774: the record names every main-loop model billed (aux task excluded), and the
    # error says which one was the final served model and which was billed mid-session.
    check("record lists every main-loop model billed, not the aux task",
          sorted(result.get("billed_models") or []) == ["aux-fallback", "m-1"], result.get("billed_models"))
    check("error names the final served model and the mid-session model",
          "final served_model 'm-1'" in result.get("error", "")
          and "mid-session call billed 'aux-fallback'" in result.get("error", ""), result.get("error"))
    wf.save_node(run, baked, {baked["id"]: baked}, result)
    rec = json.loads((run / "nodes" / f"{baked['id']}.json").read_text())
    check("committed node record carries billed_models",
          sorted(rec.get("billed_models") or []) == ["aux-fallback", "m-1"], rec)
    wf.commit_item_record(run, baked, {baked["id"]: baked}, 0, result)
    item = json.loads((run / "nodes" / f"{baked['id']}.0.json").read_text())
    check("fan-out item record carries billed_models too",
          sorted(item.get("billed_models") or []) == ["aux-fallback", "m-1"], item)
    legacy = wf._stamp_served({"_run": run}, {"skey": title.split("#a", 1)[0],
                               "status": "done"}, saved["nodes"][0])
    check("no pin/proof: legacy hold remains disabled", legacy.get("status") == "done"
          and "route_unavailable" not in str(legacy), legacy)
    check("no pin/proof: the runner invents no billed_models", "billed_models" not in legacy, legacy)
    # est-2ek.1.774: a single-model child gets a one-item list and still passes.
    db = sqlite3.connect(home / "state.db")
    db.execute("delete from session_model_usage where model='aux-fallback'")
    db.commit(); db.close()
    single = wf._stamp_served({"_run": run}, {"skey": title.split("#a", 1)[0],
                              "status": "done"}, baked)
    check("single-model child still passes with a one-item billed_models",
          single.get("status") == "done" and single.get("billed_models") == ["m-1"], single)
print("ALL PASS" if not failures else f"FAILURES: {failures}")
sys.exit(bool(failures))
