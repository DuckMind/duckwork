"""Tool handlers — always return JSON strings, never raise."""

from __future__ import annotations

import json

import sketch_store


def sketch_pad_last(args: dict, **kwargs) -> str:
    del args, kwargs
    try:
        return json.dumps(sketch_store.last_sketch(), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
