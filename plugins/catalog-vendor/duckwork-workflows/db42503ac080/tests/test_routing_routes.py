"""Deterministic regressions for explicit workflow provider/model routing."""
import importlib.util
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
sys.path.insert(0, str(BUILD))

with tempfile.TemporaryDirectory(prefix=".routing-test-", dir=HERE) as tmp:
    os.environ["DUCKWORK_HOME"] = tmp
    os.environ["TMPDIR"] = tmp
    tempfile.tempdir = tmp

    import wfcommon
    door_spec = importlib.util.spec_from_file_location("routing_test_door", BUILD / "__init__.py")
    door = importlib.util.module_from_spec(door_spec)
    door_spec.loader.exec_module(door)
    import wf as engine

    class Ctx:
        def get_config(self, key, default=None):
            return {"luna-tier": "openai-codex/gpt-6-luna"} if key == "models" else default

    door._CTX = Ctx()
    door._seat_model_cfg = lambda: {
        "default": "seat-default",
        "aliases": {"luna": "openai-codex/gpt-6-luna"},
    }

    qualified = {
        "id": "qualified", "type": "agent", "goal": "route",
        "provider": "openai-codex", "model": "openai-codex/gpt-6-luna",
    }
    tiered = {
        "id": "tiered", "type": "agent", "goal": "route",
        "provider": "openai-codex", "model": "luna-tier",
    }
    graph_nodes = [qualified, tiered]
    assert wfcommon.validate_graph(graph_nodes) is None, "provider/model graph should validate"

    err, table, routes = door._resolve_models(graph_nodes)
    assert err is None, err
    assert qualified["provider"] == "openai-codex" and qualified["model"] == "gpt-6-luna"
    assert tiered["provider"] == "openai-codex" and tiered["model"] == "gpt-6-luna"
    assert tiered["tier"] == "luna-tier"
    assert routes["qualified"] == {
        "requested": {"provider": "openai-codex", "model": "openai-codex/gpt-6-luna"},
        "resolved": {"provider": "openai-codex", "model": "gpt-6-luna"},
    }
    assert routes["tiered"]["requested"] == {"provider": "openai-codex", "model": "luna-tier"}
    assert routes["tiered"]["resolved"] == {"provider": "openai-codex", "model": "gpt-6-luna"}
    assert table["qualified"] == "openai-codex/gpt-6-luna"
    assert table["tiered"] == "openai-codex/gpt-6-luna  (luna-tier)"

    bad_provider = {"id": "bad", "type": "agent", "goal": "x", "provider": "openai-codex"}
    errors = wfcommon.validate_graph_errors([bad_provider])
    assert any(e["field"] == "provider" and "model" in e["msg"] for e in errors), errors

    # A literal equal to a configured alias target bakes its provider like an alias does
    # (est-2ek.1.46: a bare `-m openai-codex/...` died HTTP 400 on the seat default route);
    # aliases remain accepted as aliases.
    literal = [{"id": "literal", "type": "agent", "goal": "x", "model": "openai-codex/gpt-6-luna"}]
    alias = [{"id": "alias", "type": "agent", "goal": "x", "model": "luna"}]
    assert door.resolve_models(literal)[0] is None
    assert (literal[0]["provider"], literal[0]["model"]) == ("openai-codex", "gpt-6-luna")
    assert door.resolve_models(alias)[0] is None and alias[0]["model"] == "luna"

    # Exercise the actual child command builder without launching Duckwork or contacting a provider.
    run = Path(tmp) / "run"
    (run / "nodes").mkdir(parents=True)
    node = {"id": "child", "type": "agent", "goal": "route", "model": "gpt-6-luna",
            "provider": "openai-codex"}
    captured = []

    class FakeProcess:
        pid = os.getpid()
        returncode = 0

        def communicate(self, timeout=None):
            captured[0][1]["stdout"].write('```json\n{"routed": true}\n```\n')
            captured[0][1]["stdout"].flush()

        def poll(self):            # the runner polls (#18 liveness) instead of blocking
            self.communicate()
            return self.returncode

    def fake_popen(argv, **kwargs):
        captured.append((argv, kwargs))
        return FakeProcess()

    meta = {
        "_run": run, "duckwork_bin": "not-executed", "_procs": {},
        "_procs_lock": threading.Lock(), "_stop": threading.Event(), "_spawn_n": {}, "node_timeout": 5,
    }
    with patch.object(engine.subprocess, "Popen", fake_popen):
        child = engine.run_child(meta, node, {"child": node}, "route", "", None)
    assert child["status"] == "done", child
    argv = captured[0][0]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna", argv
    assert argv[argv.index("--provider") + 1] == "openai-codex", argv
    assert "openai-codex/gpt-6-luna" not in argv, argv

print("ALL PASS")
