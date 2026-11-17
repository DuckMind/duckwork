"""Durable session file path list for file-tray."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "file-tray"
MAX_ITEMS = 40
MAX_PATH = 500
MAX_NAME = 160

WATCH_TOOLS = {
    "read_file",
    "write_file",
    "patch",
}

_ACTION = {
    "read_file": "read",
    "write_file": "write",
    "patch": "patch",
}

_V4A_FILE = re.compile(
    r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$",
    re.MULTILINE,
)


def data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore

        return plugin_data_dir(PLUGIN_ID)
    except Exception:
        home = Path(os.environ.get("DUCKWORK_HOME") or (Path.home() / ".duckwork"))
        path = home / "plugin-data" / PLUGIN_ID
        path.mkdir(parents=True, exist_ok=True)
        return path


def state_path() -> Path:
    return data_dir() / "state.json"


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {"items": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    if not isinstance(raw, dict):
        return {"items": []}
    items = raw.get("items")
    if not isinstance(items, list):
        raw["items"] = []
    return raw


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_path(raw: str) -> str | None:
    text = (raw or "").strip().strip('"').strip("'")
    if not text or len(text) > MAX_PATH:
        return None
    if "\n" in text or "\r" in text or "\x00" in text:
        return None
    # Skip URLs and bare schemes
    lower = text.lower()
    if lower.startswith(("http://", "https://", "ftp://", "file://")):
        return None
    # Collapse redundant separators for Windows / POSIX display
    cleaned = text.replace("\\", "/")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    # Keep drive letters like C:/...
    if len(cleaned) >= 2 and cleaned[1] == ":":
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned[:MAX_PATH]


def display_name(path: str) -> str:
    base = path.rstrip("/").rsplit("/", 1)[-1]
    return (base or path)[:MAX_NAME]


def action_for(tool: str) -> str:
    return _ACTION.get(tool, tool[:32])


def paths_from_args(tool: str, args: dict[str, Any]) -> list[str]:
    found: list[str] = []
    if not isinstance(args, dict):
        return found

    for key in ("path", "file", "filepath", "file_path"):
        val = args.get(key)
        if isinstance(val, str):
            p = normalize_path(val)
            if p:
                found.append(p)

    paths = args.get("paths")
    if isinstance(paths, list):
        for item in paths:
            if isinstance(item, str):
                p = normalize_path(item)
                if p:
                    found.append(p)

    # V4A multi-file patch body (OpenAI-family)
    if tool == "patch":
        mode = str(args.get("mode") or "replace").lower()
        patch_body = args.get("patch")
        if mode == "patch" and isinstance(patch_body, str):
            for match in _V4A_FILE.finditer(patch_body):
                p = normalize_path(match.group(1))
                if p:
                    found.append(p)

    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in found:
        key = p.lower() if os.name == "nt" else p
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def record_files(
    *,
    tool: str,
    paths: list[str],
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:
    state = load_state()
    items: list[dict[str, Any]] = [
        it for it in state.get("items", []) if isinstance(it, dict) and it.get("path")
    ]
    index = {
        (it["path"].lower() if os.name == "nt" else it["path"]): i for i, it in enumerate(items)
    }
    ts = now_iso()
    action = action_for(tool)
    for path in paths:
        key = path.lower() if os.name == "nt" else path
        entry = {
            "path": path,
            "name": display_name(path),
            "action": action,
            "tool": tool,
            "ts": ts,
        }
        if key in index:
            items[index[key]] = entry
        else:
            items.append(entry)
            index[key] = len(items) - 1
    if len(items) > max_items:
        items = items[-max_items:]
    state["items"] = items
    save_state(state)
    return items


def list_files() -> list[dict[str, Any]]:
    state = load_state()
    items = state.get("items")
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict) and it.get("path")]


def clear_files() -> None:
    save_state({"items": []})


def to_markdown(items: list[dict[str, Any]] | None = None) -> str:
    rows = items if items is not None else list_files()
    if not rows:
        return "(file-tray is empty)"
    lines = []
    for i, it in enumerate(rows, 1):
        action = it.get("action") or ""
        path = it["path"]
        if action:
            lines.append(f"{i}. `{path}` ({action})")
        else:
            lines.append(f"{i}. `{path}`")
    return "\n".join(lines)
