"""Portable lifecycle-hook payload mapping.

The mapper accepts the common command-hook envelope used by Claude Code,
Codex and CommandCode, plus the event shapes exposed by OpenCode and Pi.
Only typed counts and short privacy-masked labels leave this module. Raw
prompts, model output, tool arguments and tool results are never copied.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from spectator.core.contracts import EventInput
from spectator.feed.engine import privacy_mask


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalise_event(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _encoded_size(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8", errors="replace"))
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        raw = "[unavailable]"
    return len(raw.encode("utf-8", errors="replace"))


def _source_id(harness: str, event_name: str, payload: dict[str, Any], properties: dict[str, Any]) -> str:
    explicit = _first(
        payload.get("prompt_id"),
        payload.get("tool_use_id"),
        payload.get("toolUseId"),
        payload.get("tool_call_id"),
        payload.get("toolCallId"),
        payload.get("message_id"),
        payload.get("messageId"),
        payload.get("messageID"),
        payload.get("uuid"),
        payload.get("id"),
        properties.get("callID"),
        properties.get("callId"),
        properties.get("id"),
        payload.get("turn_id"),
        payload.get("turnId"),
    )
    if not explicit:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        explicit = hashlib.sha256(canonical.encode("utf-8", errors="replace")).hexdigest()[:24]
    return f"{harness}:{event_name}:{explicit}"[:200]


def map_hook_payload(harness: str, payload: dict[str, Any]) -> tuple[str, str, tuple[EventInput, ...]]:
    """Return ``(session_id, cwd, events)`` for one harness hook payload."""
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be an object")
    harness = _first(harness).lower()
    if not harness:
        raise ValueError("harness is required")

    properties = _mapping(payload.get("properties"))
    session_obj = _mapping(payload.get("session"))
    property_session = _mapping(properties.get("session"))
    session_id = _first(
        payload.get("session_id"),
        payload.get("sessionId"),
        payload.get("sessionID"),
        session_obj.get("id"),
        properties.get("session_id"),
        properties.get("sessionId"),
        properties.get("sessionID"),
        property_session.get("id"),
    )
    cwd = _first(
        payload.get("cwd"),
        payload.get("directory"),
        payload.get("worktree"),
        properties.get("cwd"),
        properties.get("directory"),
        properties.get("worktree"),
        session_obj.get("cwd"),
    )
    if not session_id:
        raise ValueError("hook payload does not contain a session identifier")
    if not cwd:
        raise ValueError("hook payload does not contain a working directory")

    raw_event = _first(
        payload.get("hook_event_name"),
        payload.get("event_name"),
        payload.get("type"),
        properties.get("type"),
    )
    event_name = _normalise_event(raw_event)
    source_id = _source_id(harness, event_name or "event", payload, properties)

    starts = {"sessionstart", "sessioncreated", "sessionstartup", "sessionresume", "sessionstartedevent"}
    idles = {"stop", "turnend", "sessionidle", "sessionstop"}
    ends = {"sessionend", "sessionshutdown", "sessiondeleted"}
    user_messages = {"userpromptsubmit", "input", "userprompt", "messageuser"}
    assistant_messages = {"messageupdated", "messageend", "assistantmessage", "assistant"}
    tool_calls = {"pretooluse", "toolexecutebefore", "toolcall", "toolstart", "toolexecutionstart"}
    tool_results = {"posttooluse", "toolexecuteafter", "toolresult", "toolend", "toolexecutionend"}

    if event_name in starts:
        event = EventInput(source_id, "status_change", {"from": "starting", "to": "active"})
        return session_id, cwd, (event,)
    if event_name in idles:
        event = EventInput(source_id, "status_change", {"from": "active", "to": "idle"})
        return session_id, cwd, (event,)
    if event_name in ends:
        event = EventInput(source_id, "status_change", {"from": "active", "to": "closed"})
        return session_id, cwd, (event,)

    if event_name in user_messages:
        content = payload.get(
            "prompt",
            payload.get("text", payload.get("content", properties.get("content", ""))),
        )
        declared_size = payload.get("content_size")
        chars = (
            declared_size
            if isinstance(declared_size, int) and not isinstance(declared_size, bool) and declared_size >= 0
            else _encoded_size(content)
        )
        event = EventInput(
            source_id,
            "message",
            {"role": "user", "chars": chars, "note": "user message"},
        )
        return session_id, cwd, (event,)

    if event_name in assistant_messages:
        message = _mapping(payload.get("message"))
        content = payload.get(
            "last_assistant_message",
            payload.get("content", message.get("content", properties.get("content", ""))),
        )
        event = EventInput(
            source_id,
            "message",
            {"role": "assistant", "chars": _encoded_size(content), "note": "assistant reply"},
        )
        return session_id, cwd, (event,)

    if event_name in tool_calls:
        tool = privacy_mask(
            _first(
                payload.get("tool_name"),
                payload.get("toolName"),
                properties.get("tool"),
                properties.get("tool_name"),
                "tool",
            )
        ) or "tool"
        inputs = payload.get(
            "tool_input",
            payload.get("input", payload.get("args", properties.get("input", {}))),
        )
        args = len(inputs) if isinstance(inputs, dict) else (1 if inputs else 0)
        event = EventInput(
            source_id,
            "tool_call",
            {"tool": tool, "args": args, "note": f"invoked {tool}"},
        )
        return session_id, cwd, (event,)

    if event_name in tool_results:
        tool = privacy_mask(
            _first(
                payload.get("tool_name"),
                payload.get("toolName"),
                properties.get("tool"),
                properties.get("tool_name"),
                "tool",
            )
        ) or "tool"
        content = payload.get(
            "tool_response",
            payload.get("content", payload.get("result", properties.get("output"))),
        )
        is_error = bool(
            payload.get("is_error")
            or payload.get("isError")
            or payload.get("error")
            or properties.get("error")
        )
        event = EventInput(
            source_id,
            "tool_result",
            {"tool": tool, "status": "error" if is_error else "ok", "size": _encoded_size(content)},
        )
        return session_id, cwd, (event,)

    return session_id, cwd, ()
