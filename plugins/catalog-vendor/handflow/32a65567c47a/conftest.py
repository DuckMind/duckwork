"""pytest bootstrap.

The repo root holds ``__init__.py`` (it *is* the plugin package), so pytest must
not try to collect that file as a test module of the rootdir package — hence
``collect_ignore`` here plus ``--import-mode=importlib`` in pyproject.toml.

Shared *helpers* live in ``tests/helpers.py`` (importable via the ``pythonpath``
ini setting); this file only holds fixtures, which pytest can only find in a
conftest.
"""

from __future__ import annotations

import pytest

collect_ignore = ["__init__.py"]


@pytest.fixture()
def hf_home(tmp_path, monkeypatch):
    """Point the store at a throwaway dir, so a passing suite never touches live plans."""
    home = tmp_path / "handflow"
    monkeypatch.setenv("HANDFLOW_HOME", str(home))
    return home
