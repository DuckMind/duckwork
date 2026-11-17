# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Test isolation: never read or write the developer's real ~/.duckwork."""

from __future__ import annotations

import pytest

_TENUO_ENV = (
    "TENUO_WARRANT", "TENUO_SIGNING_KEY", "TENUO_TRUSTED_ROOT", "TENUO_CHILD_WARRANT",
    "TENUO_AUDIT_LOG", "TENUO_CONNECT_TOKEN", "TENUO_REQUIRE_SESSION_WARRANT",
    "DUCKWORK_KANBAN_TASK",
)


@pytest.fixture(autouse=True)
def _isolated_duckwork_home(tmp_path, monkeypatch):
    """Every test gets its own empty DUCKWORK_HOME and no inherited TENUO_* env."""
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "duckwork-home"))
    for name in _TENUO_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
