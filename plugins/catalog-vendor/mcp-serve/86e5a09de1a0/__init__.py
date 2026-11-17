"""mcp-serve: run Duckwork as an MCP server (``duckwork mcp-serve``).

Formerly built into duckwork-agent core as ``duckwork mcp serve`` (``mcp_serve.py``). Any MCP client
(Claude Code, Claude Desktop, Cursor, Codex, ...) can list and read your messaging conversations, poll
live events, send messages and answer approvals; ``--tools`` adds a curated slice of Duckwork' own tools.
The bridge's ten tool names, schemas and descriptions are unchanged; MCP clients configured with
``["mcp", "serve"]`` change their args to ``["mcp-serve"]``.

Wiring goes only through the public plugin API (``ctx.register_cli_command``); the server module loads
only when the command runs, so discovery stays cheap.
"""

from __future__ import annotations

from .cli import handle_cli, setup_cli


def register(ctx) -> None:
    """Plugin entry point, called by the Duckwork plugin loader."""
    ctx.register_cli_command(
        name="mcp-serve", help="Run Duckwork as an MCP server (expose conversations, optionally tools, to other agents)",
        description="Run Duckwork as a stdio MCP server. MCP client config: "
                    '{"command": "duckwork", "args": ["mcp-serve"]}. Add --tools to also expose Duckwork\' '
                    "web, browser, vision, image generation, skills and TTS tools.",
        setup_fn=setup_cli, handler_fn=handle_cli)


__all__ = ["register"]
