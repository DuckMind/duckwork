"""post_tool_call observer — collect web/browser URLs into the tray."""

from __future__ import annotations

import tray_store

WATCH_TOOLS = tray_store.WATCH_TOOLS


def on_post_tool_call(tool_name: str, args: dict, result: str, **kwargs) -> None:
    del kwargs
    try:
        if tool_name not in WATCH_TOOLS:
            return
        payload = tray_store.parse_tool_payload(result)
        arg_map = args if isinstance(args, dict) else {}
        hits = tray_store.urls_from_args(arg_map)
        tray_store.collect_from_obj(payload, hits)
        # Dedupe this call while preserving first title
        seen: dict[str, str] = {}
        for url, title in hits:
            if url not in seen:
                seen[url] = title
        if not seen:
            return
        tray_store.record_sources(
            tool=tool_name,
            query=tray_store.extract_query(arg_map),
            hits=list(seen.items()),
        )
    except Exception:
        return
