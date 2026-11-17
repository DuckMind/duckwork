# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
# Copyright 2026 bytecakelake
# SPDX-License-Identifier: Apache-2.0
"""Duckwork plugin entry shim.

Duckwork looks for ``plugin.yaml`` + ``__init__.py`` at the repo root. All real code lives in
``src/duckwork_gemini_media``; this file only makes it importable and delegates ``register``.
"""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from duckwork_gemini_media.plugin import register  # noqa: E402,F401
