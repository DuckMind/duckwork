"""Deterministic projection from privacy-safe events to summary entries."""

from __future__ import annotations

from spectator.core.contracts import SessionEvent, SummaryEntry


def _text(value: object, fallback: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _count(value: object) -> int:
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def project_summary(session_id: str, event: SessionEvent) -> SummaryEntry:
    summary = event.summary
    if event.type == "message":
        role = _text(summary.get("role"), "session").title()
        note = _text(summary.get("note"), "message")
        chars = _count(summary.get("chars", 0))
        title = f"{role} update"
        body = f"{note} · {chars} characters"
        kind = "conversation"
    elif event.type == "tool_call":
        tool = _text(summary.get("tool"), "tool")
        note = _text(summary.get("note"), "tool invoked")
        args = _count(summary.get("args", 0))
        title = f"Tool call: {tool}"
        body = f"{note} · {args} argument{'s' if args != 1 else ''}"
        kind = "tool"
    elif event.type == "tool_result":
        tool = _text(summary.get("tool"), "tool")
        status = _text(summary.get("status"), "unknown")
        size = _count(summary.get("size", 0))
        title = f"Tool result: {tool}"
        body = f"{status} · {size} bytes"
        kind = "tool"
    elif event.type == "status_change":
        before = _text(summary.get("from"), "unknown")
        after = _text(summary.get("to"), "unknown")
        title = "Session status"
        body = f"{before} → {after}"
        kind = "status"
    else:
        title = "Session activity"
        body = "A privacy-safe activity event was recorded"
        kind = "activity"

    return SummaryEntry(
        entry_id=f"{session_id}:{event.cursor}",
        cursor=event.cursor,
        title=title,
        body=body,
        kind=kind,
        timestamp=event.timestamp,
    )
