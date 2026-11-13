"""Resolve DUCKWORK_HOME for standalone skill scripts.

Skill scripts may run outside the Duckwork process (e.g. system Python,
nix env, CI) where ``duckwork_constants`` is not importable.  This module
provides the same ``get_duckwork_home()`` and ``display_duckwork_home()``
contracts as ``duckwork_constants`` without requiring it on ``sys.path``.

When ``duckwork_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``duckwork_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``DUCKWORK_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from duckwork_constants import display_duckwork_home
    from duckwork_constants import get_duckwork_home
except (ModuleNotFoundError, ImportError):

    def get_duckwork_home() -> Path:
        """Return the Duckwork home directory (default: ~/.duckwork).

        Mirrors ``duckwork_constants.get_duckwork_home()``."""
        val = os.environ.get("DUCKWORK_HOME", "").strip()
        return Path(val) if val else Path.home() / ".duckwork"

    def display_duckwork_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``duckwork_constants.display_duckwork_home()``."""
        home = get_duckwork_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
