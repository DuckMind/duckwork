"""Resolve DUCKWORK_HOME for standalone skill scripts.

Skill scripts may run outside the Duckwork process (system Python, nix env,
CI) where ``duckwork_constants`` is not importable.  This module provides the
same ``get_duckwork_home()`` contract without requiring it on ``sys.path``.

When ``duckwork_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from duckwork_constants import get_duckwork_home
except (ModuleNotFoundError, ImportError):

    def get_duckwork_home() -> Path:
        """Return the Duckwork home directory (default: ``~/.duckwork``)."""
        val = os.environ.get("DUCKWORK_HOME", "").strip()
        return Path(val) if val else Path.home() / ".duckwork"
