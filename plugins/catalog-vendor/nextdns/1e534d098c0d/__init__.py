"""Duckwork Agent plugin: NextDNS query logs and analytics.

Read-only access to the NextDNS API for DNS triage: what was resolved, what
was blocked and by which list, and aggregate counts per domain or device.
"""

from . import schemas, tools

_TOOLS = (
    ("nextdns_logs", schemas.LOGS, tools.nextdns_logs),
    ("nextdns_blocked", schemas.BLOCKED, tools.nextdns_blocked),
    ("nextdns_analytics", schemas.ANALYTICS, tools.nextdns_analytics),
    ("nextdns_profile", schemas.PROFILE, tools.nextdns_profile),
)


def register(ctx):
    for name, schema, handler in _TOOLS:
        ctx.register_tool(name=name, toolset="nextdns", schema=schema, handler=handler)

    def _handle_nextdns(raw_args: str) -> str:
        return tools.nextdns_analytics({"metric": "status"})

    ctx.register_command(
        "nextdns",
        handler=_handle_nextdns,
        description="NextDNS query totals (default / blocked / relayed)",
    )
