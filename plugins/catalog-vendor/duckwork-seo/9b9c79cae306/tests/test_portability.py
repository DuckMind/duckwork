"""
Tests for v2 Checkpoint 7 (Phase G + I):
    scripts/portability_check.py — frontmatter portability lint
    AGENTS.md — multi-platform instructions (Codex/Cline/Aider added)
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import portability_check as pc  # noqa: E402

# ---------------------------------------------------------------------------
# portability_check
# ---------------------------------------------------------------------------


def test_whole_repo_passes_portability_lint() -> None:
    """Every SKILL.md in skills/ and extensions/ must pass with 0 errors.
    Warnings + info are acceptable; only errors fail the build."""
    paths = pc._find_skill_files()
    assert paths, "expected at least one SKILL.md in skills/"
    errors: list[dict] = []
    for path in paths:
        for finding in pc.check_one(path):
            if finding["severity"] == "error":
                errors.append(finding)
    assert errors == [], (
        f"{len(errors)} portability errors:\n  "
        + "\n  ".join(f"{e['path']}: {e['rule']}: {e['message']}" for e in errors)
    )


def test_check_one_flags_missing_frontmatter(tmp_path) -> None:
    bad = tmp_path / "SKILL.md"
    bad.write_text("# Skill without frontmatter\n\nBody.\n")
    findings = pc.check_one(bad)
    rules = [f["rule"] for f in findings]
    assert "no-frontmatter" in rules


def test_check_one_flags_missing_name(tmp_path) -> None:
    bad = tmp_path / "SKILL.md"
    bad.write_text("---\ndescription: example\n---\n\nbody")
    findings = pc.check_one(bad)
    rules = [f["rule"] for f in findings]
    assert "missing-name" in rules


def test_check_one_flags_camelcase_name(tmp_path) -> None:
    bad = tmp_path / "SKILL.md"
    bad.write_text("---\nname: badCamelCase\ndescription: example\n---\nbody")
    findings = pc.check_one(bad)
    rules = [f["rule"] for f in findings]
    assert "name-not-kebab-case" in rules


def test_check_one_flags_missing_description(tmp_path) -> None:
    bad = tmp_path / "SKILL.md"
    bad.write_text("---\nname: seo-x\n---\nbody")
    findings = pc.check_one(bad)
    rules = [f["rule"] for f in findings]
    assert "missing-description" in rules


def test_check_one_warns_on_inline_comment_in_tools(tmp_path) -> None:
    bad = tmp_path / "SKILL.md"
    bad.write_text(
        "---\nname: seo-x\ndescription: x\n"
        "tools: Read, Bash  # bash needed for analyse\n---\nbody"
    )
    findings = pc.check_one(bad)
    rules = [(f["severity"], f["rule"]) for f in findings]
    assert ("warning", "tools-has-inline-comment") in rules


def test_check_one_clean_skill_returns_no_findings(tmp_path) -> None:
    ok = tmp_path / "SKILL.md"
    ok.write_text(
        "---\nname: seo-clean\n"
        "description: A clean skill with no portability issues.\n"
        "metadata:\n  version: \"1.9.9\"\n"
        "---\n\nBody.\n"
    )
    findings = pc.check_one(ok)
    assert findings == []
