"""Local checks that do not require Duckwork."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="command-tray-test-")

import cmd_hooks
import cmd_store
import cmd_tools


def test_success_and_fail() -> None:
    cmd_store.clear_commands()
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "pytest -q"},
        json.dumps({"exit_code": 0, "output": "3 passed"}),
    )
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "python -c \"import sys; sys.exit(1)\""},
        json.dumps({"exit_code": 1, "output": "Error: boom"}),
    )
    items = cmd_store.list_commands()
    assert len(items) == 2
    by_cmd = {it["command"]: it for it in items}
    assert by_cmd["pytest -q"]["status"] == "ok"
    assert by_cmd["pytest -q"]["exit_code"] == 0
    fail = by_cmd['python -c "import sys; sys.exit(1)"']
    assert fail["status"] == "fail"
    assert fail["exit_code"] == 1
    assert "boom" in fail["preview"]


def test_dedupe_updates() -> None:
    cmd_store.clear_commands()
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "npm test"},
        json.dumps({"exit_code": 1, "output": "FAIL"}),
    )
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "npm test"},
        json.dumps({"exit_code": 0, "output": "ok"}),
    )
    items = cmd_store.list_commands()
    assert len(items) == 1
    assert items[0]["status"] == "ok"
    assert items[0]["runs"] == 2


def test_redact() -> None:
    cmd_store.clear_commands()
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "curl -H 'Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz' https://x"},
        json.dumps({"exit_code": 0, "output": "ok token=ghp_abcdefghijklmnopqrstuv"}),
    )
    items = cmd_store.list_commands()
    assert len(items) == 1
    assert "sk-" not in items[0]["command"] or "[redacted]" in items[0]["command"]
    assert "ghp_" not in items[0]["preview"]


def test_ignore_other_tools() -> None:
    cmd_store.clear_commands()
    cmd_hooks.on_post_tool_call(
        "read_file",
        {"path": "README.md"},
        json.dumps({"ok": True}),
    )
    assert cmd_store.list_commands() == []


def test_workdir() -> None:
    cmd_store.clear_commands()
    cmd_hooks.on_post_tool_call(
        "terminal",
        {"command": "ls", "workdir": r"C:\Users\aydin\proj"},
        json.dumps({"exit_code": 0, "output": "a"}),
    )
    assert cmd_store.list_commands()[0]["workdir"] == "C:/Users/aydin/proj"


def test_tools_json() -> None:
    cmd_store.clear_commands()
    data = json.loads(cmd_tools.command_tray_list({}, extra="x"))
    assert data["ok"] is True
    assert data["count"] == 0
    assert "(command-tray is empty)" in data["markdown"]
    cleared = json.loads(cmd_tools.command_tray_clear({}))
    assert cleared["ok"] is True


if __name__ == "__main__":
    test_success_and_fail()
    test_dedupe_updates()
    test_redact()
    test_ignore_other_tools()
    test_workdir()
    test_tools_json()
    print("ok")
