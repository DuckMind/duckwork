"""dad50be002da89d5: model policy at the door and actual served-route admission."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("model_law_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71_door15; _iso71_door15.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
FAKE = str(ROOT / "tests" / "fake")


def check(value, label):
    assert value, label
    print("PASS", label)


def graph(policy=None, fanout=False):
    node = {"id": "worker", "type": "agent", "goal": "OK"}
    if fanout:
        node["fanout"] = {"items": ["a", "b"], "goal": "OK {item}"}
    g = {"name": "model-law", "nodes": [node,
         {"id": "next", "type": "echo", "after": ["worker"], "output": {"reached": True}}]}
    if policy is not None:
        g["model_policy"] = policy
    return g


with tempfile.TemporaryDirectory(prefix="model-law-") as td:
    home = Path(td)
    (home / "config.yaml").write_text("model:\n  default: safe\n  aliases:\n    opus: anthropic/forbidden-target\n  workflows_forbidden_models:\n    - banned-seat\n")
    with patch.dict(os.environ, DUCKWORK_HOME=td, WF_RUNS_ROOT=str(Path(td) / "workflows")), patch.object(door, "_spawn_runner"):  # #71 shelf pin
        # This import is deliberately blocked: the stdlib YAML fallback must read lists.
        with patch.dict(sys.modules, {"duckwork_cli.config": None}):
            check(door._seat_model_cfg().get("workflows_forbidden_models") == ["banned-seat"],
                  "stdlib seat config list is read")
            invalid = door.act_run({"graph": graph({"require_model": True})})
            check(any(e.get("node") == "worker" and e.get("field") == "model"
                      for e in invalid.get("errors", [])), "run refuses missing required model")
            for policy in ({"require_model": "yes"}, {"forbidden_models": "fake"}):
                err = door.act_run({"graph": graph(policy)})
                check(bool(err.get("errors")), "policy shape rejected")
            alias = graph({"forbidden_models": ["forbidden-target"]})
            alias["nodes"][0]["model"] = "opus"
            err = door.act_run({"graph": alias})
            check(any(e.get("field") == "model" for e in err.get("errors", [])),
                  "alias target forbidden at submit")
            seat = graph()
            seat["nodes"][0]["model"] = "banned-seat"
            err = door.act_run({"graph": seat})
            check(any(e.get("field") == "model" for e in err.get("errors", [])),
                  "seat floor forbids model without graph policy")
            # The same door must prevent amend's graph.json replacement.
            good = door.act_run({"graph": graph(), "duckwork_bin": FAKE})
            check(bool(good.get("run_id")), "policy-free graph accepted")
            run = home / "workflows" / good["run_id"]
            before = (run / "graph.json").read_bytes()
            amend = door.act_amend({"run_id": good["run_id"], "graph": graph({"require_model": True})})
            check(bool(amend.get("errors")) and (run / "graph.json").read_bytes() == before,
                  "amend refuses absent model before writing")

    # One child has no served row; the other has a proven forbidden route.
    # This launcher is local to the hermetic home, never a production credential.
    mixed_fake = home / "mixed-fake"
    mixed_fake.write_text("#!/usr/bin/env python3\nimport os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "query = Path(args[args.index('--query-file') + 1]).read_text()\n"
        "if 'CLEAR QSLEEP' in query or 'FAILME' in query: os.environ.pop('FAKE_API_CALLS', None)\n"
        f"os.execv(sys.executable, [sys.executable, {str(ROOT / 'tests' / 'fake_duckwork.py')!r}, *args])\n")
    mixed_fake.chmod(0o700)

    def run_child(g, *, row=True, launcher=FAKE):
        runs = home / "workflows"
        run = runs / ("case-" + str(len(list(runs.iterdir()))))
        (run / "nodes").mkdir(parents=True)
        (run / "gates").mkdir()
        (run / "graph.json").write_text(json.dumps(g))
        (run / "run.json").write_text(json.dumps({"name": "case", "duckwork_bin": launcher,
                                                "node_timeout": 20, "started": "2099-01-01T00:00:00+00:00"}))
        argv = home / (run.name + ".argv")
        env = {**os.environ, "DUCKWORK_HOME": td, "WF_RUNS_ROOT": str(home / "workflows"), "FAKE_LOG": str(home / "fake.log"),  # #71 shelf pin
               "FAKE_ARGV_LOG": str(argv)}
        if row:
            env["FAKE_API_CALLS"] = "1"
        p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run.name],
                           env=env, text=True, capture_output=True, timeout=60)
        assert (run / "nodes" / "worker.json").exists(), p.stdout + p.stderr
        return run, json.loads((run / "nodes" / "worker.json").read_text()), argv.read_text()

    plain, rec, argv = run_child(graph())
    check(rec["status"] == "done" and " -m " not in " " + argv,
          "baseline: no policy preserves model-absent spawn")
    check(rec.get("served_model") == "fake" and rec.get("served_billing_provider") == "fake-provider",
          "solo commit records served model and billing provider")
    denied, rec, _ = run_child(graph({"forbidden_models": ["fake"]}))
    events = [json.loads(x) for x in (denied / "events.jsonl").read_text().splitlines()]
    check(rec["status"] == "failed" and rec.get("error_class") == "forbidden_model"
          and any(e["event"] == "node.failed" and e.get("error_class") == "forbidden_model" for e in events)
          and not (denied / "nodes" / "next.json").exists(),
          "served forbidden model fails and blocks downstream gate")
    absent, rec, _ = run_child(graph({"forbidden_models": ["fake"]}), row=False)
    check(rec["status"] == "done" and rec.get("served_model") is None,
          "missing sessions row is unknown, not forbidden")
    fan, rec, _ = run_child(graph({"forbidden_models": ["fake"]}, fanout=True))
    results = rec["output"]["all_results"]
    check(all(x.get("served_model") == "fake" and x.get("served_billing_provider") == "fake-provider"
              and x.get("error_class") == "forbidden_model" for x in results),
          "fan-out item commits stamp and reject served model")
    def parent_denied(run, record, label):
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        details = record.get("failed_detail", [])
        check(record["status"] == "failed" and record.get("error_class") == "forbidden_model"
              and any(e["event"] == "node.failed" and e.get("error_class") == "forbidden_model"
                      and e.get("failed_detail") == details for e in events)
              and not any(e["event"] == "node.finished" and e.get("node") == "worker" for e in events)
              and not (run / "nodes" / "next.json").exists(), label + ": parent fails, event typed, downstream blocked")
        check(any(d.get("error_class") == "forbidden_model"
                  and d.get("served_model") == "fake"
                  and d.get("served_billing_provider") == "fake-provider" for d in details),
              label + ": failed detail retains typed served evidence")

    parent_denied(fan, rec, "all forbidden")
    mixed = graph({"forbidden_models": ["fake"]}, fanout=True)
    mixed["nodes"][0]["fanout"] = {"items": ["BAN", "CLEAR QSLEEP 0.8"],
                                    "goal": "{item}", "quorum": 1}
    run, rec, _ = run_child(mixed, launcher=str(mixed_fake))
    results = rec["output"]["all_results"]
    check(results[0].get("error_class") == "forbidden_model" and results[1]["status"] == "done"
          and results[1].get("served_model") is None and len(rec["output"]["items"]) == 1,
          "mixed quorum: successful unknown sibling and forbidden item retained")
    parent_denied(run, rec, "quorum otherwise met")
    mixed["nodes"][0]["fanout"]["items"] = ["BAN", "FAILME", "CLEAR QSLEEP 0.8"]
    run, rec, _ = run_child(mixed, launcher=str(mixed_fake))
    detail = rec["failed_detail"]
    check(rec["output"]["all_results"][1]["error_class"] != "forbidden_model"
          and detail[1]["error_class"] == rec["output"]["all_results"][1]["error_class"]
          and detail[0]["error_class"] == "forbidden_model"
          and detail[1]["served_model"] is None,
          "mixed failure keeps ordinary cause and unknown route distinct from forbidden")
    parent_denied(run, rec, "mixed failures")
print("ALL PASS")
