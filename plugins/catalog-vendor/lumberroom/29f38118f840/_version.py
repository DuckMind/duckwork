# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""The plugin's version, in a module with no imports.

Duckwork loads cli.py under a synthetic parent package without running __init__.py, so a name
defined there is missing on that path. bridge.py and auth.py read the version from here instead.
"""

__version__ = "1.0.2"
