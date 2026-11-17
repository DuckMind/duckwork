# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""duckwork-agent-memory — LanceDB-backed MemoryProvider plugin for Duckwork Agent.

Loaded by Duckwork's memory plugin discovery system. The `register(ctx)` entry
point below is called with a plugin context that exposes
`register_memory_provider()`.

This module is a thin entry point: the plugin implementation lives in the
``src`` subpackage so the repo root stays legible. We only re-export the
provider here.
"""
from __future__ import annotations

if not __package__:
    # Loaded as a top-level module without a package context (e.g. directly
    # from the repo root by the benchmark/test harness). Manufacture a package
    # rooted at this directory so the ``src`` subpackage and its relative
    # imports resolve.
    import importlib
    import sys
    from pathlib import Path

    package_name = "duckwork_agent_memory"
    package = sys.modules.setdefault(package_name, sys.modules[__name__])
    package.__path__ = [str(Path(__file__).parent)]
    LanceDBMemoryProvider = importlib.import_module(
        f"{package_name}.src.provider"
    ).LanceDBMemoryProvider
else:
    from .src.provider import LanceDBMemoryProvider


def register(ctx) -> None:
    """Register the LanceDB memory provider with the Duckwork plugin context."""
    ctx.register_memory_provider(LanceDBMemoryProvider())


__all__ = ["LanceDBMemoryProvider", "register"]
