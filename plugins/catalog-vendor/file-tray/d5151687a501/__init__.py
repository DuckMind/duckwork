"""file-tray — session paths from read_file / write_file / patch."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import file_context
import file_hooks
import file_schemas
import file_tools


def _handle_slash(ctx, raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    verb = parts[0].lower() if parts else "list"
    if verb in {"list", "show", "md", "markdown"}:
        return ctx.dispatch_tool("file_tray_list", {"markdown": True})
    if verb in {"clear", "reset"}:
        return ctx.dispatch_tool("file_tray_clear", {})
    return (
        "Usage:\n"
        "  /files          — markdown list of paths this session\n"
        "  /files list     — same\n"
        "  /files clear    — empty the tray"
    )


def register(ctx) -> None:
    file_context.set_ctx(ctx)

    ctx.register_tool(
        name="file_tray_list",
        toolset="file_tray",
        schema=file_schemas.FILE_TRAY_LIST,
        handler=file_tools.file_tray_list,
    )
    ctx.register_tool(
        name="file_tray_clear",
        toolset="file_tray",
        schema=file_schemas.FILE_TRAY_CLEAR,
        handler=file_tools.file_tray_clear,
    )
    ctx.register_hook("post_tool_call", file_hooks.on_post_tool_call)
    try:
        ctx.register_command(
            "files",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Paths this agent touched (read / write / patch)",
            args_hint="list|clear",
        )
    except TypeError:
        ctx.register_command(
            "files",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Paths this agent touched (read / write / patch)",
        )

    skill_md = Path(__file__).parent / "skills" / "file-tray" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("file-tray", skill_md)
        except TypeError:
            ctx.register_skill("file-tray", str(skill_md))
