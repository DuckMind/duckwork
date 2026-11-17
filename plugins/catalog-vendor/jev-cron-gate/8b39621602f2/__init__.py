"""jev-cron-gate — skip Duckwork agent cron runs that Jev says would do nothing useful.

Registers one tool, ``jev_cron_gate`` (setup / status / test / remove), and a skill
explaining how to attach a gate to a job. The gate itself (gate.py) is a stdlib-only
pre-run script that plugs into Duckwork cron's built-in wake gate
(last stdout line ``{"wakeAgent": false}`` skips the LLM run). Fail-open everywhere.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import tools
from .schemas import JEV_CRON_GATE

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    ctx.register_tool(name="jev_cron_gate", schema=JEV_CRON_GATE,
                      handler=lambda args, **kw: tools.handle(args, **kw), toolset="jev-cron-gate")
    try:
        skill = Path(__file__).parent / "skills" / "jev-cron-gate" / "SKILL.md"
        ctx.register_skill("jev-cron-gate", skill)
    except Exception as e:  # never break plugin load over the doc skill
        logger.debug("jev-cron-gate: skill registration skipped: %s", e)
