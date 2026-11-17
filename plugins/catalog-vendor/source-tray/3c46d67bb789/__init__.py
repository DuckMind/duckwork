"""source-tray — session URLs from web_search / web_extract / browser_navigate."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import tray_context
import tray_hooks
import tray_schemas
import tray_tools


def _handle_slash(ctx, raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    verb = parts[0].lower() if parts else "list"
    if verb in {"list", "show", "md", "markdown"}:
        return ctx.dispatch_tool("source_tray_list", {"markdown": True})
    if verb in {"clear", "reset"}:
        return ctx.dispatch_tool("source_tray_clear", {})
    return (
        "Usage:\n"
        "  /sources          — markdown list of URLs this session\n"
        "  /sources list     — same\n"
        "  /sources clear    — empty the tray"
    )


def register(ctx) -> None:
    tray_context.set_ctx(ctx)

    ctx.register_tool(
        name="source_tray_list",
        toolset="source_tray",
        schema=tray_schemas.SOURCE_TRAY_LIST,
        handler=tray_tools.source_tray_list,
    )
    ctx.register_tool(
        name="source_tray_clear",
        toolset="source_tray",
        schema=tray_schemas.SOURCE_TRAY_CLEAR,
        handler=tray_tools.source_tray_clear,
    )
    ctx.register_hook("post_tool_call", tray_hooks.on_post_tool_call)
    try:
        ctx.register_command(
            "sources",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="URLs this agent opened (search / extract / browser)",
            args_hint="list|clear",
        )
    except TypeError:
        ctx.register_command(
            "sources",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="URLs this agent opened (search / extract / browser)",
        )

    skill_md = Path(__file__).parent / "skills" / "source-tray" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("source-tray", skill_md)
        except TypeError:
            ctx.register_skill("source-tray", str(skill_md))
