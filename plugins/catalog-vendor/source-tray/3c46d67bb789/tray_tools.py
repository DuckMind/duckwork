"""Tool handlers — always return JSON strings, never raise."""

from __future__ import annotations

import json

import tray_store


def source_tray_list(args: dict, **kwargs) -> str:
    del kwargs
    try:
        markdown = True
        if isinstance(args, dict) and args.get("markdown") is False:
            markdown = False
        items = tray_store.list_sources()
        payload: dict = {"ok": True, "count": len(items), "items": items}
        if markdown:
            payload["markdown"] = tray_store.to_markdown(items)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})


def source_tray_clear(args: dict, **kwargs) -> str:
    del args, kwargs
    try:
        tray_store.clear_sources()
        return json.dumps({"ok": True, "count": 0, "items": []})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
