"""ja-writing-guard: find and fix Japanese AI-writing tells in Duckwork Agent.

Registers:

- tool ``ja_writing_check`` (toolset ``ja_writing``): deterministic, offline
  check that returns a score, the surface threshold and positioned findings;
- hook ``transform_llm_output``: checks each final Japanese answer; reports by
  default, and rewrites over-threshold answers when ``mode: enforce`` is set;
- hook ``post_tool_call`` (read-only observer): notes turns in which a tool
  returned a ``MEDIA:`` attachment line, so enforce mode leaves those answers
  alone and another plugin's attachment is never dropped;
- slash command ``/ja-check``: check a text, or show the last answer's report;
- skill ``ja-writing-guard:rewrite-ja``: how to rewrite without changing meaning.

No network calls, no environment variables. In enforce mode only, the rewrite
uses ``ctx.llm`` (the user's own configured model) once or twice per flagged
answer.
"""

from __future__ import annotations

from pathlib import Path

from . import schemas, tools
from .hook import Guard


def register(ctx):
    guard = Guard(ctx)
    ctx.register_tool(
        name="ja_writing_check",
        toolset="ja_writing",
        schema=schemas.JA_WRITING_CHECK,
        handler=tools.ja_writing_check,
        emoji="🖋",
    )
    ctx.register_hook("transform_llm_output", guard.on_output)
    ctx.register_hook("post_tool_call", guard.on_tool_result)
    ctx.register_command(
        "ja-check",
        tools.make_command(guard),
        description="Check Japanese text for AI-style phrasing (no args: last answer's report) / 日本語の AI 的な言い回しを検査（引数なしで直前の返答の結果）",
        args_hint="[surface] <text>",
    )
    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)
