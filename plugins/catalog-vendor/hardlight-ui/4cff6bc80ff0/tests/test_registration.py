"""Native registration contracts plus opt-in real Duckwork subprocess integration."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from hardlight import __version__

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {"hardlight_reference", "hardlight_direction", "hardlight_inspect", "hardlight_contrast", "hardlight_navigation"}


def load_plugin():
    spec = importlib.util.spec_from_file_location("hardlight_contract_plugin", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Context:
    def __init__(self):
        self.tools, self.skills, self.commands, self.sections = {}, {}, {}, {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = (schema, handler)

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = path

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler

    def register_system_prompt_section(self, id, content, **kwargs):
        assert isinstance(content, str) and len(content) <= kwargs["max_chars"]
        self.sections[id] = content


def test_native_adapter_shape_and_commands(tmp_path):
    plugin = load_plugin()
    ctx = Context()
    plugin.register(ctx)
    assert set(ctx.tools) == TOOLS
    assert ctx.skills["frontend-design"].is_file()
    assert __version__ in ctx.commands["hardlight"]("version")
    assert "styles" in ctx.commands["hardlight"]("help")
    assert "swiss-editorial" in ctx.commands["hardlight"]("styles")
    assert "help" in ctx.commands["hardlight"]("not-a-command")
    for name, (schema, handler) in ctx.tools.items():
        assert schema["name"] == name and "function" not in schema
        assert schema["parameters"]["type"] == "object"
        assert json.loads(handler({}, task_id="x", session_id="y"))["ok"] is (name == "hardlight_reference")
        assert json.loads(handler([], task_id="x"))["ok"] is False
    contrast = ctx.tools["hardlight_contrast"][1]
    assert json.loads(contrast({"pairs": [{"foreground": "#000", "background": "#fff", "role": "text"}]}))["pairs"][0]["ratio"] == 21
    schema, direction = ctx.tools["hardlight_direction"]
    assert schema["parameters"]["properties"]["context"]["additionalProperties"] is False
    result = json.loads(direction({"brief": "Print room", "context": {"tasks": ["Review a proof"]}}, task_id="test", session_id="test"))
    assert result["context"]["tasks"] == ["Review a proof"]
    assert result["design_contract"]["status"] == "awaiting_host_authorship"
    assert json.loads(direction({"brief": "Print room", "context": {"tasks": []}}))["ok"] is False
    # Optional prompt API can be absent; required APIs fail before any registration.
    ctx = Context()
    ctx.register_system_prompt_section = None
    plugin.register(ctx)
    assert len(ctx.tools) == 5
    for missing in ("register_tool", "register_skill", "register_command"):
        ctx = Context()
        setattr(ctx, missing, None)
        with pytest.raises(RuntimeError, match=missing):
            plugin.register(ctx)
        assert not ctx.tools


_NATIVE = r'''
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
from duckwork_cli.plugins import PluginManager
from duckwork_cli.plugins_manifest import parse_manifest_file
from duckwork_cli.plugins_discovery import suppress_plugin_discovery
from tools.registry import registry
manager = PluginManager(scope_key=os.environ["DUCKWORK_HOME"])
names = ["hardlight_reference", "hardlight_direction", "hardlight_inspect", "hardlight_contrast", "hardlight_navigation"]
with suppress_plugin_discovery():
    manifest = parse_manifest_file(root / "plugin.yaml", root, source="user", prefix="")
    assert manifest is not None
    assert set(manifest.provides_tools) == set(names)
    assert not manifest.provides_hooks
    try:
        manager._load_plugin(manifest)
        loaded = manager._plugins["hardlight-ui"]
        assert loaded.enabled and loaded.error is None, loaded.error
        args = [
            {"topic": "style", "style": "swiss-editorial"},
            {"brief": "Field collection workspace", "authority": "extension"},
            {"root": str(root / "examples"), "max_files": 4},
            {"pairs": [{"foreground": "#000", "background": "#fff", "role": "text"}]},
            {"pages": [{"id": "home", "label": "Home", "links": []}], "tasks": []},
        ]
        results = []
        for name, payload in zip(names, args):
            raw = registry.dispatch(name, payload, scope=manager.scope_key, task_id="contract-test", session_id="contract-session")
            assert isinstance(raw, str), (name, raw)
            result = json.loads(raw)
            assert result["ok"] is True, (name, result)
            results.append({"tool": name, "ok": True})
        invalid = json.loads(registry.dispatch("hardlight_contrast", {"pairs": []}, scope=manager.scope_key, task_id="contract-test", session_id="contract-session"))
        assert invalid["ok"] is False
        platform = json.loads(registry.dispatch("hardlight_reference", {"topic": "platform"}, scope=manager.scope_key, task_id="contract-test"))
        assert platform["ok"] and platform["features"] and platform["schema_version"] == 1
        contextual = json.loads(registry.dispatch("hardlight_direction", {"brief": "Print room", "authority": "extension", "context": {"tasks": ["Review a proof"], "identity": "Keep the incumbent workbench"}}, scope=manager.scope_key, task_id="contract-test", session_id="contract-session"))
        assert contextual["ok"] and contextual["preserve_incumbent"]
        assert contextual["context"]["tasks"] == ["Review a proof"]
        assert contextual["design_contract"]["status"] == "awaiting_host_authorship"
        invalid_context = json.loads(registry.dispatch("hardlight_direction", {"brief": "Print room", "context": {"tasks": []}}, scope=manager.scope_key))
        assert invalid_context["ok"] is False
        assert manager.find_plugin_skill("hardlight-ui:frontend-design").is_file()
        command = manager._plugin_commands["hardlight"]["handler"]
        assert manifest.version in command("version")
        assert "swiss-editorial" in command("styles")
        sections = manager.render_system_prompt_sections({"session_id": "contract-session", "model": "test", "provider": "test", "platform": "cli", "profile_name": "isolated", "cwd": str(root)})
        assert len(sections) == 1
        print(json.dumps({"native_results": results, "prompt_sections": len(sections)}))
    finally:
        manager.unload()
    for name in names:
        assert registry.get_entry(name, scope=manager.scope_key) is None
    assert manager.find_plugin_skill("hardlight-ui:frontend-design") is None
    assert "hardlight" not in manager._plugin_commands
    assert not manager._system_prompt_sections
print("native unload clean")
'''


@pytest.mark.native
def test_real_duckwork_load_dispatch_and_unload(tmp_path):
    source = os.environ.get("DUCKWORK_SOURCE")
    if not source:
        pytest.skip("Opt in to real native integration with DUCKWORK_SOURCE pointing at an installed Duckwork checkout; this is not native proof")
    source = Path(source).resolve()
    assert (source / "duckwork_cli" / "plugins.py").is_file(), "DUCKWORK_SOURCE must be a real Duckwork source checkout"
    home = tmp_path / "home"
    duckwork_home = home / ".duckwork"
    duckwork_home.mkdir(parents=True)
    env = dict(os.environ, HOME=str(home), DUCKWORK_HOME=str(duckwork_home), PYTHONPATH=os.pathsep.join((str(source), str(ROOT))))
    # HOME is replaced before any host import, not just around the manager.
    process = subprocess.run([sys.executable, "-c", textwrap.dedent(_NATIVE), str(ROOT)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stdout + "\n" + process.stderr
    assert "native unload clean" in process.stdout
    print(process.stdout.strip())
