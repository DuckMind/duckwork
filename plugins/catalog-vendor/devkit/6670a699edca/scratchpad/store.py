"""Per-session scratchpad buffers: named drafts edited in place, removed with their session.

Buffers live under the plugin's data root, one directory per session:
``<DUCKWORK_HOME>/plugin-data/devkit/sessions/<dir>/<name>``. Each session directory carries
``.session`` (the raw session id) and ``.stamp.json`` (our own record: created / last_active),
written only through the plugin's own hooks so cleanup never depends on Duckwork internals alone.

Cleanup is layered (``reconcile``):
1. ``state.db`` fast path: a directory whose session row is gone is removed. Fails safe: an
   unreadable database removes nothing, and a read that matches none of our sessions while
   several would be removed is treated as a schema change and skipped.
2. Our own stamp: a directory idle longer than ``idle_days`` (Duckwork' auto-prune window) is
   removed whatever the database says.
The Desktop viewer is the manual backup.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import sqlite3
import time
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
IDLE_DAYS = 90
GRACE_SECONDS = 3600
TOUCH_EVERY_SECONDS = 300
_SESSION_FILE = ".session"
_STAMP_FILE = ".stamp.json"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_DIR = re.compile(r"^[A-Za-z0-9_-]{1,96}$")


class ScratchpadError(ValueError):
    pass


def default_root() -> Path:
    from plugins.plugin_storage import plugin_data_dir
    return plugin_data_dir("devkit") / "sessions"


def _dir_name(session_id: str) -> str:
    if _SAFE_DIR.match(session_id):
        return session_id
    return "s-" + hashlib.sha256(session_id.encode()).hexdigest()[:32]


def _read_stamp(path: Path) -> dict:
    try:
        data = json.loads((path / _STAMP_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_stamp(path: Path, stamp: dict) -> None:
    tmp = path / (_STAMP_FILE + ".tmp")
    tmp.write_text(json.dumps(stamp), encoding="utf-8")
    tmp.replace(path / _STAMP_FILE)


def session_dir(root: Path, session_id: str, *, create: bool = True) -> Path:
    if not session_id:
        raise ScratchpadError("no session is bound to this call")
    path = root / _dir_name(session_id)
    if create and not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        (path / _SESSION_FILE).write_text(session_id, encoding="utf-8")
        now = time.time()
        _write_stamp(path, {"session_id": session_id, "created": now, "last_active": now})
    return path


def touch(root: Path, session_id: str, *, now: float | None = None) -> bool:
    """Record activity for a session that already has a scratchpad; never creates one."""
    if not session_id:
        return False
    path = root / _dir_name(session_id)
    if not path.is_dir():
        return False
    now = time.time() if now is None else now
    stamp = _read_stamp(path)
    if now - float(stamp.get("last_active") or 0) < TOUCH_EVERY_SECONDS:
        return False
    stamp.setdefault("session_id", session_id)
    stamp.setdefault("created", now)
    stamp["last_active"] = now
    _write_stamp(path, stamp)
    return True


def _buffer(root: Path, session_id: str, name: str, *, create_dir: bool = False) -> Path:
    if not isinstance(name, str) or not _NAME.match(name):
        raise ScratchpadError(
            f"invalid buffer name {name!r}: use a plain file name like 'main.py' (letters, digits, . _ -)")
    return session_dir(root, session_id, create=create_dir) / name


def _describe(path: Path, **extra) -> dict:
    text = path.read_text(encoding="utf-8")
    return {"name": path.name, "path": str(path), "bytes": len(text.encode("utf-8")),
            "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0), **extra}


def write(root: Path, session_id: str, name: str, content: str) -> dict:
    if not isinstance(content, str):
        raise ScratchpadError("content must be a string")
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ScratchpadError(f"buffer larger than {MAX_BYTES} bytes")
    path = _buffer(root, session_id, name, create_dir=True)
    created = not path.exists()
    path.write_text(content, encoding="utf-8")
    touch(root, session_id)
    return _describe(path, created=created)


def patch(root: Path, session_id: str, name: str, old: str, new: str, *, replace_all: bool = False) -> dict:
    path = _existing(root, session_id, name)
    text = path.read_text(encoding="utf-8")
    if not old:
        raise ScratchpadError("old_text must not be empty")
    count = text.count(old)
    if count == 0:
        raise ScratchpadError(f"old_text not found in {name}")
    if count > 1 and not replace_all:
        raise ScratchpadError(f"old_text matches {count} places in {name}; add context or set replace_all")
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    if len(updated.encode("utf-8")) > MAX_BYTES:
        raise ScratchpadError(f"buffer larger than {MAX_BYTES} bytes")
    path.write_text(updated, encoding="utf-8")
    touch(root, session_id)
    return _describe(path, replacements=count if replace_all else 1)


def read(root: Path, session_id: str, name: str) -> dict:
    path = _existing(root, session_id, name)
    return _describe(path, content=path.read_text(encoding="utf-8"))


def _buffer_files(path: Path) -> list[Path]:
    return [p for p in sorted(path.iterdir()) if p.is_file() and not p.name.startswith(".")]


def list_buffers(root: Path, session_id: str) -> list[dict]:
    path = session_dir(root, session_id, create=False)
    if not path.is_dir():
        return []
    return [_describe(p) for p in _buffer_files(path)]


def delete(root: Path, session_id: str, name: str) -> dict:
    path = _existing(root, session_id, name)
    path.unlink()
    return {"name": name, "deleted": True}


def buffer_path(root: Path, session_id: str, name: str) -> Path:
    return _existing(root, session_id, name)


def _existing(root: Path, session_id: str, name: str) -> Path:
    path = _buffer(root, session_id, name)
    if not path.is_file():
        raise ScratchpadError(f"no buffer named {name!r} in this session")
    return path


# --- inventory and manual cleanup (the Desktop viewer) ---------------------------------------

def _entry_session_id(entry: Path) -> str | None:
    try:
        return (entry / _SESSION_FILE).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _last_active(entry: Path) -> float:
    stamped = _read_stamp(entry).get("last_active")
    if isinstance(stamped, (int, float)) and stamped > 0:
        return float(stamped)
    times = [entry.stat().st_mtime] + [p.stat().st_mtime for p in entry.iterdir() if p.is_file()]
    return max(times)


def _session_entries(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [e for e in sorted(root.iterdir()) if e.is_dir() and _entry_session_id(e)]


def inventory(root: Path) -> list[dict]:
    rows = []
    for entry in _session_entries(root):
        stamp = _read_stamp(entry)
        files = _buffer_files(entry)
        rows.append({
            "dir": entry.name,
            "session_id": _entry_session_id(entry),
            "created": stamp.get("created"),
            "last_active": _last_active(entry),
            "bytes": sum(p.stat().st_size for p in files),
            "buffers": [{"name": p.name, "bytes": p.stat().st_size} for p in files],
        })
    rows.sort(key=lambda r: r["last_active"], reverse=True)
    return rows


def with_existence(rows: list[dict], live: set[str] | None) -> list[dict]:
    """Add ``exists`` (True/False, or None when unknown) to inventory rows. A database read that
    matches none of two or more folders is treated as unknown, like reconcile's schema guard."""
    if live is not None and len(rows) >= 2 and not any(r["session_id"] in live for r in rows):
        live = None
    return [{**r, "exists": None if live is None else r["session_id"] in live} for r in rows]


def _entry_by_dir(root: Path, dir_name: str) -> Path:
    if not isinstance(dir_name, str) or not _SAFE_DIR.match(dir_name):
        raise ScratchpadError(f"invalid session folder {dir_name!r}")
    entry = root / dir_name
    if not entry.is_dir() or not _entry_session_id(entry):
        raise ScratchpadError(f"no scratchpad folder {dir_name!r}")
    return entry


def read_in_dir(root: Path, dir_name: str, name: str) -> dict:
    entry = _entry_by_dir(root, dir_name)
    path = entry / name if isinstance(name, str) and _NAME.match(name) else None
    if path is None or not path.is_file():
        raise ScratchpadError(f"no buffer named {name!r}")
    return _describe(path, content=path.read_text(encoding="utf-8"), session_id=_entry_session_id(entry))


def write_in_dir(root: Path, dir_name: str, name: str, content: str) -> dict:
    """Save a user edit from the Desktop viewer into an existing buffer."""
    entry = _entry_by_dir(root, dir_name)
    path = entry / name if isinstance(name, str) and _NAME.match(name) else None
    if path is None or not path.is_file():
        raise ScratchpadError(f"no buffer named {name!r}")
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_BYTES:
        raise ScratchpadError(f"content must be text no larger than {MAX_BYTES} bytes")
    path.write_text(content, encoding="utf-8")
    touch(root, _entry_session_id(entry) or "")
    return _describe(path)


def remove_session_dir(root: Path, dir_name: str) -> dict:
    entry = _entry_by_dir(root, dir_name)
    shutil.rmtree(entry)
    return {"dir": dir_name, "removed": True}


def remove_buffer_in_dir(root: Path, dir_name: str, name: str) -> dict:
    entry = _entry_by_dir(root, dir_name)
    if not isinstance(name, str) or not _NAME.match(name) or not (entry / name).is_file():
        raise ScratchpadError(f"no buffer named {name!r}")
    (entry / name).unlink()
    return {"dir": dir_name, "name": name, "deleted": True}


def remove_all(root: Path) -> dict:
    removed = [e.name for e in _session_entries(root)]
    for name in removed:
        shutil.rmtree(root / name, ignore_errors=True)
    return {"removed": removed}


# --- automatic cleanup -----------------------------------------------------------------------

def db_session_ids(state_db: Path) -> set[str] | None:
    if not state_db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True, timeout=5)
        try:
            return {row[0] for row in conn.execute("SELECT id FROM sessions")}
        finally:
            conn.close()
    except sqlite3.Error:
        return None


@contextlib.contextmanager
def _exclusive(root: Path):
    """One reconcile at a time across Duckwork processes; yields False when another holds it."""
    root.mkdir(parents=True, exist_ok=True)
    handle = open(root / ".reconcile.lock", "a+")
    try:
        try:
            import fcntl
        except ImportError:  # Windows: no advisory lock; reconcile is idempotent anyway
            yield True
            return
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        handle.close()


def reconcile(root: Path, state_db: Path, *, idle_days: float = IDLE_DAYS,
              grace_seconds: float = GRACE_SECONDS, now: float | None = None) -> list[dict]:
    """Remove folders of deleted or long-idle sessions; returns ``{session_id, reason}`` rows."""
    if not root.is_dir():
        return []
    now = time.time() if now is None else now
    with _exclusive(root) as held:
        if not held:
            return []
        entries = [(e, _entry_session_id(e)) for e in _session_entries(root)]
        live = db_session_ids(state_db)
        by_db, by_idle = [], []
        for entry, session_id in entries:
            idle = now - _last_active(entry)
            if idle < grace_seconds:
                continue
            if live is not None and session_id not in live:
                by_db.append((entry, session_id))
            elif idle > idle_days * 86400:
                by_idle.append((entry, session_id))
        overlap = live is not None and any(sid in live for _, sid in entries)
        if by_db and not overlap and len(by_db) >= 2:
            # The database matches none of our sessions: most likely a schema change, not a mass
            # delete. Leave these to the idle rule and the viewer.
            by_idle.extend((e, s) for e, s in by_db if now - _last_active(e) > idle_days * 86400)
            by_db = []
        removed = []
        for reason, group in (("deleted", by_db), ("idle", by_idle)):
            for entry, session_id in group:
                shutil.rmtree(entry, ignore_errors=True)
                removed.append({"session_id": session_id, "reason": reason})
        return removed
