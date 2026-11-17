"""The corpus must follow Duckwork' *current* home, not the one at import.

Duckwork' get_duckwork_home() honours a context-local per-profile override, so a
long-lived process can serve profile A and later profile B. The retriever
must resolve skill/config paths at call time and never mistake a profile
switch for a test override of its legacy path constants.
"""

import contextvars
import importlib
import sys
import types
from pathlib import Path

import pytest

import bm25_retriever as br


def _write_skill(root: Path, rel: str, name: str, description: str) -> None:
    skill_dir = root / rel
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n'
    )


def _make_home(home: Path, tag: str) -> Path:
    _write_skill(home / "skills", f"only-{tag}", f"only-{tag}", f"widget{tag} tool")
    _write_skill(home / "skills", f"f1-{tag}", f"f1-{tag}", "filler one")
    _write_skill(home / "skills", f"f2-{tag}", f"f2-{tag}", "filler two things")
    return home


@pytest.fixture
def duckwork_home_override(monkeypatch, tmp_path):
    """Stub duckwork_constants with a context-local home override, as Duckwork
    has, and import bm25_retriever while profile A is active."""
    home_a = _make_home(tmp_path / "homeA", "A")
    home_b = _make_home(tmp_path / "homeB", "B")
    override = contextvars.ContextVar("duckwork_home", default=None)
    hc = types.ModuleType("duckwork_constants")
    hc.get_duckwork_home = lambda: Path(override.get() or home_a)
    hc.get_config_path = lambda: hc.get_duckwork_home() / "config.yaml"
    hc.get_skills_dir = lambda: hc.get_duckwork_home() / "skills"
    monkeypatch.setitem(sys.modules, "duckwork_constants", hc)
    # The standalone loader path needs "agent" to be UNIMPORTABLE, not just
    # absent: `from agent.prompt_builder import ...` resolves against
    # sys.modules['agent.prompt_builder'] directly, bypassing the None
    # sentinel on "agent". Neutralize the whole import family for this file.
    monkeypatch.setitem(sys.modules, "agent.prompt_builder", None)
    monkeypatch.setitem(sys.modules, "agent.skill_utils", None)
    importlib.reload(br)
    yield override, home_b
    monkeypatch.undo()
    importlib.reload(br)


def test_index_follows_home_switch_after_import(duckwork_home_override, monkeypatch):
    override, home_b = duckwork_home_override
    # No Duckwork skill-discovery helpers: exercises the standalone loader.
    monkeypatch.setitem(sys.modules, "agent", None)
    override.set(str(home_b))  # a later turn runs under profile B

    index = br.get_index()
    assert index is not None
    assert [r[0] for r in index.retrieve("widgetB")] == ["only-B"]
    assert index.retrieve("widgetA") == []


def test_home_switch_uses_duckwork_discovery(duckwork_home_override, monkeypatch):
    """A profile switch must not divert away from Duckwork' gated loader."""
    override, home_b = duckwork_home_override
    pb = types.ModuleType("agent.prompt_builder")
    pb._current_session_platform_hint = lambda: ""
    pb.extract_skill_conditions = lambda fm: {}
    shown = []
    pb._skill_should_show = lambda *a: shown.append(a) or True
    pb._parse_skill_file = lambda f: (True, {"name": br._parse_skill_md(f)[0]}, br._parse_skill_md(f)[1])
    pb._build_snapshot_entry = lambda f, root, fm, desc: {
        "category": "general", "skill_name": f.parent.name,
        "frontmatter_name": fm["name"], "description": desc,
    }
    su = types.ModuleType("agent.skill_utils")
    su.get_disabled_skill_names = lambda platform=None: set()
    su.get_project_skills_dirs = lambda: []
    su.get_all_skills_dirs = lambda: [sys.modules["duckwork_constants"].get_skills_dir()]
    su.iter_project_skill_files = lambda root: sorted(root.rglob("SKILL.md"))
    su.iter_skill_index_files = lambda root, filename: sorted(root.rglob(filename))
    monkeypatch.setitem(sys.modules, "agent", types.ModuleType("agent"))
    monkeypatch.setitem(sys.modules, "agent.prompt_builder", pb)
    monkeypatch.setitem(sys.modules, "agent.skill_utils", su)
    monkeypatch.setitem(sys.modules, "duckwork_cli.plugins", None)
    override.set(str(home_b))

    index = br.get_index()
    assert index is not None
    assert [r[0] for r in index.retrieve("widgetB")] == ["only-B"]
    assert shown, "Duckwork' _skill_should_show gate must run"
