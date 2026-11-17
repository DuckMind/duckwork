"""command-tray — session shell commands from the terminal tool."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import cmd_context
import cmd_hooks
import cmd_schemas
import cmd_tools


def _handle_slash(ctx, raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    verb = parts[0].lower() if parts else "list"
    if verb in {"list", "show", "md", "markdown"}:
        return ctx.dispatch_tool("command_tray_list", {"markdown": True})
    if verb in {"clear", "reset"}:
        return ctx.dispatch_tool("command_tray_clear", {})
    return (
        "Usage:\n"
        "  /commands          — markdown list of commands this session\n"
        "  /commands list     — same\n"
        "  /commands clear    — empty the tray"
    )


def register(ctx) -> None:
    cmd_context.set_ctx(ctx)

    ctx.register_tool(
        name="command_tray_list",
        toolset="command_tray",
        schema=cmd_schemas.COMMAND_TRAY_LIST,
        handler=cmd_tools.command_tray_list,
    )
    ctx.register_tool(
        name="command_tray_clear",
        toolset="command_tray",
        schema=cmd_schemas.COMMAND_TRAY_CLEAR,
        handler=cmd_tools.command_tray_clear,
    )
    ctx.register_hook("post_tool_call", cmd_hooks.on_post_tool_call)
    try:
        ctx.register_command(
            "commands",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Shell commands this agent ran (terminal)",
            args_hint="list|clear",
        )
    except TypeError:
        ctx.register_command(
            "commands",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Shell commands this agent ran (terminal)",
        )

    skill_md = Path(__file__).parent / "skills" / "command-tray" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("command-tray", skill_md)
        except TypeError:
            ctx.register_skill("command-tray", str(skill_md))
