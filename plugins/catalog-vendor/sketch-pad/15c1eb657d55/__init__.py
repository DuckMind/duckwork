"""sketch-pad — mouse sketch on Desktop, attach PNG to the next chat send."""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = str(Path(__file__).resolve().parent)
if _DIR in sys.path:
    sys.path.remove(_DIR)
sys.path.insert(0, _DIR)

import sketch_context
import sketch_schemas
import sketch_tools


def _handle_slash(ctx, raw_args: str) -> str:
    del ctx
    verb = ((raw_args or "").strip().split() or ["last"])[0].lower()
    if verb in {"last", "show", "path"}:
        return sketch_tools.sketch_pad_last({})
    return "Usage:\n  /sketch          — path of the last confirmed drawing\n  /sketch last     — same"


def register(ctx) -> None:
    sketch_context.set_ctx(ctx)
    ctx.register_tool(
        name="sketch_pad_last",
        toolset="sketch_pad",
        schema=sketch_schemas.SKETCH_PAD_LAST,
        handler=sketch_tools.sketch_pad_last,
    )
    try:
        ctx.register_command(
            "sketch",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Path of the last Sketch Pad drawing",
            args_hint="last",
        )
    except TypeError:
        ctx.register_command(
            "sketch",
            handler=lambda raw: _handle_slash(ctx, raw),
            description="Path of the last Sketch Pad drawing",
        )

    skill_md = Path(__file__).parent / "skills" / "sketch-pad" / "SKILL.md"
    if skill_md.is_file():
        try:
            ctx.register_skill("sketch-pad", skill_md)
        except TypeError:
            ctx.register_skill("sketch-pad", str(skill_md))
