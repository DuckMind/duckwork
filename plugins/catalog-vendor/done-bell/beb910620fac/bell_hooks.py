"""Turn-end and approval observers. Never raise."""

from __future__ import annotations

import bell_store


def on_session_end(
    session_id: str = "",
    completed: bool = False,
    interrupted: bool = False,
    platform: str = "",
    **kwargs,
) -> None:
    del kwargs
    try:
        if interrupted:
            kind = "interrupted"
            detail = "interrupted"
            title = "Duckwork stopped"
            body = "The turn was interrupted."
        elif completed:
            kind = "done"
            detail = "completed"
            title = "Duckwork is done"
            body = "The agent finished this turn."
        else:
            kind = "done"
            detail = "ended"
            title = "Duckwork is done"
            body = "The turn ended."
        bell_store.record_event(
            kind,
            session_id=str(session_id or ""),
            platform=str(platform or ""),
            detail=detail,
            needs_you=False,
        )
        bell_store.ring_cli(title, body, platform_name=str(platform or ""))
    except Exception:
        return


def on_pre_approval_request(platform: str = "", session_key: str = "", **kwargs) -> None:
    del kwargs
    try:
        if not bell_store.get_settings().get("needs_you"):
            return
        bell_store.record_event(
            "needs_you",
            session_id=str(session_key or ""),
            platform=str(platform or ""),
            detail="approval",
            needs_you=True,
        )
        bell_store.ring_cli(
            "Duckwork needs you",
            "Waiting for approval.",
            platform_name=str(platform or ""),
        )
    except Exception:
        return


def on_post_approval_response(**kwargs) -> None:
    del kwargs
    try:
        bell_store.clear_needs_you()
    except Exception:
        return


def on_agent_loop_stopped(
    session_key: str = "",
    platform: str = "",
    reason: str = "",
    **kwargs,
) -> None:
    del kwargs
    try:
        bell_store.record_event(
            "interrupted",
            session_id=str(session_key or ""),
            platform=str(platform or ""),
            detail=str(reason or "stopped")[:120],
            needs_you=False,
        )
    except Exception:
        return
