"""Shared fixtures: isolated Duckwork home and Duckwork-style plugin load."""

from __future__ import annotations

import sys
import types

import pytest

from helpers import FIXTURES, load_plugin


@pytest.fixture(scope="session")
def plugin():
    return load_plugin()


@pytest.fixture(autouse=True)
def duckwork_home(tmp_path, monkeypatch):
    """Stub duckwork_constants.get_duckwork_home. DUCKWORK_HOME is not the boundary."""
    home = tmp_path / "duckwork-home"
    home.mkdir()
    monkeypatch.setenv("DUCKWORK_HOME", str(home))
    mod = types.ModuleType("duckwork_constants")
    mod.get_duckwork_home = lambda: str(home)
    monkeypatch.setitem(sys.modules, "duckwork_constants", mod)
    return home


@pytest.fixture
def fixtures_dir():
    return FIXTURES
