"""Monid plugin — bundles the official Monid skill.

Monid (https://monid.ai) connects your agent to third-party tools and APIs
(web search and scraping, people and company data, social media, media
generation, email and phone) through one integration. The agent discovers,
compares and runs tools at runtime, paid per call from one Monid balance.
Discovery and inspection are free; every run spends the user's balance, and
the skill requires the user's confirmation of the price before each run.

The skill registers as ``monid:monid`` and is loaded explicitly with
``skill_view("monid:monid")``. It drives either the ``monid`` CLI (works
with the built-in terminal tool, no Duckwork configuration needed) or the
hosted Monid MCP server (``mcp_servers.monid`` with ``auth: oauth``).
"""

from pathlib import Path

_SKILL_MD = Path(__file__).parent / "skills" / "monid" / "SKILL.md"


def register(ctx):
    ctx.register_skill(
        "monid",
        _SKILL_MD,
        description=(
            "Monid connects the agent to third-party tools and APIs "
            "(search, scraping, people/company data, social media, media "
            "generation) paid per call from the user's Monid balance. "
            "Load only when the user explicitly asks to use Monid."
        ),
    )
