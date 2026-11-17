# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Directory-plugin entry point for Duckwork Agent."""

try:
    from .cognee_integration_duckwork import CogneeMemoryProvider
except ImportError:  # pragma: no cover - supports direct pytest/path imports.
    import sys
    from pathlib import Path

    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    from cognee_integration_duckwork import CogneeMemoryProvider


def register(ctx) -> None:
    """Register Cognee as the active Duckwork memory provider."""
    ctx.register_memory_provider(CogneeMemoryProvider())
