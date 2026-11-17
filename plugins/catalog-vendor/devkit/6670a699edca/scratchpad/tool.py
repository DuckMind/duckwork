"""The ``scratchpad`` tool: schema and handler."""
from __future__ import annotations

import json
import os

from . import store

SCHEMA = {
    "name": "scratchpad",
    "description": (
        "Default home for drafts you show, discuss or iterate on with the user: code, HTML pages, "
        "lesson pads, notes. Each session has its own named buffers that you edit in place (write "
        "once, then patch) instead of creating a new file per draft; they are deleted with the "
        "session. action=open shows a buffer in the Desktop code viewer/preview, where the user can "
        "edit it too. Not for throwaway machinery nobody reads (screenshots, downloads, logs, "
        "one-off helper scripts): those go to ~/.duckwork/cache/scratch. Real files only when the work "
        "moves into a project or the user asks for a file: action=promote with the destination. "
        "Actions: write, patch, read, list, open, delete, promote."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["write", "patch", "read", "list", "open", "delete", "promote"]},
            "name": {"type": "string",
                     "description": "Buffer file name, e.g. 'main.py' or 'page.html' (extension sets highlighting)."},
            "content": {"type": "string", "description": "write: the full buffer content."},
            "old_text": {"type": "string", "description": "patch: exact text to replace."},
            "new_text": {"type": "string", "description": "patch: replacement text."},
            "replace_all": {"type": "boolean", "description": "patch: replace every match."},
            "path": {"type": "string",
                     "description": "promote: absolute or ~ destination path of the real file."},
            "overwrite": {"type": "boolean", "description": "promote: replace an existing file."},
        },
        "required": ["action"],
    },
}

_ctx = None
_root_override = None


def bind(ctx) -> None:
    global _ctx
    _ctx = ctx


def _root():
    return _root_override if _root_override is not None else store.default_root()


def _session(session_id, task_id):
    return str(session_id or task_id or "")


def _ok(data) -> str:
    return json.dumps({"success": True, **data}, ensure_ascii=False)


def _err(message) -> str:
    return json.dumps({"success": False, "error": str(message)}, ensure_ascii=False)


def handle(args, session_id=None, task_id=None, **_kw) -> str:
    args = args or {}
    action = (args.get("action") or "").strip()
    sid = _session(session_id, task_id)
    root = _root()
    try:
        if action == "write":
            return _ok(store.write(root, sid, args.get("name"), args.get("content", "")))
        if action == "patch":
            return _ok(store.patch(root, sid, args.get("name"), args.get("old_text", ""),
                                   args.get("new_text", ""), replace_all=bool(args.get("replace_all"))))
        if action == "read":
            return _ok(store.read(root, sid, args.get("name")))
        if action == "list":
            return _ok({"buffers": store.list_buffers(root, sid)})
        if action == "delete":
            return _ok(store.delete(root, sid, args.get("name")))
        if action == "open":
            return _open(root, sid, args.get("name"))
        if action == "promote":
            return _promote(root, sid, args.get("name"), args.get("path"), bool(args.get("overwrite")))
        return _err("action must be one of: write, patch, read, list, open, delete, promote")
    except store.ScratchpadError as exc:
        return _err(exc)


def _open(root, sid, name) -> str:
    path = store.buffer_path(root, sid, name)
    if _ctx is None:
        return _err("scratchpad is not registered with Duckwork")
    return _ctx.dispatch_tool("desktop_preview", {"action": "open", "url": str(path), "label": name})


def _promote(root, sid, name, dest, overwrite) -> str:
    path = store.buffer_path(root, sid, name)
    if not dest or not isinstance(dest, str):
        return _err("promote needs path: the absolute or ~ destination of the real file")
    target = os.path.expanduser(dest)
    if not os.path.isabs(target):
        return _err("promote path must be absolute or start with ~")
    if os.path.exists(target) and not overwrite:
        return _err(f"{target} already exists; set overwrite to replace it")
    if _ctx is None:
        return _err("scratchpad is not registered with Duckwork")
    result = _ctx.dispatch_tool("write_file", {"path": target, "content": path.read_text(encoding="utf-8")})
    return json.dumps({"success": True, "promoted": name, "path": target, "write_file": _maybe_json(result)},
                      ensure_ascii=False)


def _maybe_json(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw
