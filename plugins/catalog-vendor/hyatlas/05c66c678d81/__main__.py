# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Standalone ``python -m plugins.memory.hyatlas`` entry point.

Mirrors the pattern Hindsight uses for duckwork_hindsight.memory —
runs the plugin's CLI without needing the parent Duckwork binary on PATH.
"""

import sys

from .cli import _main_standalone

if __name__ == "__main__":
    sys.exit(_main_standalone())
