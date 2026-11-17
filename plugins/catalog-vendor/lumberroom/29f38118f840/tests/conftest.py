# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Loads the repository root as the package lumberroom_duckwork, the way a wheel install names it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_package() -> None:
    if "lumberroom_duckwork" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "lumberroom_duckwork", PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["lumberroom_duckwork"] = module
    spec.loader.exec_module(module)


_load_package()


@pytest.fixture
def duckwork_home(tmp_path, monkeypatch):
    home = tmp_path / "duckwork-home"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setenv("DUCKWORK_HOME", str(home))
    return home


@pytest.fixture
def cfg():
    from lumberroom_duckwork.config import LumberroomConfig

    return LumberroomConfig(base_url="http://fake.lumberroom.test", auth="token")


@pytest.fixture
def fake_engine():
    from fakes import FakeEngine

    return FakeEngine()
