"""DataForSEO role skill must fail closed when its MCP tools are unavailable."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_SKILL = ROOT / "skills" / "role-seo-dataforseo" / "SKILL.md"


def test_dataforseo_role_fails_closed_without_mcp() -> None:
    text = ROLE_SKILL.read_text(encoding="utf-8")
    assert "fail closed" in text
    assert "Never inspect credential or" in text
    assert "never bypass MCP with curl, raw HTTP, or another client" in text
