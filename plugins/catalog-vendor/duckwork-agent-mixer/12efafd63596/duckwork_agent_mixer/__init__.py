"""Agent Mixer - a mixing desk for how much a coding agent may change.

Duckwork plugin (``/mixer`` plus ``pre_tool_call`` / ``pre_llm_call`` hooks) and a harness-agnostic
``agent-mixer`` CLI for Claude Code, Codex and Gemini CLI. Standard library only.

``register`` imports the Duckwork adapter lazily, so the CLI never pays for it.
"""

__all__ = ["register"]
__version__ = "0.2.0"


def register(ctx):
    """Duckwork plugin entry point (``duckwork_agent.plugins`` group)."""
    from .duckwork.plugin import register as _register

    _register(ctx)
