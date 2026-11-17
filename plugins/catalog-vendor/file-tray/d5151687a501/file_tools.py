"""Tool handlers — always return JSON strings, never raise."""

from __future__ import annotations

import json

import file_store


def file_tray_list(args: dict, **kwargs) -> str:
    del kwargs
    try:
        markdown = True
        if isinstance(args, dict) and args.get("markdown") is False:
            markdown = False
        items = file_store.list_files()
        payload: dict = {"ok": True, "count": len(items), "items": items}
        if markdown:
            payload["markdown"] = file_store.to_markdown(items)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})


def file_tray_clear(args: dict, **kwargs) -> str:
    del args, kwargs
    try:
        file_store.clear_files()
        return json.dumps({"ok": True, "count": 0, "items": []})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
