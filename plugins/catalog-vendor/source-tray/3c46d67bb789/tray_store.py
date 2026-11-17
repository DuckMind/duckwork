"""Durable session source list for source-tray."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

PLUGIN_ID = "source-tray"
MAX_ITEMS = 40
MAX_TITLE = 160
MAX_QUERY = 200

_URL_RE = re.compile(r"https?://[^\s\]\)<>\"']+", re.IGNORECASE)

WATCH_TOOLS = {
    "web_search",
    "web_extract",
    "browser_navigate",
    "browser_open",
    "web_fetch",
}


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


def parse_tool_payload(result: Any) -> Any:
    if isinstance(result, (dict, list)):
        return result
    if not isinstance(result, str) or not result.strip():
        return {}
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"_text": result}


def normalize_url(raw: str) -> str | None:
    text = (raw or "").strip().rstrip(".,);]")
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    cleaned = urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))
    if len(cleaned) > 500:
        return None
    return cleaned


def _title_from(obj: dict[str, Any], url: str) -> str:
    for key in ("title", "name", "heading"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:MAX_TITLE]
    host = urlparse(url).netloc
    return host or url[:MAX_TITLE]


def _urls_from_text(text: str, found: list[tuple[str, str]]) -> None:
    for match in _URL_RE.findall(text):
        if len(found) >= MAX_ITEMS:
            return
        url = normalize_url(match)
        if url:
            found.append((url, urlparse(url).netloc or url))


def collect_from_obj(obj: Any, found: list[tuple[str, str]]) -> None:
    if len(found) >= MAX_ITEMS:
        return
    if isinstance(obj, dict):
        url = None
        for key in ("url", "href", "link", "uri"):
            val = obj.get(key)
            if isinstance(val, str):
                url = normalize_url(val)
                if url:
                    break
        if url:
            found.append((url, _title_from(obj, url)))
        for key, val in obj.items():
            if key in {"content", "markdown", "text", "output", "body", "snippet"}:
                continue
            if key == "_text" and isinstance(val, str):
                _urls_from_text(val, found)
                continue
            collect_from_obj(val, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_from_obj(item, found)
    elif isinstance(obj, str) and len(obj) < 400:
        _urls_from_text(obj, found)


def urls_from_args(args: dict[str, Any]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if not isinstance(args, dict):
        return found
    for key in ("url", "href"):
        val = args.get(key)
        if isinstance(val, str):
            url = normalize_url(val)
            if url:
                found.append((url, urlparse(url).netloc or url))
    urls = args.get("urls")
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, str):
                url = normalize_url(item)
                if url:
                    found.append((url, urlparse(url).netloc or url))
    return found


def extract_query(args: dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return ""
    for key in ("query", "q", "search"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:MAX_QUERY]
    return ""


def record_sources(
    *,
    tool: str,
    query: str,
    hits: list[tuple[str, str]],
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:
    state = load_state()
    items: list[dict[str, Any]] = [
        it for it in state.get("items", []) if isinstance(it, dict) and it.get("url")
    ]
    index = {it["url"]: i for i, it in enumerate(items)}
    ts = now_iso()
    for url, title in hits:
        entry = {
            "url": url,
            "title": (title or url)[:MAX_TITLE],
            "tool": tool,
            "query": query,
            "ts": ts,
        }
        if url in index:
            items[index[url]] = entry
        else:
            items.append(entry)
            index[url] = len(items) - 1
    if len(items) > max_items:
        items = items[-max_items:]
    state["items"] = items
    save_state(state)
    return items


def list_sources() -> list[dict[str, Any]]:
    state = load_state()
    items = state.get("items")
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict) and it.get("url")]


def clear_sources() -> None:
    save_state({"items": []})


def to_markdown(items: list[dict[str, Any]] | None = None) -> str:
    rows = items if items is not None else list_sources()
    if not rows:
        return "(source-tray is empty)"
    lines = []
    for i, it in enumerate(rows, 1):
        title = it.get("title") or it["url"]
        lines.append(f"{i}. [{title}]({it['url']})")
    return "\n".join(lines)
