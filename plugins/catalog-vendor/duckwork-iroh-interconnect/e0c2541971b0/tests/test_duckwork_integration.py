"""E2E test: the plugin loads through the REAL Duckwork PluginManager.

Contract (plan §7 Duckwork integration tests):
- Discovery from ~/.duckwork/plugins/ with plugin.yaml + register(ctx).
- User plugins are gated by plugins.enabled in config.yaml (fail-closed);
  the test enables the plugin explicitly through that documented surface.
- The four tools register into the global registry with the real
  registration path (not a mock ctx).
- Tools dispatch with the actual args-dict convention.
- Runs against a temp DUCKWORK_HOME; restores global registry state after.
"""

import json
import sys
import time
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
DUCKWORK_REPO = Path.home() / ".duckwork" / "duckwork-agent"

pytestmark = [
    pytest.mark.skipif(
        not DUCKWORK_REPO.exists(), reason="Duckwork source checkout not found"
    ),
    pytest.mark.skipif(
        pytest.importorskip("yaml", reason="PyYAML is required by Duckwork") is None,
        reason="PyYAML is required by Duckwork",
    ),
]

_TOOL_NAMES = (
    "iroh_peer_status",
    "iroh_peer_list",
    "iroh_peer_pair",
    "iroh_peer_make_ticket",
    "iroh_peer_call",
    "iroh_peer_settings",
    "iroh_send_file",
    "iroh_fetch_file",
    "iroh_transfer_status",
)


@pytest.fixture()
def duckwork_env(tmp_path, monkeypatch):
    """Temp DUCKWORK_HOME with the plugin installed + enabled."""
    home = tmp_path / "duckwork-home"
    plugins_dir = home / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "duckwork-iroh-interconnect").symlink_to(PLUGIN_DIR)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - duckwork-iroh-interconnect\n"
    )
    monkeypatch.setenv("DUCKWORK_HOME", str(home))
    monkeypatch.setenv("DUCKWORK_IROH_STATE_DIR", str(home / "iroh-interconnect"))
    monkeypatch.syspath_prepend(str(DUCKWORK_REPO))
    yield home

    # Unregister plugin tools so global registry state doesn't leak between
    # tests (the real manager unload path also does this).
    try:
        from tools.registry import registry

        for name in _TOOL_NAMES:
            registry.deregister(name)
    except Exception:
        pass


def _load_plugin():
    import duckwork_cli.plugins as plugin_system

    plugin_system.discover_plugins(force=True)
    return plugin_system.get_plugin_manager()


def test_real_plugin_manager_discovers_and_registers(duckwork_env):
    manager = _load_plugin()
    loaded = manager._plugins.get("duckwork-iroh-interconnect")
    assert loaded is not None, f"loaded keys: {list(manager._plugins)}"
    assert loaded.enabled, f"plugin not enabled: {loaded.error}"
    assert loaded.error is None
    assert set(loaded.tools_registered) == set(_TOOL_NAMES)

    from tools.registry import registry

    for name in _TOOL_NAMES:
        entry = registry.get_entry(name)
        assert entry is not None, f"{name} missing from registry"
        assert entry.toolset == "iroh"


def test_registered_tool_dispatches_end_to_end(duckwork_env, monkeypatch):
    # Keep the sidecar out of the picture for this dispatch check.
    monkeypatch.setenv("DUCKWORK_IROH_SIDECAR", "/nonexistent/sidecar")
    _load_plugin()
    from tools.registry import registry

    raw = registry.get_entry("iroh_peer_status").handler({}, task_id=None)
    out = json.loads(raw)
    assert out["success"] is True
    assert out["sidecar_available"] is False  # env override hides any binary
    assert (duckwork_env / "iroh-interconnect" / "peers.json").exists()


def test_pair_then_call_fail_closed(duckwork_env, monkeypatch):
    monkeypatch.setenv("DUCKWORK_IROH_SIDECAR", "/nonexistent/sidecar")
    _load_plugin()
    from tools.registry import registry

    ticket = (
        "duckwork-iroh://pair?peer=e2epeer123456&secret=longenoughsecretvalue42"
        f"&ts={int(time.time())}&nonce={'ab12cd34ef56ab12cd34ef56ab12cd34'}"
    )
    pair_out = json.loads(
        registry.get_entry("iroh_peer_pair").handler(
            {"ticket": ticket, "confirm": True}, task_id=None
        )
    )
    assert pair_out["success"] is True

    call_out = json.loads(
        registry.get_entry("iroh_peer_call").handler(
            {"peer": "e2epeer123456", "message": "hi"}, task_id=None
        )
    )
    # No sidecar binary in this env -> must fail closed with a clear error.
    assert call_out["success"] is False
    assert "sidecar" in call_out["error"].lower()


def test_disabled_plugin_stays_unregistered(duckwork_env, monkeypatch):
    """Without the enable gate, a user plugin must NOT register tools."""
    (duckwork_env / "config.yaml").write_text("plugins: {}\n")
    manager = _load_plugin()
    loaded = manager._plugins.get("duckwork-iroh-interconnect")
    assert loaded is not None
    assert not loaded.enabled
    assert loaded.tools_registered == []
