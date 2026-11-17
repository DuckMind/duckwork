"""Import the plugin the way Duckwork does, with no Duckwork install.

Duckwork imports a directory plugin as a package with ``submodule_search_locations`` set to the plugin
folder. The repo folder is ``bot-cabinet-v2``, which isn't an importable name, so tests load it as
``bot_cabinet_v2``. Every test module does ``from _load import sub``.
"""

from __future__ import annotations

import atexit
import importlib
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "bot_cabinet_v2"

# Isolation. Every test run gets its own Duckwork home and its own Cabinet data folder, set before the plugin
# is imported, so no test can read or write the user's real ~/.duckwork. tests/test_isolation.py proves it.
# CABINET_SANDBOX_LAYOUT=home (the harness sets it) lays the sandbox out like a real install instead: Duckwork's home is
# <sandbox>/home/.duckwork and Cabinet's folder is .duckwork/state/bot-cabinet-v2, so the page shows ~/.duckwork/profiles/<name>.
def _real_user_home() -> Path:
    """The person's real home folder, read before HOME is pointed at the sandbox (pwd on macOS and Linux)."""
    try:
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except ImportError:  # Windows: no pwd module; Path.home() reads USERPROFILE, which nothing here changes
        return Path.home()


REAL_USER_HOME = _real_user_home()
SANDBOX = Path(tempfile.mkdtemp(prefix="cabinet-test-"))
os.environ["HOME"] = str(SANDBOX / "home")
if os.name == "nt":  # Path.home() reads USERPROFILE on Windows, not HOME
    os.environ["USERPROFILE"] = str(SANDBOX / "home")
if os.environ.get("CABINET_SANDBOX_LAYOUT") == "home":
    _DUCKWORK = SANDBOX / "home" / ".duckwork"
    os.environ["DUCKWORK_HOME"] = str(_DUCKWORK)
    os.environ["CABINET_DATA_DIR"] = str(_DUCKWORK / "state" / "bot-cabinet-v2")
else:
    _DUCKWORK = SANDBOX / "duckwork-home"
    os.environ["DUCKWORK_HOME"] = str(_DUCKWORK)
    os.environ["CABINET_DATA_DIR"] = str(SANDBOX / "cabinet-data")
(SANDBOX / "home").mkdir(parents=True, exist_ok=True)
(_DUCKWORK / "profiles").mkdir(parents=True, exist_ok=True)
atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)


def _load():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(PACKAGE, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(ROOT)]
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


pkg = _load()


def sub(name: str):
    return importlib.import_module(f"{PACKAGE}.{name}")
