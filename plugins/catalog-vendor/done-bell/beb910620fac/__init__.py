"""done-bell — notify when a Duckwork turn finishes."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import bell_context
import bell_hooks
import bell_schemas
import bell_tools


def _handle_slash(ctx, raw_args: str) -> str:
    del ctx
    verb = ((raw_args or "").strip().split() or ["status"])[0].lower()
    if verb in {"status", "show", "list"}:
        return bell_tools.done_bell_status({"markdown": True})
    if verb in {"mute", "off"}:
        return bell_tools.done_bell_status({"mute": True, "markdown": True})
    if verb in {"unmute", "on"}:
        return bell_tools.done_bell_status({"mute": False, "markdown": True})
    return (
        "Usage:\n"
        "  /bell           — last Done Bell events\n"
        "  /bell status    — same\n"
        "  /bell mute      — silence notify + chime\n"
        "  /bell unmute    — turn the bell back on"
    )


def register(ctx) -> None:
    bell_context.set_ctx(ctx)
    ctx.register_tool(
        name="done_bell_status",
        toolset="done_bell",
        schema=bell_schemas.DONE_BELL_STATUS,
        handler=bell_tools.done_bell_status,
    )
    ctx.register_hook("on_session_end", bell_hooks.on_session_end)
    ctx.register_hook("pre_approval_request", bell_hooks.on_pre_approval_request)
    ctx.register_hook("post_approval_response", bell_hooks.on_post_approval_response)
    ctx.register_hook("agent_loop_stopped", bell_hooks.on_agent_loop_stopped)
    try:
        ctx.register_command(
            "bell",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Done Bell — last turn events, mute/unmute",
            args_hint="status|mute|unmute",
        )
    except TypeError:
        ctx.register_command(
            "bell",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Done Bell — last turn events, mute/unmute",
        )

    skill_md = Path(__file__).parent / "skills" / "done-bell" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("done-bell", skill_md)
        except TypeError:
            ctx.register_skill("done-bell", str(skill_md))
