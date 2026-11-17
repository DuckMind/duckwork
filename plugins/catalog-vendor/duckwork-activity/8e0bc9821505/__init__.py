"""duckwork-activity: GitHub-style activity page for Duckwork Desktop.

Registers:
  * ``duckwork activity`` CLI command (``summary`` / ``day``, ``--json`` for the desktop page);
  * ``/activity`` slash command with a short text summary.

The desktop UI lives in ``desktop/plugin.js`` (built from ``src/plugin.tsx``) and reads
data by running ``duckwork activity ... --json`` through the gateway's ``cli.exec`` RPC.
Everything is read-only over the local session store; there are no network calls.
"""

from __future__ import annotations

from . import commands


def register(ctx) -> None:
    ctx.register_command(
        "activity",
        handler=commands.slash_command,
        description="Show token and session totals (duckwork-activity)",
        args_hint="[days]",
    )
    ctx.register_cli_command(
        name="activity",
        help="Usage activity: tokens, sessions, models (duckwork-activity plugin)",
        setup_fn=commands.setup_argparse,
        handler_fn=commands.handle_cli,
    )
