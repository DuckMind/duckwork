"""Import the plugin as the package ``inbox_plugin`` and give every test its own empty
DUCKWORK_HOME (and kanban root), so nothing reads or writes the real ~/.duckwork."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_plugin_package() -> None:
    if "inbox_plugin" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "inbox_plugin", PLUGIN_ROOT / "__init__.py", submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["inbox_plugin"] = module
    spec.loader.exec_module(module)


_load_plugin_package()
# Test helpers (inbox_seed.py) import by name; --import-mode=importlib keeps tests/ off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def duckwork_home(tmp_path, monkeypatch):
    home = tmp_path / "duckwork-home"
    home.mkdir()
    monkeypatch.setenv("DUCKWORK_HOME", str(home))
    # The kanban board lives at the default Duckwork root, which resolves to the REAL ~/.duckwork
    # whenever tmp_path sits under it; pin it to the temp home explicitly.
    monkeypatch.setenv("DUCKWORK_KANBAN_HOME", str(home))
    for var in ("DUCKWORK_KANBAN_DB", "DUCKWORK_KANBAN_BOARD", "DUCKWORK_DELEGATED_CHILD_CONTEXT"):
        monkeypatch.delenv(var, raising=False)
    return home
