"""Static instruction guards for full audit persistence and SPA wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_seo_audit_starts_with_render_page_auto() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    process = text[text.index("## Process"):text.index("## Crawl Configuration")]
    assert 'duckwork seo run render_page.py' in process
    assert "python3 scripts/render_page.py" not in process
    assert "--mode auto" in process
    assert "scripts/fetch_page.py` to retrieve HTML" not in process


def test_seo_audit_requires_persistent_artifacts() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    for artifact in (
        "FULL-AUDIT-REPORT.md",
        "ACTION-PLAN.md",
        "audit-data.json",
        "findings/",
        "screenshots/",
    ):
        assert artifact in text
    assert "{domain}-audit" in text


def test_audit_roles_use_renderer_or_capture_script() -> None:
    expectations = {
        "role-seo-performance": "render_page.py",
        "role-seo-visual": "capture_screenshot.py",
        "role-seo-technical": "render_page.py",
        "role-seo-content": "render_page.py",
        "role-seo-schema": "render_page.py",
    }
    for role, marker in expectations.items():
        text = (REPO_ROOT / "skills" / role / "SKILL.md").read_text(encoding="utf-8")
        assert marker in text, f"{role} must mention {marker}"


def test_audit_roles_document_output_dir_findings_contract() -> None:
    for role in (
        "role-seo-performance", "role-seo-visual", "role-seo-technical",
        "role-seo-content", "role-seo-schema", "role-seo-sitemap",
        "role-seo-geo", "role-seo-local", "role-seo-maps", "role-seo-google",
        "role-seo-backlinks", "role-seo-cluster", "role-seo-sxo",
        "role-seo-drift", "role-seo-ecommerce", "role-seo-agentic",
    ):
        text = (REPO_ROOT / "skills" / role / "SKILL.md").read_text(encoding="utf-8")
        assert "output_dir" in text
        assert "findings/" in text


def test_seo_audit_report_command_keeps_outputs_in_audit_dir() -> None:
    text = (REPO_ROOT / "skills" / "seo-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "--output-dir {domain}-audit/" in text
