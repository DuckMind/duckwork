"""e-Stat plugin for Duckwork Agent: official Japanese government statistics.

Three read-only tools that take an agent from a question to a cited number:
search tables, inspect a table's dimensions, and fetch values by name.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILL = Path(__file__).resolve().parent / "skills" / "estat-figures" / "SKILL.md"
_SKILL_DESCRIPTION = (
    "Japan statistics (e-Stat) for a census, population, households, prices, a consumer price index, wages, and prefectures. "
    "Before web_search, use tool_search to find the e-Stat tools and tool_call to run them. "
    "Report only numbers the tool returned."
)

# Duckwork imports this directory as a package. pytest's collector also imports this
# file on its own (the repo root is the package), where relative imports cannot work.
if __package__:
    from . import client, schemas, tools


def register(ctx):
    """Register every tool under the `estat` toolset, then the figures skill."""
    for schema in schemas.ALL_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="estat",
            schema=schema,
            handler=tools.HANDLERS[schema["name"]],
            requires_env=[client.APP_ID_ENV],
            emoji="📊",
        )
    try:
        ctx.register_skill(
            "japan-statistics",
            _SKILL,
            description=_SKILL_DESCRIPTION,
        )
    except Exception:
        logger.warning("jp-estat skill was not registered", exc_info=True)
