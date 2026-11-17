# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Parcel deliveries for Duckwork: read, add, and look up carriers through Parcel's API."""
from __future__ import annotations

import threading
from pathlib import Path

from . import tools
from .client import ParcelClient

_client = None
_client_lock = threading.Lock()


def _get_client() -> ParcelClient:
    # One client per process; it resolves the API key per call, so profile scoping still applies.
    global _client
    with _client_lock:
        if _client is None:
            _client = ParcelClient()
        return _client


def _deliveries(args, **kwargs):
    return tools.handle_deliveries(_get_client(), args or {})


def _add(args, **kwargs):
    return tools.handle_add(_get_client(), args or {})


def _carriers(args, **kwargs):
    return tools.handle_carriers(_get_client(), args or {})


def _slash_parcel(raw_args: str = "") -> str:
    mode = "recent" if (raw_args or "").strip().lower() == "recent" else "active"
    return tools.format_for_command(tools.handle_deliveries(_get_client(), {"filter": mode}))


def register(ctx):
    for schema, handler, emoji in (
        (tools.DELIVERIES_SCHEMA, _deliveries, "📦"),
        (tools.ADD_SCHEMA, _add, "➕"),
        (tools.CARRIERS_SCHEMA, _carriers, "🚚"),
    ):
        ctx.register_tool(name=schema["name"], toolset="parcel", schema=schema, handler=handler,
                          description=schema["description"], emoji=emoji)
    ctx.register_command("parcel", _slash_parcel,
                         description="Show deliveries on the way (Parcel)", args_hint="[recent]")
    ctx.register_skill("deliveries", Path(__file__).parent / "skills" / "deliveries" / "SKILL.md",
                       description="How to answer delivery questions and add packages with Parcel.")
