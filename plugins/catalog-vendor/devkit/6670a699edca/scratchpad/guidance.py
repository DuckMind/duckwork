"""Make the scratchpad the default for drafts: a short per-turn rule naming the right place."""
from __future__ import annotations

from . import store

_RULE = ("[where things go] Drafts you show, discuss or iterate on with the user (code, HTML pages, "
         "notes) -> the `scratchpad` tool: named buffers for this session, edited in place with patch, "
         "shown with action=open. Throwaway machinery nobody reads (screenshots, downloads, logs, "
         "one-off helper scripts) -> ~/.duckwork/cache/scratch. Project work, or the user asks for a "
         "file -> write_file or scratchpad action=promote. If `scratchpad` is not directly callable, "
         "load it with tool_describe(names=[\"scratchpad\"]).")


def reminder(root_fn, session_id=None, **_kw):
    """``pre_llm_call``: the rule plus this session's buffer names."""
    text = _RULE
    if session_id:
        try:
            names = [b["name"] for b in store.list_buffers(root_fn(), str(session_id))]
        except Exception:
            names = []
        if names:
            text += " Scratchpad buffers: " + ", ".join(names[:20]) + "."
    return {"context": text}
