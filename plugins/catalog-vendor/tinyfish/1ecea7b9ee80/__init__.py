"""Directory-plugin entry point loaded by ``duckwork plugins install``."""

from __future__ import annotations

try:
    from .tinyfish_duckwork import __version__, register
except ImportError:  # pip installs import the packaged module directly
    from tinyfish_duckwork import __version__, register

__all__ = ["__version__", "register"]
