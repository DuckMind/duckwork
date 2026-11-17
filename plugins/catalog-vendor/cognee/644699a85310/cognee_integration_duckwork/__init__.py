# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Cognee memory provider plugin for Duckwork Agent."""

from .provider import CogneeMemoryProvider

__all__ = ["CogneeMemoryProvider", "register"]


def register(ctx) -> None:
    """Pip entry-point registration hook for Duckwork Agent."""
    ctx.register_memory_provider(CogneeMemoryProvider())
