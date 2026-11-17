"""Tool handlers — always return JSON strings, never raise."""

from __future__ import annotations

import json

import bell_store


def done_bell_status(args: dict, **kwargs) -> str:
    del kwargs
    try:
        payload_in = args if isinstance(args, dict) else {}
        if "mute" in payload_in and payload_in["mute"] is not None:
            bell_store.patch_settings({"muted": bool(payload_in["mute"])})
        snap = bell_store.snapshot()
        markdown = True
        if payload_in.get("markdown") is False:
            markdown = False
        if markdown:
            snap["markdown"] = bell_store.to_markdown(snap)
        return json.dumps(snap, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
