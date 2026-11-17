"""Native Duckwork host context kept outside the harness-neutral core."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

_lock = threading.RLock()
_context: Any | None = None


def configure_native_context(context: Any) -> None:
    global _context
    with _lock:
        _context = context


def clear_native_context() -> None:
    global _context
    with _lock:
        _context = None


def native_context_configured() -> bool:
    with _lock:
        return _context is not None


def _session_key(state_db_path: Path, session_id: str) -> str | None:
    if not session_id or not Path(state_db_path).is_file():
        return None
    uri = f"file:{Path(state_db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            if "session_key" not in columns:
                return None
            row = conn.execute(
                "SELECT session_key FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row or not row[0]:
        return None
    return str(row[0])


def inject_native_message(
    session_id: str,
    state_db_path: Path,
    content: str,
    role: str = "user",
    mode: str = "queue",
) -> bool:
    """Inject through the public Duckwork PluginContext seam, or fail closed."""
    with _lock:
        context = _context
    if context is None:
        return False
    try:
        key = _session_key(state_db_path, session_id)
        return bool(
            context.inject_message(
                content,
                role=role,
                mode=mode,
                session_key=key,
            )
        )
    except Exception:
        return False
