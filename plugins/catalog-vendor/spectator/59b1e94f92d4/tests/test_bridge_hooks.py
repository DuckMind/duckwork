"""Conformance tests for the portable lifecycle-hook adapter."""

from __future__ import annotations

import json

import pytest

from spectator.bridge.hooks import map_hook_payload


@pytest.mark.parametrize("harness", ["claude-code", "codex", "commandcode"])
def test_common_hook_envelope_maps_user_prompt_without_copying_content(harness):
    payload = {
        "session_id": f"{harness}-session",
        "cwd": "/workspace/project",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "SECRET user request that must not enter the feed",
        "prompt_id": "prompt-1",
    }
    session_id, cwd, events = map_hook_payload(harness, payload)
    assert session_id == f"{harness}-session"
    assert cwd == "/workspace/project"
    assert len(events) == 1
    event = events[0]
    assert event.type == "message"
    assert event.source_id.endswith("prompt-1")
    assert event.summary == {
        "role": "user",
        "chars": len(payload["prompt"]),
        "note": "user message",
    }
    assert "SECRET" not in repr(event.summary)


def test_opencode_chat_message_uses_declared_content_size_without_raw_content():
    payload = {
        "type": "input",
        "sessionID": "opencode-session",
        "directory": "/workspace/project",
        "messageID": "message-4",
        "content_size": 123,
    }
    _, _, events = map_hook_payload("opencode", payload)
    assert events[0].source_id.endswith("message-4")
    assert events[0].summary == {"role": "user", "chars": 123, "note": "user message"}


def test_opencode_event_envelope_maps_tool_call():
    payload = {
        "type": "tool.execute.before",
        "sessionID": "opencode-session",
        "directory": "/workspace/project",
        "properties": {
            "callID": "call-9",
            "tool": "bash",
            "input": {"command": "pytest", "timeout": 30},
        },
    }
    session_id, cwd, events = map_hook_payload("opencode", payload)
    assert session_id == "opencode-session"
    assert cwd == "/workspace/project"
    assert events[0].type == "tool_call"
    assert events[0].source_id.endswith("call-9")
    assert events[0].summary == {"tool": "bash", "args": 2, "note": "invoked bash"}


def test_pi_event_envelope_maps_tool_result():
    payload = {
        "type": "tool_execution_end",
        "sessionId": "pi-session",
        "cwd": "/workspace/project",
        "toolCallId": "tool-3",
        "toolName": "read",
        "isError": False,
        "result": {"content": [{"type": "text", "text": "raw output is measured but never copied"}]},
    }
    _, _, events = map_hook_payload("pi", payload)
    assert events[0].type == "tool_result"
    encoded = json.dumps(payload["result"], sort_keys=True, separators=(",", ":"))
    assert events[0].summary == {
        "tool": "read",
        "status": "ok",
        "size": len(encoded.encode()),
    }
    assert "raw output" not in repr(events[0].summary)


def test_pi_input_and_tool_start_use_the_published_extension_shape():
    user_payload = {
        "type": "input",
        "sessionId": "pi-session",
        "cwd": "/workspace/project",
        "text": "private user text",
        "source": "interactive",
        "_spectator_occurrence": "entry-4",
    }
    _, _, user_events = map_hook_payload("pi", user_payload)
    assert user_events[0].summary == {
        "role": "user",
        "chars": len(user_payload["text"]),
        "note": "user message",
    }
    assert "private user text" not in repr(user_events[0].summary)

    tool_payload = {
        "type": "tool_execution_start",
        "sessionId": "pi-session",
        "cwd": "/workspace/project",
        "toolCallId": "tool-4",
        "toolName": "bash",
        "args": {"command": "pytest", "timeout": 30},
    }
    _, _, tool_events = map_hook_payload("pi", tool_payload)
    assert tool_events[0].summary == {"tool": "bash", "args": 2, "note": "invoked bash"}


@pytest.mark.parametrize(
    ("event_name", "expected"),
    [
        ("SessionStart", {"from": "starting", "to": "active"}),
        ("Stop", {"from": "active", "to": "idle"}),
        ("SessionEnd", {"from": "active", "to": "closed"}),
    ],
)
def test_lifecycle_events_map_to_status_changes(event_name, expected):
    payload = {
        "session_id": "session-1",
        "cwd": "/workspace/project",
        "hook_event_name": event_name,
        "timestamp": "2026-08-25T12:00:00Z",
    }
    first = map_hook_payload("generic", payload)[2][0]
    second = map_hook_payload("generic", payload)[2][0]
    assert first.type == "status_change"
    assert first.summary == expected
    assert first.source_id == second.source_id


def test_hook_transport_rejects_non_http_urls_before_opening_them():
    from spectator.bridge.cli import _send_json

    with pytest.raises(RuntimeError, match="http or https"):
        _send_json("file:///etc/passwd", "token", "POST", {})
