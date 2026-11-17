"""Local checks that do not require Duckwork."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DUCKWORK_HOME"] = tempfile.mkdtemp(prefix="source-tray-test-")

import tray_hooks
import tray_store
import tray_tools


def test_normalize() -> None:
    assert tray_store.normalize_url("https://Example.COM/a") == "https://example.com/a"
    assert tray_store.normalize_url("not-a-url") is None
    assert tray_store.normalize_url("ftp://x.com") is None


def test_search_results() -> None:
    tray_store.clear_sources()
    payload = json.dumps(
        {
            "results": [
                {"title": "Python docs", "url": "https://docs.python.org/3/"},
                {"title": "PEP 8", "url": "https://peps.python.org/pep-0008/"},
            ]
        }
    )
    tray_hooks.on_post_tool_call(
        "web_search",
        {"query": "python style"},
        payload,
    )
    items = tray_store.list_sources()
    assert len(items) == 2
    urls = {it["url"] for it in items}
    assert "https://docs.python.org/3/" in urls
    assert items[0]["query"] == "python style"


def test_extract_args_urls() -> None:
    tray_store.clear_sources()
    tray_hooks.on_post_tool_call(
        "web_extract",
        {"urls": ["https://example.com/page"]},
        json.dumps({"results": [{"url": "https://example.com/page", "title": "Example", "content": "see https://spam.example/ignore"}]}),
    )
    items = tray_store.list_sources()
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/page"


def test_ignore_terminal() -> None:
    tray_store.clear_sources()
    tray_hooks.on_post_tool_call(
        "terminal",
        {"command": "curl https://example.com"},
        json.dumps({"exit_code": 0, "output": "ok"}),
    )
    assert tray_store.list_sources() == []


def test_dedupe() -> None:
    tray_store.clear_sources()
    tray_hooks.on_post_tool_call(
        "browser_navigate",
        {"url": "https://example.com/a"},
        json.dumps({"ok": True}),
    )
    tray_hooks.on_post_tool_call(
        "browser_navigate",
        {"url": "https://example.com/a"},
        json.dumps({"ok": True}),
    )
    assert len(tray_store.list_sources()) == 1


def test_tools_json() -> None:
    tray_store.clear_sources()
    data = json.loads(tray_tools.source_tray_list({}, extra="x"))
    assert data["ok"] is True
    assert data["count"] == 0
    cleared = json.loads(tray_tools.source_tray_clear({}))
    assert cleared["ok"] is True


if __name__ == "__main__":
    test_normalize()
    test_search_results()
    test_extract_args_urls()
    test_ignore_terminal()
    test_dedupe()
    test_tools_json()
    print("ok")
