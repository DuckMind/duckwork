# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Duckwork directory-plugin entry point.

``duckwork plugins install tenuo-ai/duckwork-tenuo`` clones this repository into
``~/.duckwork/plugins/duckwork-tenuo/`` and imports this file as the plugin
module. ``pip install`` users never touch it: Duckwork finds the
``duckwork_agent.plugins`` entry point and imports ``duckwork_tenuo`` directly.

This shim makes the clone importable without putting the clone on
``sys.path``: if ``duckwork_tenuo`` is already installed it is reused,
otherwise the sibling package directory is loaded by path.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent / "duckwork_tenuo"


def _load_package():
    if "duckwork_tenuo" in sys.modules:
        return sys.modules["duckwork_tenuo"]
    try:
        return importlib.import_module("duckwork_tenuo")
    except ModuleNotFoundError as exc:
        if exc.name != "duckwork_tenuo":
            raise
    spec = importlib.util.spec_from_file_location(
        "duckwork_tenuo", _PKG_DIR / "__init__.py", submodule_search_locations=[str(_PKG_DIR)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load duckwork_tenuo from {_PKG_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["duckwork_tenuo"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop("duckwork_tenuo", None)
        raise
    return module


try:
    _pkg = _load_package()
except ModuleNotFoundError as exc:
    if exc.name in ("tenuo", "tenuo_core"):
        raise ModuleNotFoundError(
            "duckwork-tenuo needs the 'tenuo' package, which Duckwork does not install for "
            "plugins. Run: pip install 'tenuo>=0.3.2' in the environment Duckwork uses."
        ) from exc
    raise

register = _pkg.register
DuckworkGuard = _pkg.DuckworkGuard
DuckworkAuditEvent = _pkg.DuckworkAuditEvent

__all__ = ["register", "DuckworkGuard", "DuckworkAuditEvent"]
