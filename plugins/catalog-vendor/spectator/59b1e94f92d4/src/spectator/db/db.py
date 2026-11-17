"""SQLite database layer for duckwork-spectator.

WAL mode, busy_timeout=5000, single-writer discipline (threading.Lock +
BEGIN IMMEDIATE). All writes go through ``write_txn``; reads use snapshot
isolation.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sqlite3
import stat
import threading
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("spectator.db")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS invites (
    invite_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    session_gen TEXT NOT NULL,
    session_label TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    joined INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guests (
    guest_id TEXT PRIMARY KEY,
    invite_id TEXT NOT NULL REFERENCES invites(invite_id),
    name TEXT DEFAULT '',
    joined_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    summary TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_sources (
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    seq INTEGER NOT NULL REFERENCES events(seq) ON DELETE CASCADE,
    PRIMARY KEY (session_id, source_id)
);

CREATE TABLE IF NOT EXISTS suggestions (
    id TEXT PRIMARY KEY,
    guest_id TEXT NOT NULL REFERENCES guests(guest_id),
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'pending',
    receipt_state TEXT,
    delivery_id TEXT,
    delivery_state TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    receipt_state TEXT
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_expiry ON suggestions(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_suggestions_delivery ON suggestions(delivery_id);
CREATE INDEX IF NOT EXISTS idx_events_session_timestamp ON events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at);

CREATE TABLE IF NOT EXISTS feed_cursor (
    session_id TEXT PRIMARY KEY,
    file_identity TEXT NOT NULL,
    cursor INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Database handle
# ---------------------------------------------------------------------------

_write_lock = threading.Lock()


def _nearest_existing_directory(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _make_private_directories(path: Path) -> None:
    """Create every missing directory in ``path`` with owner-only access."""
    missing: list[Path] = []
    candidate = path
    while not candidate.exists():
        if candidate.is_symlink():
            raise PermissionError(f"runtime storage directory must not be a symlink: {candidate}")
        missing.append(candidate)
        if candidate == candidate.parent:
            raise PermissionError(f"cannot create runtime storage directory: {path}")
        candidate = candidate.parent

    for directory in reversed(missing):
        with contextlib.suppress(FileExistsError):
            directory.mkdir(mode=0o700)
        _require_owned_regular_path(directory)
        if os.name == "posix":
            directory.chmod(0o700)


def _require_safe_parent(path: Path) -> None:
    """Reject parents that another local user could use to replace ``path``."""
    if os.name != "posix":
        return
    parent = _nearest_existing_directory(path.parent)
    parent_stat = parent.stat()
    mode = stat.S_IMODE(parent_stat.st_mode)
    writable_by_others = bool(mode & (stat.S_IWGRP | stat.S_IWOTH))
    sticky = bool(mode & stat.S_ISVTX)
    if writable_by_others and not sticky:
        raise PermissionError(f"runtime storage parent is group/world-writable: {parent}")
    if parent_stat.st_uid not in {0, os.geteuid()} and not sticky:
        raise PermissionError(f"runtime storage parent is not trusted: {parent}")


def _require_owned_regular_path(path: Path) -> None:
    if os.name != "posix":
        return
    if path.is_symlink():
        raise PermissionError(f"runtime storage path must not be a symlink: {path}")
    if not path.exists():
        return
    if path.stat().st_uid != os.geteuid():
        raise PermissionError(f"runtime storage path is not owned by the current user: {path}")


class SpectatorDB:
    """Thread-safe SQLite database with WAL mode and single-writer discipline."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        data_dir = self.db_path.parent
        _require_safe_parent(data_dir)
        if data_dir.is_symlink():
            raise PermissionError(f"runtime storage directory must not be a symlink: {data_dir}")
        _make_private_directories(data_dir)
        _require_safe_parent(data_dir)
        _require_owned_regular_path(data_dir)
        if os.name == "posix":
            data_dir.chmod(0o700)
        _require_safe_parent(self.db_path)
        _require_owned_regular_path(self.db_path)
        self._local = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self._conns_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        # One connection per thread. The poller writes from a background
        # thread while request threads read; sharing a single connection
        # object across threads corrupts transaction state ("cannot commit -
        # no transaction is active"). Thread-local connections keep WAL
        # snapshot reads isolated from the writer's transaction.
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        _require_owned_regular_path(self.db_path)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            _require_owned_regular_path(self.db_path)
            if os.name == "posix":
                self.db_path.chmod(0o600)
        except Exception:
            conn.close()
            raise
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
        with self._conns_lock:
            self._conns.append(conn)
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._connect()

    def init_schema(self) -> None:
        """Create all tables and indexes. Safe to call on an existing DB."""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
        log.info("SpectatorDB schema initialised: %s", self.db_path)

    def write_txn(self) -> _WriteTxn:
        """Context manager: acquires the write lock and opens a BEGIN
        IMMEDIATE transaction. All writes must go through this."""
        return _WriteTxn(self)

    def close(self) -> None:
        with self._conns_lock:
            conns = list(self._conns)
            self._conns.clear()
        for conn in conns:
            with contextlib.suppress(Exception):
                conn.close()


class _WriteTxn:
    """Acquires the module-level write lock and opens BEGIN IMMEDIATE."""

    def __init__(self, db: SpectatorDB) -> None:
        self._db = db

    def __enter__(self) -> sqlite3.Cursor:
        _write_lock.acquire()
        try:
            self._conn = self._db._connect()
            self._cursor = self._conn.cursor()
            self._cursor.execute("BEGIN IMMEDIATE")
            return self._cursor
        except Exception:
            _write_lock.release()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            _write_lock.release()

    def __init_subclass__(cls, **kwargs):  # type: ignore[override]
        super().__init_subclass__(**kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> str:
    """RFC3339 UTC timestamp."""
    return datetime.now(UTC).isoformat()