"""Duckwork plugin: Handflow — a Manus-style planning flow, native to Duckwork.

The agent writes a step plan before it works, marks each step as it goes, and
replans mid-flight; a dockable desktop pane shows the same plan live.

Import-safe and side-effect-free at import and inside ``register()``: the state
directory is resolved per call, never here (one process serves several profiles,
and the catalog capability probe imports this module in a bare interpreter with
nothing on disk).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_PLUGIN_DIR = str(Path(__file__).resolve().parent)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

try:  # loaded as a package by the plugin loader / capability probe
    from .handflow.tools import HANDLERS, SCHEMAS  # type: ignore
except ImportError:  # loaded as a bare module (sys.path root only)
    from handflow.tools import HANDLERS, SCHEMAS  # type: ignore

__all__ = ["register"]


def register(ctx: Any) -> None:
    """Wire the agent half: the ``handflow`` tool. The desktop half is ``desktop/plugin.js``."""
    for name, handler in HANDLERS.items():
        ctx.register_tool(name=name, toolset="handflow", schema=SCHEMAS[name], handler=handler)
