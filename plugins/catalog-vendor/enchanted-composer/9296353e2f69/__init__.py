"""Enchanted Composer unified Duckwork plugin."""

__all__ = ["__version__", "register"]

__version__ = "0.2.7"


def register(_ctx: object) -> None:
    """Expose the native Duckwork plugin entry point; dashboard routes load separately."""
