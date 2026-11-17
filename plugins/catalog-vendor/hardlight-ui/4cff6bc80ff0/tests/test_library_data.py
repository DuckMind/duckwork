"""Shipped content contracts, not automated judgments of artistic merit."""
import ast
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import pytest
from packaging.requirements import Requirement

from hardlight import __version__

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    "swiss-editorial", "bauhaus-play", "editorial-luxe", "neo-brutalist",
    "organic-humanist", "kinetic-poster", "cinematic-gallery", "quiet-craft",
    "deco-geometric", "retro-future", "systemic-product", "data-atelier",
    "wayfinding", "illustrated-world", "spatial-technical", "expressive-material",
}
TOPICS = {"workflow", "navigation", "states", "typography", "color", "motion", "review", "systems", "browser", "layout", "platform", "performance"}
STYLE_FIELDS = {
    "id", "name", "family", "surfaces", "thesis", "composition", "typography",
    "palette", "material", "motion", "interaction", "mobile", "use_when",
    "avoid_when", "signature", "source_ids",
}


def atlas():
    path = ROOT / "data/atlas.json"
    assert path.is_file(), "The shipped artistic atlas is missing"
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_metadata_agrees_across_distribution_surfaces():
    manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    skill = (ROOT / "skills/frontend-design/SKILL.md").read_text(encoding="utf-8")
    assert re.findall(r'^version: ([0-9.]+)$', manifest, re.M) == [__version__]
    assert re.findall(r'^version = "([0-9.]+)"$', project, re.M) == [__version__]
    assert re.findall(r'^version: ([0-9.]+)$', skill, re.M) == [__version__]
    assert 'requires_duckwork: ">=0.21.0"' in manifest


def test_optional_browser_dependency_resolves_only_on_supported_platforms():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = ast.literal_eval(re.search(r'^browser = (.+)$', project, re.M)[1])
    playwright, = [Requirement(item) for item in requirements]
    assert playwright.name == "playwright"
    assert playwright.marker is not None
    for platform in ("linux", "darwin", "win32", "android", "ios", "emscripten"):
        assert playwright.marker.evaluate({"sys_platform": platform}) is (platform in {"linux", "darwin", "win32"})


def test_canonical_atlas_has_exact_schema_and_resolving_sources():
    data = atlas()
    assert set(data) == {"schema_version", "styles", "sources"}
    assert type(data["schema_version"]) is int and data["schema_version"] == 1
    assert isinstance(data["styles"], list)
    assert {s["id"] for s in data["styles"]} == CANONICAL
    assert len(data["styles"]) == len(CANONICAL)
    assert isinstance(data["sources"], list) and data["sources"]
    sources = {s["id"]: s for s in data["sources"]}
    assert len(sources) == len(data["sources"]), "Duplicate source IDs"
    for source in sources.values():
        assert set(source) == {"id", "title", "url", "kind"}
        assert all(isinstance(v, str) and v.strip() == v and v for v in source.values())
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source["id"])
        url = urlparse(source["url"])
        assert url.scheme == "https" and url.netloc and not url.username and not url.password
        assert source["kind"] in {"standard", "design-system", "art-reference", "product", "curation"}
    for style in data["styles"]:
        assert set(style) == STYLE_FIELDS
        for key in STYLE_FIELDS - {"composition", "palette", "surfaces", "source_ids"}:
            assert isinstance(style[key], str) and style[key].strip(), (style["id"], key)
        assert isinstance(style["composition"], list) and len(style["composition"]) >= 3
        assert all(isinstance(v, str) and v.strip() for v in style["composition"])
        assert isinstance(style["surfaces"], list) and style["surfaces"]
        assert len(set(style["surfaces"])) == len(style["surfaces"])
        assert set(style["surfaces"]) <= {"marketing", "product", "reading", "commerce", "portfolio"}
        assert set(style["palette"]) == {"canvas", "text", "accent"}
        assert all(isinstance(c, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in style["palette"].values())
        assert isinstance(style["source_ids"], list) and style["source_ids"]
        assert len(set(style["source_ids"])) == len(style["source_ids"])
        assert set(style["source_ids"]) <= sources.keys()
    used = {sid for style in data["styles"] for sid in style["source_ids"]}
    assert used == sources.keys(), "Orphaned sources obscure the evidence map"
    assert {s["kind"] for s in data["sources"]} == {"standard", "design-system", "art-reference", "product", "curation"}


@pytest.mark.parametrize("topic", sorted(TOPICS))
def test_task_reference_exists_and_local_markdown_links_resolve(topic):
    path = ROOT / "references" / f"{topic}.md"
    assert path.is_file(), f"Missing shipped reference: {topic}"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# ") and "## " in text
    assert len(text.split()) >= 180, "A topic must contain actionable guidance, not just a pointer"
    assert not re.search(r"\b(?:TODO|TBD|FIXME)\b", text)
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if urlparse(target).scheme or target.startswith("#"):
            continue
        local = target.split("#", 1)[0]
        assert (path.parent / local).resolve().is_file(), (topic, target)


def test_skill_frontmatter_and_reference_calls_are_portable():
    path = ROOT / "skills/frontend-design/SKILL.md"
    assert path.is_file(), "The bundled frontend design skill is missing"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front, body = text[4:].split("\n---\n", 1)
    fields = dict(re.findall(r"^(name|description|version|author|license): (.+)$", front, re.M))
    assert set(fields) == {"name", "description", "version", "author", "license"}
    assert fields["name"] == "frontend-design"
    description = fields["description"].strip('"')
    assert len(description) <= 60 and description.endswith(".")
    assert description.startswith("Use when ")
    assert fields["author"] == "Seth Wilson and Duckwork Agent"
    assert fields["license"] == "MIT"
    assert "platforms: [linux, macos, windows]" in front
    assert not re.search(r"/(?:home|Users|workspace)/", text)
    assert not re.search(r"\b(?:TODO|TBD|FIXME)\b", text)
    topics = set(re.findall(r'hardlight_reference\(topic="([a-z]+)"', body))
    assert TOPICS <= topics
    assert topics <= TOPICS | {"index", "atlas", "style"}
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
        if not urlparse(target).scheme and not target.startswith("#"):
            assert (path.parent / target.split("#", 1)[0]).resolve().is_file(), target


def test_skill_authoring_sections_examples_and_metadata():
    text = (ROOT / "skills/frontend-design/SKILL.md").read_text(encoding="utf-8")
    front, body = text[4:].split("\n---\n", 1)
    assert re.search(r'^metadata:\n  author: Seth Wilson and Duckwork Agent <[^<> ]+@[^<> ]+>$', front, re.M)
    assert re.search(r'^  tags: \[frontend, design, navigation, typography, accessibility\]$', front, re.M)
    sections = set(re.findall(r'^## (.+)$', body, re.M))
    assert {"Purpose", "When to Use", "Prerequisites", "Instructions", "Examples",
            "Limitations", "Troubleshooting", "Verification"} <= sections
    assert re.findall(r'^### ([1-7])\. ', body, re.M) == list("1234567")
    examples = body.split("## Examples\n", 1)[1].split("\n## ", 1)[0]
    assert 'hardlight_reference(topic="navigation")' in examples
    assert 'hardlight_contrast(' in examples
    assert "Expected:" in examples
    recovery = body.split("## Troubleshooting\n", 1)[1].split("\n## ", 1)[0]
    assert "Playwright" in recovery and "install" in recovery
    assert "direct URL" in recovery and "retest" in recovery


def test_evidence_map_accounts_for_every_atlas_source_without_private_paths():
    path = ROOT / "docs/research.md"
    assert path.is_file(), "The source evidence map is missing"
    text = path.read_text(encoding="utf-8")
    for source in atlas()["sources"]:
        assert f'`{source["id"]}`' in text, source["id"]
        assert source["url"] in text, source["url"]
    assert not re.search(r"/(?:home|Users|workspace)/", text)
