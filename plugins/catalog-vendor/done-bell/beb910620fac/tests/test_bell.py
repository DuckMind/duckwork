"""Local checks that do not require Duckwork."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="done-bell-test-")
os.environ["DONE_BELL_NO_OS"] = "1"

import bell_hooks
import bell_store
import bell_tools


def test_defaults() -> None:
    snap = bell_store.snapshot()
    assert snap["ok"] is True
    assert snap["needs_you"] is False
    assert snap["settings"]["muted"] is False
    assert snap["settings"]["sound"] is True
    assert snap["events"] == []


def test_record_done() -> None:
    event = bell_store.record_event("done", session_id="s1", platform="cli", detail="completed")
    assert event["kind"] == "done"
    events = bell_store.list_events()
    assert events[-1]["id"] == event["id"]


def test_needs_you_cycle() -> None:
    bell_hooks.on_pre_approval_request(platform="cli", session_key="s2")
    snap = bell_store.snapshot()
    assert snap["needs_you"] is True
    assert snap["events"][-1]["kind"] == "needs_you"
    bell_hooks.on_post_approval_response(approved=True)
    assert bell_store.snapshot()["needs_you"] is False


def test_session_end_completed() -> None:
    bell_hooks.on_session_end(session_id="s3", completed=True, interrupted=False, platform="cli")
    kinds = [e["kind"] for e in bell_store.list_events()]
    assert "done" in kinds


def test_session_end_interrupted() -> None:
    bell_hooks.on_session_end(session_id="s4", completed=False, interrupted=True, platform="cli")
    assert bell_store.list_events()[-1]["kind"] == "interrupted"


def test_mute_via_tool() -> None:
    data = json.loads(bell_tools.done_bell_status({"mute": True, "markdown": True}))
    assert data["ok"] is True
    assert data["settings"]["muted"] is True
    assert "muted" in data["markdown"]
    data = json.loads(bell_tools.done_bell_status({"mute": False}))
    assert data["settings"]["muted"] is False


def test_tool_kwargs() -> None:
    data = json.loads(bell_tools.done_bell_status({}, extra="x"))
    assert data["ok"] is True


def test_hook_kwargs() -> None:
    bell_hooks.on_session_end(session_id="s5", completed=True, extra="x")
    bell_hooks.on_agent_loop_stopped(session_key="s5", platform="gateway", reason="user", extra="x")
    assert bell_store.list_events()[-1]["kind"] == "interrupted"


def test_cli_notify_gate() -> None:
    bell_store.patch_settings({"muted": True, "os_notify": True})
    assert bell_store.should_os_notify_cli("cli") is False
    bell_store.patch_settings({"muted": False, "os_notify": True})
    assert bell_store.should_os_notify_cli("cli") is True
    assert bell_store.should_os_notify_cli("gateway") is False
    assert bell_store.should_os_notify_cli("desktop") is False


if __name__ == "__main__":
    test_defaults()
    test_record_done()
    test_needs_you_cycle()
    test_session_end_completed()
    test_session_end_interrupted()
    test_mute_via_tool()
    test_tool_kwargs()
    test_hook_kwargs()
    test_cli_notify_gate()
    print("ok")
