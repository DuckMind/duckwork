# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Tool schemas: the bundled snapshot, the per-profile cache, and MCP to Duckwork conversion."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

SNAPSHOT_FILE = Path(__file__).with_name("tools_snapshot.json")
CACHE_DIR = "lumberroom"
CACHE_NAME = "tools_cache.json"

def load_snapshot() -> dict[str, Any]:
    """{"handshake", "server_info", "instructions", "tools": [MCP tool dicts]} as L0 captured it."""
    return json.loads(SNAPSHOT_FILE.read_text())


def _cache_path(duckwork_home: str) -> Path:
    return Path(duckwork_home) / CACHE_DIR / CACHE_NAME


def read_cache(duckwork_home: str) -> dict[str, Any] | None:
    """The last live listing for this profile, same shape as the snapshot; None when absent or unreadable."""
    try:
        return json.loads(_cache_path(duckwork_home).read_text())
    except (OSError, ValueError):
        return None


def write_cache(duckwork_home: str, listing: Mapping[str, Any]) -> None:
    """Atomic write of {"instructions", "tools"} to $DUCKWORK_HOME/lumberroom/tools_cache.json."""
    path = _cache_path(duckwork_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(listing)))
    os.replace(tmp, path)


def to_duckwork_schema(tool: Mapping[str, Any]) -> dict[str, Any]:
    """MCP {"name", "description", "inputSchema"} to Duckwork {"name", "description", "parameters"}."""
    input_schema = dict(tool.get("inputSchema") or {})
    input_schema.pop("$schema", None)
    input_schema.pop("title", None)
    input_schema.setdefault("type", "object")
    input_schema.setdefault("properties", {})
    return {"name": tool["name"], "description": tool.get("description", ""), "parameters": input_schema}


def select(allowlist: Sequence[str], tools: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The MCP tool dicts whose names the allowlist carries, in allowlist order."""
    by_name = {tool["name"]: tool for tool in tools}
    return [dict(by_name[name]) for name in allowlist if name in by_name]
