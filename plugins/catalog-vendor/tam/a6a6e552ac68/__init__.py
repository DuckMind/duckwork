"""total-agent-memory (TAM) memory provider for Duckwork Agent.

This directory is both the pip package and the Duckwork directory plugin (plugin.yaml sits next to
this file); Duckwork recognises it by the MemoryProvider / register_memory_provider marker below.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.1"


def register(ctx: Any) -> None:
    """Duckwork plugin entry point (directory plugin and ``duckwork_agent.memory_providers`` entry point)."""
    from .provider import TamMemoryProvider

    ctx.register_memory_provider(TamMemoryProvider())


__all__ = ["__version__", "register"]
