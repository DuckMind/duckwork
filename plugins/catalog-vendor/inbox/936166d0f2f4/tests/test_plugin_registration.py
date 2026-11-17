"""Plugin wiring through Duckwork' real discovery path against a temp DUCKWORK_HOME: ``duckwork inbox``
exists only when the plugin is enabled, and the registered command runs end to end."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import pytest

from inbox_seed import write_cron

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _install(duckwork_home: Path, enabled: bool) -> None:
    dest = duckwork_home / "plugins" / "inbox"
    shutil.copytree(PLUGIN_ROOT, dest, ignore=shutil.ignore_patterns("tests", "__pycache__", ".pytest_cache"))
    enabled_yaml = "    - inbox\n" if enabled else "    []\n"
    (duckwork_home / "config.yaml").write_text("plugins:\n  enabled:\n" + enabled_yaml, encoding="utf-8")


def _manager():
    from duckwork_cli.plugins import PluginManager

    pm = PluginManager()
    pm.discover_and_load()
    return pm


def _parser(pm) -> argparse.ArgumentParser:
    info = pm._cli_commands["inbox"]
    parser = argparse.ArgumentParser(prog="duckwork inbox")
    info["setup_fn"](parser)
    parser.set_defaults(func=info["handler_fn"])
    return parser


@pytest.fixture
def enabled_manager(duckwork_home):
    _install(duckwork_home, enabled=True)
    return _manager()


def test_disabled_plugin_registers_nothing(duckwork_home):
    _install(duckwork_home, enabled=False)
    assert "inbox" not in _manager()._cli_commands


def test_enabled_plugin_registers_the_command(enabled_manager):
    assert enabled_manager._cli_commands["inbox"]["plugin"] == "inbox"


def test_command_prints_the_inbox(enabled_manager, duckwork_home, capsys):
    write_cron(duckwork_home, [{"id": "j", "name": "nightly", "enabled": True, "last_status": "error",
                              "last_error": "timeout", "next_run_at": "2026-10-22T03:00:00"}])
    args = _parser(enabled_manager).parse_args([])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "cron 'nightly'  last run FAILED: timeout" in out
    assert "nightly  next: 2026-10-22T03:00:00" in out


def test_json_flag(enabled_manager, duckwork_home, capsys):
    args = _parser(enabled_manager).parse_args(["--json"])
    assert args.func(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["home"] == str(duckwork_home)
    assert data["generated_at"] <= time.time()
    assert set(data) >= {"attention", "in_progress", "finished_undelivered", "cron", "sessions", "sources"}
