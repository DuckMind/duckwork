"""Test bootstrap: put a duckwork-agent checkout on sys.path.

The plugin imports the host's ``providers`` package at module load, so the
tests need a duckwork-agent source tree. Resolution order:

1. ``DUCKWORK_AGENT_REPO`` env var (CI pins an exact upstream commit).
2. A sibling ``duckwork-agent`` directory (developer convenience).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _duckwork_repo() -> Path | None:
    env = os.environ.get("DUCKWORK_AGENT_REPO", "").strip()
    candidates = [Path(env)] if env else []
    candidates.append(PACKAGE_ROOT.parent / "duckwork-agent")
    for candidate in candidates:
        if (candidate / "providers" / "base.py").is_file():
            return candidate.resolve()
    return None


DUCKWORK_REPO = _duckwork_repo()


def pytest_configure(config):
    if DUCKWORK_REPO is None:
        raise pytest.UsageError(
            "duckwork-agent checkout not found. Set DUCKWORK_AGENT_REPO to a "
            "clone of https://github.com/DuckMind/duckwork"
        )
    if str(DUCKWORK_REPO) not in sys.path:
        sys.path.insert(0, str(DUCKWORK_REPO))


@pytest.fixture(scope="session")
def plugin_module():
    """Import the package root ``__init__.py`` exactly once per session."""
    spec = importlib.util.spec_from_file_location(
        "telnyx_provider_plugin", PACKAGE_ROOT / "__init__.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def telnyx_profile(plugin_module):
    return plugin_module.telnyx
