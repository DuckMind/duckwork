"""Load the repo root as a package, the same way Duckwork loads an installed plugin directory."""

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PACKAGE = "financial_datasets_plugin"


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        PACKAGE, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def plugin():
    return sys.modules.get(PACKAGE) or _load_plugin()


@pytest.fixture
def api(plugin, monkeypatch):
    """Record every API request instead of sending it. Set `api.response` to shape the reply."""

    class FakeApi:
        def __init__(self):
            self.calls = []
            self.response = {}

        def get(self, path, params=None, paginated=False):
            self.calls.append({"method": "GET", "path": path, "params": params or {}, "paginated": paginated})
            return self.response

        def post(self, path, body):
            self.calls.append({"method": "POST", "path": path, "body": body})
            return self.response

    fake = FakeApi()
    monkeypatch.setattr(plugin.client, "get", fake.get)
    monkeypatch.setattr(plugin.client, "post", fake.post)
    return fake
