"""Make the plugin importable as a package and put Duckwork on sys.path when it is installed locally."""

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "openmail_plugin"

if PKG not in sys.modules:
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT)]
    sys.modules[PKG] = pkg

for candidate in (os.environ.get("DUCKWORK_AGENT_DIR"), Path.home() / ".duckwork" / "duckwork-agent"):
    if candidate and Path(candidate).joinpath("gateway").is_dir():
        sys.path.insert(0, str(candidate))
        break
