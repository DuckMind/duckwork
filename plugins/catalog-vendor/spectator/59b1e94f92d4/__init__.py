"""Duckwork native plugin entrypoint.

The product core remains harness-neutral. This file only hands Duckwork' public
PluginContext to the isolated Duckwork adapter.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent
_SRC = _PLUGIN_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from spectator.duckwork_plugin import register

__all__ = ["register"]
