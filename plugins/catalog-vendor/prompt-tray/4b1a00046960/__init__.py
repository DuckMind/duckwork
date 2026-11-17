"""prompt-tray — saved composer prompts for Duckwork Desktop."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import prompt_context
import prompt_schemas
import prompt_tools


def _handle_slash(ctx, raw_args: str) -> str:
    del ctx
    verb = ((raw_args or "").strip().split() or ["list"])[0].lower()
    if verb in {"list", "show", "md", "markdown"}:
        return prompt_tools.prompt_tray_list({"markdown": True})
    return (
        "Usage:\n"
        "  /prompts          — saved Prompt Tray snippets\n"
        "  /prompts list     — same"
    )


def register(ctx) -> None:
    prompt_context.set_ctx(ctx)
    ctx.register_tool(
        name="prompt_tray_list",
        toolset="prompt_tray",
        schema=prompt_schemas.PROMPT_TRAY_LIST,
        handler=prompt_tools.prompt_tray_list,
    )
    try:
        ctx.register_command(
            "prompts",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Saved Prompt Tray snippets",
            args_hint="list",
        )
    except TypeError:
        ctx.register_command(
            "prompts",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Saved Prompt Tray snippets",
        )

    skill_md = Path(__file__).parent / "skills" / "prompt-tray" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("prompt-tray", skill_md)
        except TypeError:
            ctx.register_skill("prompt-tray", str(skill_md))
