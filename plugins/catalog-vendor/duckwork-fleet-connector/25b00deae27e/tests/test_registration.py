"""register() under in_process and host isolation with a fake ctx and fake Duckwork modules."""
import sys
import types
from pathlib import Path
import pytest

class Ctx:
    def __init__(self):
        self.commands, self.cli, self.dashboard, self.platform = [], [], [], []
    def register_command(self, name, handler, **kw): self.commands.append((name, handler, kw))
    def register_cli_command(self, name, **kw): self.cli.append((name, kw))
    def register_dashboard_auth_provider(self, p): self.dashboard.append(p)
    def register_platform_handler(self, platform, factory): self.platform.append(platform)

@pytest.fixture
def duckwork(monkeypatch, tmp_path):
    state = {"mode": "in_process"}
    const = types.ModuleType("duckwork_constants")
    const.get_duckwork_home = lambda: tmp_path
    iso = types.ModuleType("duckwork_cli.plugin_isolation")
    iso.isolation_mode = lambda: state["mode"]
    monkeypatch.setitem(sys.modules, "duckwork_constants", const)
    monkeypatch.setitem(sys.modules, "duckwork_cli", types.ModuleType("duckwork_cli"))
    monkeypatch.setitem(sys.modules, "duckwork_cli.plugin_isolation", iso)
    base = types.ModuleType("duckwork_cli.dashboard_auth.base")
    for name in ("DashboardAuthProvider", "Session", "LoginStart"):
        setattr(base, name, type(name, (), {}))
    for name in ("InvalidCodeError", "RefreshExpiredError"):
        setattr(base, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, "duckwork_cli.dashboard_auth", types.ModuleType("duckwork_cli.dashboard_auth"))
    monkeypatch.setitem(sys.modules, "duckwork_cli.dashboard_auth.base", base)
    return state

def test_in_process_registers_everything(duckwork, tmp_path):
    from fleet_connector.bridge import register
    ctx = Ctx()
    register(ctx)
    assert [c[0] for c in ctx.commands] == ["fleet"]
    assert [c[0] for c in ctx.cli] == ["fleet"]
    assert ctx.cli[0][1]["setup_fn"] and ctx.cli[0][1]["handler_fn"] and ctx.cli[0][1]["help"]
    assert len(ctx.dashboard) == 1 and ctx.platform == ["telegram"]

def test_host_isolation_keeps_universal_flow_only(duckwork, caplog):
    from fleet_connector.bridge import register
    duckwork["mode"] = "host"
    ctx = Ctx()
    register(ctx)
    assert [c[0] for c in ctx.commands] == ["fleet"] and [c[0] for c in ctx.cli] == ["fleet"]
    assert ctx.platform == [] and ctx.dashboard == []
    assert "isolation" in caplog.text

def test_host_context_does_not_require_native_registration_apis(duckwork):
    from fleet_connector.bridge import register
    duckwork["mode"] = "host"
    ctx = Ctx()
    ctx.register_dashboard_auth_provider = None
    ctx.register_platform_handler = None
    register(ctx)
    assert [c[0] for c in ctx.commands] == ["fleet"]
    assert [c[0] for c in ctx.cli] == ["fleet"]
    assert ctx.platform == [] and ctx.dashboard == []

@pytest.mark.parametrize("missing", ["register_command", "register_cli_command",
                                    "register_dashboard_auth_provider", "register_platform_handler"])
def test_missing_required_api_refuses_before_partial_registration(duckwork, missing):
    from fleet_connector.bridge import register
    ctx = Ctx()
    setattr(ctx, missing, None)
    with pytest.raises(RuntimeError, match=missing):
        register(ctx)
    assert ctx.commands == [] and ctx.cli == [] and ctx.platform == [] and ctx.dashboard == []

def test_top_level_register_delegates(duckwork):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hfc_plugin", Path(__file__).parents[1] / "__init__.py",
        submodule_search_locations=[str(Path(__file__).parents[1])])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hfc_plugin"] = mod
    try:
        spec.loader.exec_module(mod)
        ctx = Ctx()
        mod.register(ctx)
    finally:
        sys.modules.pop("hfc_plugin", None)
    assert [c[0] for c in ctx.commands] == ["fleet"]
