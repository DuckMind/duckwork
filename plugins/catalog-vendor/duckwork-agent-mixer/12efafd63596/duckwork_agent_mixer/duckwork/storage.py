"""Shared Duckwork session storage; CLI harness storage remains independent."""
from __future__ import annotations

from pathlib import Path

from . import host
from ..core.store import FileStore


def state_store() -> FileStore:
    home = host.duckwork_home()
    if home is None:
        raise RuntimeError("Duckwork home is unavailable; refusing to use a separate panel store")
    return FileStore(Path(home) / "plugin-data" / "duckwork-agent-mixer" / "sessions", strict=True)


def config_context():
    """Use the host's public namespaced facade, including its managed-config guards.

    This context is used only for config access. No plugins are loaded or hooks
    registered by the API process.
    """
    from duckwork_cli.plugins import PluginContext, PluginManifest, PluginManager

    return PluginContext(PluginManifest(name="duckwork-agent-mixer"), PluginManager())
