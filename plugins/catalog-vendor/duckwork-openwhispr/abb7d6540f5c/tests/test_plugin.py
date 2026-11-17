"""Tests for duckwork-openwhispr. Stdlib + pytest only, no live network."""

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "openwhispr" / "SKILL.md"


class _RecordingCtx:
    """Minimal stand-in for the plugin context: records skill registrations."""

    def __init__(self):
        self.skills = []

    def register_skill(self, name, path):
        self.skills.append((name, str(path)))


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        "duckwork_openwhispr", ROOT / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_register_registers_the_skill():
    ctx = _RecordingCtx()
    _load_plugin().register(ctx)
    assert ctx.skills, "register() must call ctx.register_skill()"
    name, path = ctx.skills[0]
    assert name == "openwhispr"
    assert path.endswith("skills/openwhispr/SKILL.md")
    assert pathlib.Path(path).is_file()


def test_manifest_exists_and_declares_no_capabilities():
    text = (ROOT / "plugin.yaml").read_text()
    assert "name: duckwork-openwhispr" in text
    assert "tools: []" in text
    assert "hooks: []" in text


def test_skill_frontmatter_hardline():
    text = SKILL.read_text()
    assert text.startswith("---")
    m = re.search(r"^description: (.*)$", text, re.MULTILINE)
    assert m, "description frontmatter missing"
    desc = m.group(1).strip()
    assert len(desc) <= 60, f"description {len(desc)} chars"
    assert desc.endswith(".")


def test_no_core_overrides_or_self_updater():
    blob = (ROOT / "__init__.py").read_text()
    for banned in ("sys.modules", "setattr(server", "AIAgent.", "check for updates"):
        assert banned not in blob


def test_readme_discloses_credential_read():
    readme = (ROOT / "README.md").read_text().lower()
    assert "cli-config.json" in readme
    assert "cli-bridge.json" in readme
    assert "never opens credential files" in readme
    assert "0600" in readme


def test_license_present():
    assert (ROOT / "LICENSE").is_file()
    assert "MIT" in (ROOT / "LICENSE").read_text()
