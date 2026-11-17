from __future__ import annotations

import importlib.util
import argparse
import subprocess
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("duckwork_seo_plugin", ROOT / "__init__.py")
assert SPEC and SPEC.loader
PLUGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLUGIN)


class Context:
    def __init__(self):
        self.skills = []
        self.hooks = []
        self.commands = []
        self.tools = []

    def register_skill(self, name, path, description=""):
        self.skills.append((name, Path(path), description))

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))

    def register_cli_command(self, **kwargs):
        self.commands.append(kwargs)

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


def test_registers_all_seo_skills_and_roles_and_duckwork_surfaces():
    ctx = Context()

    PLUGIN.register(ctx)

    assert len([s for s in ctx.skills if s[0].startswith("seo-") or s[0] == "seo"]) == 26
    assert len([s for s in ctx.skills if s[0].startswith("role-seo-")]) == 19
    assert [(name, callback.__name__) for name, callback in ctx.hooks] == [
        ("transform_tool_result", "validate_schema_result")
    ]
    assert [command["name"] for command in ctx.commands] == ["seo"]
    assert [tool["name"] for tool in ctx.tools] == ["duckwork_seo_run"]


def test_schema_hook_adds_actionable_feedback_for_invalid_jsonld(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        '<script type="application/ld+json">{"@context":"https://schema.org"}</script>',
        encoding="utf-8",
    )

    result = PLUGIN.validate_schema_result(
        tool_name="write_file", args={"path": str(path)}, result="Wrote file"
    )

    assert "Missing @type" in result
    assert result.startswith("Wrote file")
    assert '"@context":"https://schema.org"' in path.read_text(encoding="utf-8")


def test_schema_hook_leaves_unrelated_tools_and_valid_schema_unchanged(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage"}</script>',
        encoding="utf-8",
    )

    assert PLUGIN.validate_schema_result(
        tool_name="write_file", args={"path": str(path)}, result="Wrote file"
    ) is None
    assert PLUGIN.validate_schema_result(
        tool_name="terminal", args={}, result="ok"
    ) is None


def test_setup_cli_forwards_skip_browser_and_uses_plugin_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    calls = []
    monkeypatch.setattr(
        PLUGIN.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs))
        or subprocess.CompletedProcess(command, 0),
    )

    parser = argparse.ArgumentParser()
    PLUGIN._setup_cli(parser)
    args = parser.parse_args(["setup", "--skip-browser"])
    args.action = args.seo_action

    assert PLUGIN._run_runtime(args) == 0
    command, options = calls[0]
    assert command[-1] == "--skip-browser"
    assert options["env"]["DUCKWORK_SEO_DATA_DIR"] == str(data_dir)
    assert options["env"]["DUCKWORK_SEO_CONFIG_DIR"] == str(data_dir / "config")


def test_run_preserves_caller_directory_for_relative_input_and_output(tmp_path, monkeypatch):
    caller_dir = tmp_path / "caller"
    caller_dir.mkdir()
    (caller_dir / "comparison.json").write_text('{"status":"ok"}', encoding="utf-8")
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    real_run = subprocess.run

    def run_runtime(command, **options):
        # Run the real bundled utility while preserving the handler's cwd choice.
        script, *script_args = command[2:]
        proc = real_run(
            [sys.executable, str(ROOT / "scripts" / script), *script_args],
            cwd=options.get("cwd"),
            env=options["env"],
            check=False,
        )
        return proc

    monkeypatch.setattr(PLUGIN.subprocess, "run", run_runtime)
    parser = argparse.ArgumentParser()
    PLUGIN._setup_cli(parser)
    args = parser.parse_args(
        ["run", "drift_report.py", "comparison.json", "--output", "report.html"]
    )
    args.action = args.seo_action

    monkeypatch.chdir(caller_dir)
    assert PLUGIN._run_runtime(args) == 0
    report = (caller_dir / "report.html").read_text(encoding="utf-8")
    assert "Drift" in report or "drift" in report


def test_cli_runtime_drops_ambient_provider_credentials(tmp_path, monkeypatch):
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    monkeypatch.setenv("MOZ_API_KEY", "ambient-profile-key")
    monkeypatch.setenv("DUCKWORK_SEO_AUTHORIZED_SCRIPT", "moz_api.py")
    monkeypatch.setenv("DUCKWORK_SEO_AUTHORIZED_EXTENSION", "")
    calls = []
    monkeypatch.setattr(
        PLUGIN.subprocess,
        "run",
        lambda command, **kwargs: calls.append(kwargs)
        or subprocess.CompletedProcess(command, 0),
    )
    parser = argparse.ArgumentParser()
    PLUGIN._setup_cli(parser)
    args = parser.parse_args(["run", "backlinks_auth.py", "--check"])
    args.action = args.seo_action

    assert PLUGIN._run_runtime(args) == 0
    assert "MOZ_API_KEY" not in calls[0]["env"]
    assert "DUCKWORK_SEO_AUTHORIZED_SCRIPT" not in calls[0]["env"]
    assert "DUCKWORK_SEO_AUTHORIZED_EXTENSION" not in calls[0]["env"]
    assert "PATH" in calls[0]["env"]


def test_native_run_tool_reads_only_profile_scoped_secrets(tmp_path, monkeypatch):
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    scoped = {"MOZ_API_KEY": "profile-a-moz", "BING_WEBMASTER_API_KEY": "profile-a-bing"}
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: scoped.get(name, default)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    monkeypatch.setenv("MOZ_API_KEY", "launch-profile-key")
    script_path = tmp_path / "moz_api.py"
    script_path.write_text("pass\n", encoding="utf-8")
    runtime = types.SimpleNamespace(
        _status=lambda root, data_dir: {"ready": True, "python_path": sys.executable},
        _resolve_script=lambda root, script, extension: script_path,
        _safe_env=lambda status: {"PATH": __import__("os").environ["PATH"]},
    )
    monkeypatch.setattr(PLUGIN, "_load_runtime", lambda: runtime)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(PLUGIN.subprocess, "run", run)
    ctx = Context()
    PLUGIN.register(ctx)
    result = ctx.tools[0]["handler"]({"script": "moz_api.py", "args": ["metrics", "example.com"]})

    assert result == "0"
    env = calls[0][1]["env"]
    assert env["MOZ_API_KEY"] == "profile-a-moz"
    assert "BING_WEBMASTER_API_KEY" not in env
    assert "launch-profile-key" not in env.values()
    assert "MOZ_API_KEY" not in calls[0][0]


def test_native_run_tool_fails_closed_without_secret_scope(tmp_path, monkeypatch):
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    failure = RuntimeError("provider failure carried sensitive-secret-sample")
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: (_ for _ in ()).throw(failure)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    calls = []
    monkeypatch.setattr(PLUGIN.subprocess, "run", lambda *a, **k: calls.append(a))
    ctx = Context()
    PLUGIN.register(ctx)

    result = ctx.tools[0]["handler"]({"script": "moz_api.py", "args": ["metrics", "example.com"]})

    assert result == "Duckwork profile secrets unavailable; no utility was started."
    assert "sensitive-secret-sample" not in result
    assert calls == []


def test_native_run_tool_child_gets_profile_secret_in_real_process(tmp_path, monkeypatch):
    data_dir = tmp_path / "plugin-data"
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: data_dir
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: "profile-moz" if name == "MOZ_API_KEY" else default
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    monkeypatch.setenv("MOZ_API_KEY", "ambient-wrong-profile")
    script_path = tmp_path / "moz_api.py"
    script_path.write_text(
        "import os\nprint(os.getenv('MOZ_API_KEY'))\nprint(os.getenv('BING_WEBMASTER_API_KEY', 'absent'))\n",
        encoding="utf-8",
    )
    runtime = types.SimpleNamespace(
        _status=lambda root, data_dir: {"ready": True, "python_path": sys.executable},
        _resolve_script=lambda root, script, extension: script_path,
        _safe_env=lambda status: {"PATH": __import__("os").environ["PATH"]},
    )
    monkeypatch.setattr(PLUGIN, "_load_runtime", lambda: runtime)
    ctx = Context()
    PLUGIN.register(ctx)
    result = ctx.tools[0]["handler"]({"script": "moz_api.py", "args": ["metrics"]})
    assert result == "<redacted>\nabsent"
    assert "ambient-wrong-profile" not in result


def test_native_run_tool_rejects_secret_in_arguments(monkeypatch):
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: None
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    calls = []
    monkeypatch.setattr(PLUGIN.subprocess, "run", lambda *a, **k: calls.append(a))
    ctx = Context()
    PLUGIN.register(ctx)

    result = ctx.tools[0]["handler"]({"script": "moz_api.py", "args": ["--api-key", "literal-secret"]})

    assert "never as tool arguments" in result
    assert calls == []


def test_native_run_tool_rejects_offline_script_on_host(monkeypatch):
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: None
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    calls = []
    monkeypatch.setattr(PLUGIN.subprocess, "run", lambda *a, **k: calls.append(a))
    ctx = Context()
    PLUGIN.register(ctx)

    result = ctx.tools[0]["handler"]({"script": "drift_report.py", "args": ["report.json"]})

    assert "only declared credentialed providers" in result
    assert calls == []


def test_native_matomo_process_gets_profile_config_and_token_only(tmp_path, monkeypatch):
    import os

    values = {
        "MATOMO_TOKEN": "profile-token-value",
        "MATOMO_URL": "https://profile.example.invalid",
        "MATOMO_IDSITE": "7",
        "MATOMO_API_TOKEN": None,
        "MATOMO_SITE_ID": None,
        "DUCKWORK_SEO_LOCAL_TARGETS": "profile.internal:8080",
    }
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: values.get(name, default)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    for name in values:
        monkeypatch.setenv(name, "wrong-profile")
    child = tmp_path / "matomo_report.py"
    child.write_text(
        "import os\n"
        "print(os.getenv('MATOMO_URL'))\n"
        "print(os.getenv('MATOMO_IDSITE'))\n"
        "print(os.getenv('DUCKWORK_SEO_LOCAL_TARGETS'))\n"
        "print(os.getenv('MATOMO_TOKEN') == 'profile-token-value')\n",
        encoding="utf-8",
    )
    runtime = types.SimpleNamespace(
        _status=lambda root, data_dir: {"ready": True, "python_path": sys.executable},
        _resolve_script=lambda root, script, extension: child,
        _safe_env=lambda status: {"PATH": os.environ["PATH"]},
    )
    monkeypatch.setattr(PLUGIN, "_load_runtime", lambda: runtime)
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: tmp_path / "plugin-data"
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    ctx = Context()
    PLUGIN.register(ctx)

    result = ctx.tools[0]["handler"]({"script": "matomo_report.py", "args": ["check"]})

    assert result == "https://profile.example.invalid\n7\nprofile.internal:8080\nTrue"
    assert "wrong-profile" not in result


def test_native_matomo_fails_cleanly_without_profile_url(tmp_path, monkeypatch):
    import os

    values = {"MATOMO_API_TOKEN": "profile-token", "MATOMO_SITE_ID": "7"}
    secrets = types.ModuleType("agent.secret_scope")
    secrets.get_secret = lambda name, default=None: values.get(name, default)
    monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    monkeypatch.setenv("MATOMO_URL", "https://wrong-profile.invalid")
    runtime = types.SimpleNamespace(
        _status=lambda root, data_dir: {"ready": True, "python_path": sys.executable},
        _resolve_script=lambda root, script, extension: ROOT / "scripts" / script,
        _safe_env=lambda status: {"PATH": os.environ["PATH"]},
    )
    monkeypatch.setattr(PLUGIN, "_load_runtime", lambda: runtime)
    storage = types.ModuleType("plugins.plugin_storage")
    storage.plugin_data_dir = lambda name: tmp_path / "plugin-data"
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    ctx = Context()
    PLUGIN.register(ctx)

    result = ctx.tools[0]["handler"]({"script": "matomo_report.py", "args": ["check"]})

    assert "Matomo profile settings incomplete" in result
    assert "MATOMO_URL" in result
    assert "wrong-profile" not in result
