"""Test bootstrap: import the plugin directory as the package ``mcp_serve_plugin``.

The Duckwork plugin loader imports a directory plugin as a package (``duckwork_plugins.<slug>``) so the
relative imports in ``__init__.py`` resolve; tests mirror that under a stable alias. Duckwork core
(``duckwork_cli``, ``model_tools``, ``duckwork_state``) must be importable: run with a duckwork-agent
checkout on ``PYTHONPATH``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PACKAGE = "mcp_serve_plugin"
_ROOT = Path(__file__).resolve().parents[1]

# ``python -m pytest`` from the plugin dir puts it on sys.path, where its modules could shadow core's.
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _ROOT]


def _load_plugin_package():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, _ROOT / "__init__.py", submodule_search_locations=[str(_ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


_load_plugin_package()


@pytest.fixture(autouse=True)
def _duckwork_home(tmp_path, monkeypatch):
    """Every test gets its own profile home: config.yaml and state.db land there, never in a real one."""
    (tmp_path / "duckwork").mkdir()
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "duckwork"))


@pytest.fixture
def require_mcp_2_sdk():
    """Skip tests that drive the real mcp 2.x server API when an older SDK is installed."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        found = version("mcp")
    except PackageNotFoundError:
        pytest.skip("requires the mcp package")
    if int(found.split(".")[0]) < 2:
        pytest.skip(f"requires mcp>=2 (found {found})")


class _RootIsNotATestPackage:
    """The plugin dir *is* a package (``__init__.py`` with relative imports), so pytest would collect it
    as a test ``Package`` and import that ``__init__.py`` standalone, where the relative imports cannot
    resolve. Collect it as a plain directory instead (registered globally: the root's collector is
    created through its parent's hook proxy, which never sees a conftest inside the root)."""

    @pytest.hookimpl(tryfirst=True)
    def pytest_collect_directory(self, path, parent):
        if Path(path).resolve() == _ROOT:
            return pytest.Dir.from_parent(parent, path=path)
        return None


def pytest_configure(config):
    if not config.pluginmanager.has_plugin("mcp-serve-root"):
        config.pluginmanager.register(_RootIsNotATestPackage(), "mcp-serve-root")
