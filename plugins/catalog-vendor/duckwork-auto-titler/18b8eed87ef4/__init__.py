# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Duckwork plugin root entry.

Duckwork directory plugins require an ``__init__.py`` at the plugin root and
import the plugin directory as a module (duckwork_cli/plugins.py). This thin
shim exposes the ``duckwork_auto_titler`` package next to it to the loader.
Kept as a real file (not a symlink) so Windows checkouts without symlink
support still load.
"""
import sys
from pathlib import Path

_here = Path(__file__).parent
# Keep the plugin-directory spelling last: insert-at-front makes it win when
# the root entry is loaded through a symlinked Duckwork plugin directory.
for _c in (_here.resolve(), _here):
    if str(_c) not in sys.path:
        sys.path.insert(0, str(_c))

from duckwork_auto_titler import register  # noqa: E402

__all__ = ["register"]
