"""Duckwork package metadata stays aligned with its host manifest."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_plugin_manifest() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.M)
    plugin_version = re.search(r"^version:\s*['\"]?([0-9.]+)['\"]?\s*$", manifest, re.M)
    assert project_version and plugin_version
    assert project_version.group(1) == plugin_version.group(1)


def test_reference_files_are_linked_from_instructions_or_docs() -> None:
    refs = list((ROOT / "skills").glob("**/references/*.md"))
    sources = [*ROOT.glob("skills/**/SKILL.md"), *ROOT.glob("docs/*.md")]
    sources.extend(path for path in (ROOT / "skills").glob("**/references/*.md"))
    content = {path: path.read_text(encoding="utf-8") for path in sources}
    orphans = []
    for ref in refs:
        if not any(
            other != ref and (ref.name in text or f"[[{ref.stem}]]" in text)
            for other, text in content.items()
        ):
            orphans.append(str(ref.relative_to(ROOT)))
    assert not orphans, "unlinked reference files: " + ", ".join(orphans)
