# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
import importlib
import os

import pytest

from conftest import PLUGIN_DIR


@pytest.mark.parametrize("module, name", [
    ("agent.memory_provider", "MemoryProvider"), ("agent.memory_provider", "RecallStatus"),
    ("agent.memory_provider", "spawn_context_thread"), ("agent.secret_scope", "get_secret"),
    ("duckwork_cli.config", "load_config"), ("duckwork_cli.config", "save_config"),
    ("duckwork_cli.config", "save_env_value"), ("duckwork_constants", "get_duckwork_home"),
])
def test_every_duckwork_symbol_the_plugin_imports_exists(module, name):
    assert hasattr(importlib.import_module(module), name)


def test_duckwork_loads_the_directory_provider_and_its_cli(duckwork_home, monkeypatch):
    (duckwork_home / "plugins").mkdir()
    os.symlink(PLUGIN_DIR, duckwork_home / "plugins" / "lumberroom")
    (duckwork_home / "config.yaml").write_text(
        "memory:\n  provider: lumberroom\n  lumberroom:\n    base_url: http://fake.lumberroom.test\n    auth: oauth\n")
    from plugins.memory import discover_plugin_cli_commands, load_memory_provider
    provider = load_memory_provider("lumberroom")
    assert provider is not None and provider.name == "lumberroom" and provider.is_available()
    commands = discover_plugin_cli_commands()
    assert commands and commands[0]["name"] == "lumberroom" and commands[0]["handler_fn"] is not None
