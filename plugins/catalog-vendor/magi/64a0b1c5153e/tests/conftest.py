import os
import sys
from contextvars import ContextVar
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def duckwork_home_context(monkeypatch):
    """Provide Duckwork' request-scoped home API to the isolated unit-test runtime."""
    home_override = ContextVar("test_duckwork_home_override", default=None)
    module = ModuleType("duckwork_constants")

    def set_duckwork_home_override(path):
        return home_override.set(None if path is None else str(path))

    def reset_duckwork_home_override(token):
        home_override.reset(token)

    def get_duckwork_home():
        override = home_override.get()
        if override:
            return Path(override)
        env_home = os.environ.get("DUCKWORK_HOME", "").strip()
        if env_home:
            return Path(env_home)
        return Path.home() / (".duckwork" + os.environ.get("DUCKWORK_DATA_DIR_SUFFIX", ""))

    module.set_duckwork_home_override = set_duckwork_home_override
    module.reset_duckwork_home_override = reset_duckwork_home_override
    module.get_duckwork_home = get_duckwork_home
    monkeypatch.setitem(sys.modules, "duckwork_constants", module)
    return module
