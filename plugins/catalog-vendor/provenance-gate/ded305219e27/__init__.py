# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Duckwork entry point for provenance-gate: registration only.

The imports live inside ``register`` so this file can also be imported on its own (pytest
imports a directory's ``__init__.py`` when it collects tests below it).
"""

from __future__ import annotations


def register(ctx) -> None:
    from .provenance_gate import cli
    from .provenance_gate.hooks import Gate

    gate = Gate()
    ctx.register_hook("pre_llm_call", gate.pre_llm_call)
    ctx.register_hook("pre_tool_call", gate.pre_tool_call)
    ctx.register_cli_command("provenance-gate", help=cli.HELP, setup_fn=cli.setup,
                             handler_fn=cli.make_handler(), description=cli.DESCRIPTION)
