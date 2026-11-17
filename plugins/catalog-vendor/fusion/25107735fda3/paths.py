"""Shared, portable path resolution for the fusion plugin.

Runs inside Duckwork, so paths must follow DUCKWORK_HOME (profile-aware) rather
than a hardcoded home. The plugin never knows Jordan's machine layout.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def duckwork_home() -> Path:
    """DUCKWORK_HOME if set, else ~/.duckwork (matches Duckwork' own default)."""
    ev = os.environ.get("DUCKWORK_HOME")
    if ev:
        return Path(ev)
    return Path.home() / ".duckwork"


def duckwork_python() -> str:
    """Python interpreter for subprocess script calls (honor DUCKWORK_PYTHON)."""
    return os.environ.get("DUCKWORK_PYTHON") or sys.executable or "python3"


def duckwork_bin() -> str:
    """Locate the `duckwork` executable, honoring DUCKWORK_BIN/DUCKWORK_HOME.

    Order: explicit DUCKWORK_BIN env -> `duckwork` on PATH -> the usual venv
    locations under DUCKWORK_HOME -> bare 'duckwork' (let PATH try).
    """
    ev = os.environ.get("DUCKWORK_BIN")
    if ev:
        return ev
    found = shutil.which("duckwork")
    if found:
        return found
    base = duckwork_home()
    for cand in (
        base / "duckwork-agent" / "venv" / "bin" / "duckwork",
        base / "duckwork-agent" / ".venv" / "bin" / "duckwork",
        base / "bin" / "duckwork",
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return "duckwork"
