"""Authoring door regressions; all state stays in this worktree, no children/providers."""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

BUILD = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("authoring_door", BUILD / "__init__.py")
assert spec is not None and spec.loader is not None
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
NODE = {"id": "task", "type": "agent", "goal": "Do work"}


def call(**args):
    return json.loads(door.handle(args))


def graph(**extras):
    return {"name": "file-title", "nodes": [dict(NODE)], **extras}


def check(condition, detail):
    assert condition, detail
    print("PASS", detail)


with tempfile.TemporaryDirectory(prefix="authoring-", dir=BUILD) as tmp:
    original_home = os.environ.get("DUCKWORK_HOME")
    original_runs = os.environ.get("WF_RUNS_ROOT")
    os.environ["DUCKWORK_HOME"] = tmp
    # #71: DUCKWORK_HOME alone loses to the context-local home override in lane
    # processes — the shelf only actually sandboxes when WF_RUNS_ROOT pins it
    # (checked before any home resolution). Without this, these saves land in
    # the SHARED estate library.
    os.environ["WF_RUNS_ROOT"] = str(Path(tmp) / "workflows")
    started = []
    original_spawn = door._spawn_runner
    original_alive = door.runner_alive
    setattr(door, "_spawn_runner", lambda r: started.append(r.name))
    setattr(door, "runner_alive", lambda r: True)
    try:
        source = Path(tmp) / "graph.json"
        source.write_text(json.dumps(graph()), encoding="utf-8")
        check("graph_path" in door.WORKFLOW_PARAMS["properties"], "graph_path is in tool schema")
        run = call(action="run", graph_path=str(source), name="caller-title")
        check("run_id" in run, "file-authored run launches")
        run_dir = door.run_dir(run["run_id"])
        check(json.loads((run_dir / "graph.json").read_text())["name"] == "caller-title"
              and json.loads((run_dir / "run.json").read_text())["name"] == "caller-title",
              "run action name overrides graph name consistently")
        plain = call(action="run", graph=graph())
        check(json.loads((door.run_dir(plain["run_id"]) / "graph.json").read_text())["name"] == "file-title",
              "inline graph name preserved")
        check("run_id" in call(action="run", graph=json.dumps(graph())), "inline string graph preserved")

        saved = call(action="save", graph_path=str(source), name="library-title")
        check(saved.get("saved") == "library-title" and
              json.loads((door.library_root() / "library-title.json").read_text())["name"] == "library-title",
              "file-authored save honors library name")
        check(call(action="save", graph=graph()).get("saved") == "file-title",
              "save can use graph.name")
        check(call(action="save", graph=json.dumps(graph()), name="string-entry").get("saved") == "string-entry",
              "save accepts inline JSON string through coerce")

        next_graph = graph(name="new-title", nodes=[dict(NODE, goal="Updated")])
        source.write_text(json.dumps(next_graph), encoding="utf-8")
        preview = call(action="amend", run_id=run["run_id"], graph_path=str(source), dry_run=True)
        check(preview.get("ok") and preview.get("dry_run") and
              json.loads((run_dir / "graph.json").read_text())["name"] == "caller-title",
              "file-authored amend preview has no write")
        amended = call(action="amend", run_id=run["run_id"], graph_path=str(source))
        check(amended.get("ok") and json.loads((run_dir / "graph.json").read_text())["name"] == "new-title"
              and json.loads((run_dir / "run.json").read_text())["name"] == "new-title",
              "amend changes effective name in graph and metadata")
        no_name = {"nodes": [dict(NODE, goal="Again")]}
        check(call(action="amend", run_id=run["run_id"], graph=no_name).get("ok") and
              json.loads((run_dir / "graph.json").read_text())["name"] == "new-title",
              "amend without name retains existing name")

        malformed = {"name": "bad", "nodes": [{"id": "task", "type": "agent"},
                    {"id": "gate", "type": "gate", "question": "Q", "bogus": 1}], "surprise": True}
        source.write_text(json.dumps(malformed), encoding="utf-8")
        run_count, spawn_count = len(list(door.runs_root().iterdir())), len(started)
        err = call(action="run", graph_path=str(source))
        check({(x["field"], x["node"]) for x in err.get("errors", [])} >=
              {("surprise", None), ("goal", "task"), ("bogus", "gate")}
              and len(started) == spawn_count and len(list(door.runs_root().iterdir())) == run_count,
              "run returns graph and node defects together before side effects")
        for action, args in (("save", {"name": "should-not-exist"}),
                             ("amend", {"run_id": run["run_id"]})):
            res = call(action=action, graph_path=str(source), **args)
            check(len(res.get("errors", [])) >= 3 and
                  not (door.library_root() / "should-not-exist.json").exists() and
                  json.loads((run_dir / "graph.json").read_text()) != malformed,
                  f"{action} returns all defects without mutation")

        for label, path, value in (
            ("relative", "graph.json", None),
            ("directory", tmp, None),
            ("missing", str(Path(tmp) / "missing.json"), None),
            ("UTF-8", str(source), b"\xff"),
            ("malformed JSON", str(source), b'{"nodes": [}'),
            ("oversized", str(source), b" " * (1024 * 1024 + 1)),
        ):
            if value is not None:
                source.write_bytes(value)
            res = call(action="run", graph_path=path)
            check("error" in res and len(started) == spawn_count and
                  len(list(door.runs_root().iterdir())) == run_count,
                  f"{label} path rejected before side effects")
        source.write_text(json.dumps(graph()), encoding="utf-8")
        for label, invalid in (
            ("non-list dependency", {"name": "bad", "nodes": [dict(NODE, after=3)]}),
            ("non-string dependency", {"name": "bad", "nodes": [dict(NODE, after=[{}])]}),
            ("unhashable node id", {"name": "bad", "nodes": [dict(NODE, id=[])]}),
            ("blank graph name and missing goal", {"name": " ", "nodes": [{"id": "task", "type": "agent"}]}),
        ):
            res = call(action="run", graph=invalid)
            check("error" in res and "trace" not in res and res.get("errors") and
                  len(started) == spawn_count, f"{label} produces clear validation errors")
        mixed = call(action="run", graph={"name": "bad", "nodes": [dict(NODE, after=3),
                            {"id": "another", "type": "agent"}]})
        check({(e["node"], e["field"]) for e in mixed.get("errors", [])} >=
              {("task", "after"), ("another", "goal")},
              "malformed dependencies do not conceal other validation errors")
        link = Path(tmp) / "link.json"
        link.symlink_to(source)
        check("error" in call(action="run", graph_path=str(link)), "symlink graph rejected")
        check("error" in call(action="run", graph_path=str(source), graph=graph()),
              "ambiguous graph and graph_path rejected")
        check("error" in call(action="run", graph_path=str(source), **{"from": "file-title"}),
              "ambiguous library and graph_path rejected")
        check("error" in call(action="save", graph_path=str(source), run_id=run["run_id"]),
              "ambiguous run_id and graph_path rejected for save")
    finally:
        setattr(door, "_spawn_runner", original_spawn)
        setattr(door, "runner_alive", original_alive)
        if original_home is None:
            os.environ.pop("DUCKWORK_HOME", None)
        else:
            os.environ["DUCKWORK_HOME"] = original_home
        if original_runs is None:
            os.environ.pop("WF_RUNS_ROOT", None)
        else:
            os.environ["WF_RUNS_ROOT"] = original_runs
print("ALL PASS")
