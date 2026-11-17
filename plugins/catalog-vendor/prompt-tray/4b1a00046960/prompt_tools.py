"""Tool handlers — always return JSON strings, never raise."""

from __future__ import annotations

import json

import prompt_store


def prompt_tray_list(args: dict, **kwargs) -> str:
    del kwargs
    try:
        markdown = True
        if isinstance(args, dict) and args.get("markdown") is False:
            markdown = False
        items = prompt_store.list_prompts()
        payload: dict = {"ok": True, "count": len(items), "items": items}
        if markdown:
            payload["markdown"] = prompt_store.to_markdown(items)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
