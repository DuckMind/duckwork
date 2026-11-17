from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "resolve_capabilities",
    "resolve_launch",
    "resolve_probe",
    "resolve_project_summary",
    "resolve_import_media",
    "resolve_create_timeline",
    "resolve_append_to_current_timeline",
    "resolve_add_timeline_marker",
    "resolve_scan_media_folder",
    "resolve_create_scripted_timeline",
    "resolve_render_timeline",
    "resolve_render_status",
    "resolve_generate_fcpxml_timeline",
    "resolve_generate_marker_csv",
}


def _duckwork_agent_repo() -> Path:
    configured = os.environ.get("DUCKWORK_AGENT_REPO")
    candidates = [
        Path(configured).expanduser() if configured else None,
        PLUGIN_ROOT.parent / "duckwork-agent-pr",
        PLUGIN_ROOT.parent / "duckwork-agent",
    ]
    for candidate in candidates:
        if candidate and (candidate / "duckwork_cli" / "plugins.py").is_file():
            return candidate.resolve()
    pytest.fail(
        "A real Duckwork Agent checkout is required. Set DUCKWORK_AGENT_REPO to "
        "the checkout root before running this integration test."
    )


def test_real_pluginmanager_discovers_user_install_without_import_shadowing(
    tmp_path, monkeypatch
):
    """Exercise the exact standalone user-plugin discovery and load path."""
    duckwork_repo = _duckwork_agent_repo()
    duckwork_home = tmp_path / "duckwork-home"
    installed_plugin = duckwork_home / "plugins" / "davinci-resolve"
    installed_plugin.parent.mkdir(parents=True)
    shutil.copytree(
        PLUGIN_ROOT,
        installed_plugin,
        ignore=shutil.ignore_patterns(
            ".git", ".github", ".pytest_cache", "__pycache__", "tests"
        ),
    )
    (duckwork_home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - davinci-resolve\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("DUCKWORK_HOME", str(duckwork_home))
    monkeypatch.delenv("DUCKWORK_SAFE_MODE", raising=False)
    monkeypatch.delenv("DUCKWORK_BUNDLED_PLUGINS", raising=False)
    monkeypatch.delenv("DUCKWORK_ENABLE_PROJECT_PLUGINS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(duckwork_repo))

    import tools as duckwork_tools
    from duckwork_cli.plugins import PluginManager
    from tools.registry import registry

    for module_name in [
        name for name in sys.modules if name.startswith("duckwork_plugins.davinci_resolve")
    ]:
        sys.modules.pop(module_name, None)

    sys_path_before_load = list(sys.path)
    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["davinci-resolve"]
    assert loaded.manifest.source == "user"
    assert Path(loaded.manifest.path).resolve() == installed_plugin.resolve()
    assert loaded.enabled is True
    assert loaded.error is None, f"plugin failed to load: {loaded.error}"
    assert set(loaded.tools_registered) == EXPECTED_TOOLS
    assert loaded.module.__name__ == "duckwork_plugins.davinci_resolve"
    assert "duckwork_plugins.davinci_resolve.tools" in sys.modules

    entry = registry.get_entry("resolve_probe")
    assert entry is not None
    assert entry.toolset == "davinciresolve"
    assert entry.check_fn is not None
    assert entry.check_fn() is (platform.system() == "Darwin")

    import tools as tools_after

    assert tools_after is duckwork_tools
    assert Path(tools_after.__file__).resolve() != (installed_plugin / "tools.py").resolve()
    assert sys.path == sys_path_before_load
