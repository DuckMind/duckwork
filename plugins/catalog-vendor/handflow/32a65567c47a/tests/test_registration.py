"""The catalog contract: what plugin.yaml promises is what register() wires.

The capability probe imports this package in a bare interpreter and diffs the
declared capabilities against what ``register()`` actually does. These tests run
the same diff locally so a drift can't reach the catalog PR.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from helpers import RecordingContext, plugin_yaml

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SPECIFIERS = {"@duckwork/plugin-sdk", "react", "react/jsx-runtime"}


def _register() -> RecordingContext:
    """Import the plugin root the way the capability probe does, then register."""
    import importlib.util
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "handflow_plugin_root", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["handflow_plugin_root"] = mod
    spec.loader.exec_module(mod)
    ctx = RecordingContext()
    mod.register(ctx)
    return ctx


def test_declared_tools_match_what_register_registers():
    declared = sorted(plugin_yaml().get("provides_tools") or [])
    assert declared == ["handflow"], "plugin.yaml must declare exactly the tool we ship"
    assert sorted(_register().tools) == declared


def test_declared_hooks_and_middleware_match_reality():
    ctx = _register()
    manifest = plugin_yaml()
    assert sorted(ctx.hooks) == sorted(manifest.get("provides_hooks") or [])
    assert sorted(ctx.middleware) == sorted(manifest.get("provides_middleware") or [])


def test_register_is_side_effect_free(tmp_path, monkeypatch):
    """register() must not touch disk: the probe runs it with nothing on disk."""
    home = tmp_path / "untouched"
    monkeypatch.setenv("HANDFLOW_HOME", str(home))
    _register()
    assert not home.exists(), "register() created state — the capability probe would see side effects"


def test_manifest_and_package_agree_on_the_name():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == plugin_yaml()["name"] == "handflow"
    assert (ROOT / "dashboard" / manifest["api"]).is_file()


def test_desktop_half_stays_inside_the_sdk_surface():
    """Mirror of `duckwork plugins validate`'s desktop surface check."""
    src = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/|(?<![:\\w])//[^\n]*", "", src, flags=re.S)
    for specifier in re.findall(r"^\s*import\s+[^'\"]*from\s*['\"]([^'\"]+)['\"]", stripped, re.M):
        assert specifier in ALLOWED_SPECIFIERS, f"desktop half imports {specifier!r}"
    for specifier in re.findall(r"import\(\s*['\"]([^'\"]+)['\"]", stripped):
        assert specifier in ALLOWED_SPECIFIERS, f"dynamic import of {specifier!r}"
    for banned in (r"(?<![\w$.])eval\(", r"\bnew\s+Function\(", r"\.prototype\.[\w$]+\s*=[^=]", r"<script\b"):
        assert not re.search(banned, stripped), f"desktop half uses a banned construct: {banned}"
    assert "jsx(" in stripped, "a disk plugin must call jsx()/jsxs(), never JSX syntax"


def test_no_update_mechanism_in_the_shipped_code():
    """Catalog rule 3: nothing that fetches from GitHub and rewrites plugin files."""
    for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.js")):
        if any(part.startswith(".") or part == "tests" for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for banned in ("urlretrieve", "check_for_update", "self_update", "urllib.request", "requests.get("):
            assert banned not in text, f"{path.name} looks like a self-updater ({banned})"
