"""post_tool_call observer — collect read/write/patch paths into the tray."""

from __future__ import annotations

import file_store

WATCH_TOOLS = file_store.WATCH_TOOLS


def on_post_tool_call(tool_name: str, args: dict, result: str, **kwargs) -> None:
    del result, kwargs
    try:
        if tool_name not in WATCH_TOOLS:
            return
        arg_map = args if isinstance(args, dict) else {}
        paths = file_store.paths_from_args(tool_name, arg_map)
        if not paths:
            return
        file_store.record_files(tool=tool_name, paths=paths)
    except Exception:
        return
