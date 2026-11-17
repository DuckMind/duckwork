"""Release-facing checks for shipped harness integration templates."""

from __future__ import annotations

import json
import tomllib
from importlib.resources import files
from pathlib import Path

import pytest

from spectator.integrations import available_integrations, read_integration


@pytest.mark.parametrize("harness", ["claude-code", "codex", "commandcode"])
def test_command_hook_integrations_are_parseable_and_observe_core_events(harness):
    template = json.loads(read_integration(harness))
    hooks = template["hooks"]
    assert {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}.issubset(hooks)
    commands = {
        handler["command"]
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    }
    assert commands == {f"spectator-hook --harness {harness}"}


def test_codex_session_end_hook_is_synchronous():
    """Codex ignores async for SessionEnd and emits a warning when it is set."""
    hooks = json.loads(read_integration("codex"))["hooks"]["SessionEnd"]
    handlers = [handler for group in hooks for handler in group["hooks"]]
    assert handlers
    assert all(handler.get("async") is not True for handler in handlers)


def test_extension_integrations_cover_opencode_and_pi_lifecycle():
    opencode = read_integration("opencode")
    assert '"tool.execute.before"' in opencode
    assert '"tool.execute.after"' in opencode
    assert '"chat.message"' in opencode
    assert "content_size" in opencode
    assert "message.updated" not in opencode
    assert "session.created" in opencode
    assert "session.idle" in opencode

    pi = read_integration("pi")
    for event in (
        "session_start",
        "session_shutdown",
        "input",
        "message_end",
        "tool_execution_start",
        "tool_execution_end",
    ):
        assert f'pi.on("{event}"' in pi


def test_integration_catalog_is_complete_and_contains_no_machine_paths_or_secrets():
    assert available_integrations() == (
        "claude-code",
        "codex",
        "commandcode",
        "opencode",
        "pi",
    )
    forbidden = ("/home/kensei", "api_key", "password", "bearer ")
    for harness in available_integrations():
        content = read_integration(harness).lower()
        assert not any(value in content for value in forbidden), harness


def test_integration_package_data_is_present():
    root = files("spectator.integrations")
    assert root.joinpath("claude-code.json").is_file()
    assert root.joinpath("opencode.ts").is_file()
    assert root.joinpath("pi.ts").is_file()


def test_runtime_dependencies_include_a_websocket_server_backend():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = [value.lower() for value in project["dependencies"]]
    assert any(value.startswith("websockets") for value in dependencies)
