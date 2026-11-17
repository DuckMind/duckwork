"""Saved composer prompts under plugin-data."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ID = "prompt-tray"
MAX_ITEMS = 40
MAX_TITLE = 48
MAX_BODY = 2000

_SLUG = re.compile(r"[^a-z0-9]+")

DEFAULTS: list[dict[str, str]] = [
    {
        "id": "review",
        "title": "Review",
        "body": (
            "Review the latest changes. Point out bugs, risks, and missing tests. "
            "Do not rewrite everything."
        ),
    },
    {
        "id": "plan",
        "title": "Plan",
        "body": "Make a short plan first. Do not write code until I approve.",
    },
    {
        "id": "explain",
        "title": "Explain",
        "body": "Explain this in plain language. No extra files.",
    },
]


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
    return data_dir() / "prompts.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_title(raw: str) -> str:
    text = " ".join((raw or "").split())
    return text[:MAX_TITLE]


def _clean_body(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) > MAX_BODY:
        text = text[:MAX_BODY]
    return text


def _new_id(title: str) -> str:
    base = _SLUG.sub("-", title.lower()).strip("-")[:24] or "prompt"
    return f"{base}-{uuid.uuid4().hex[:8]}"


def _normalize_item(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    title = _clean_title(str(raw.get("title") or ""))
    body = _clean_body(str(raw.get("body") or ""))
    if not title or not body:
        return None
    item_id = str(raw.get("id") or "").strip() or _new_id(title)
    item_id = item_id[:40]
    ts = str(raw.get("ts") or now_iso())
    return {"id": item_id, "title": title, "body": body, "ts": ts}


def _seed() -> list[dict[str, str]]:
    ts = now_iso()
    return [{**row, "ts": ts} for row in DEFAULTS]


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        items = _seed()
        state = {"items": items}
        save_state(state)
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": _seed()}
    if not isinstance(raw, dict):
        return {"items": _seed()}
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in raw.get("items") or []:
        item = _normalize_item(row)
        if item is None or item["id"] in seen:
            continue
        seen.add(item["id"])
        items.append(item)
        if len(items) >= MAX_ITEMS:
            break
    return {"items": items}


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def list_prompts() -> list[dict[str, str]]:
    items = load_state().get("items")
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict) and it.get("id")]


def add_prompt(title: str, body: str) -> dict[str, Any]:
    title_n = _clean_title(title)
    body_n = _clean_body(body)
    if not title_n or not body_n:
        return {"ok": False, "error": "Title and body are required."}
    items = list_prompts()
    if len(items) >= MAX_ITEMS:
        return {"ok": False, "error": f"Tray is full ({MAX_ITEMS})."}
    item = {
        "id": _new_id(title_n),
        "title": title_n,
        "body": body_n,
        "ts": now_iso(),
    }
    items.append(item)
    save_state({"items": items})
    return {"ok": True, "item": item, "count": len(items), "items": items}


def delete_prompt(item_id: str) -> dict[str, Any]:
    wanted = (item_id or "").strip()
    items = list_prompts()
    kept = [it for it in items if it["id"] != wanted]
    if len(kept) == len(items):
        return {"ok": False, "error": "Prompt not found.", "count": len(items), "items": items}
    save_state({"items": kept})
    return {"ok": True, "count": len(kept), "items": kept}


def to_markdown(items: list[dict[str, str]] | None = None) -> str:
    rows = items if items is not None else list_prompts()
    if not rows:
        return "(prompt-tray is empty)"
    lines = []
    for i, it in enumerate(rows, 1):
        lines.append(f"{i}. **{it['title']}** — {it['body']}")
    return "\n".join(lines)
