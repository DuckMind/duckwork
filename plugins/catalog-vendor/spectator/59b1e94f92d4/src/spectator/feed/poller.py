"""Transcript-tail poller — background producer for the Spectator event feed.

Reads the host session's transcript (the Duckwork ``state.db`` ``messages``
table) via stdlib ``sqlite3`` only and emits structured, privacy-masked
summaries into the existing :class:`spectator.feed.engine.FeedEngine`.

P7 constraint: this module imports ZERO ``duckwork_*`` / ``agent_peer`` symbols.
It depends only on the stdlib and the in-package ``spectator.feed.engine`` and
``spectator.db.db`` modules.

Design notes
------------
- **Source.** ``state.db`` ``messages`` table: ``id`` (global monotonic),
  ``session_id``, ``role``, ``content``, ``tool_calls``, ``tool_name``.
- **Tail cursor.** The highest ``messages.id`` already consumed for the host
  ``session_id``. Persisted in ``spectator.db`` ``feed_cursor`` keyed on
  ``session_id``. On first sighting the cursor baselines to ``0`` (no history
  suppression — a fresh spectator session replays existing rows once); the
  events table is bounded by the existing 7-day retention sweep.
- **file_identity.** ``f"{st_dev}:{st_ino}"`` of the state.db file, re-statted
  every poll. A changed identity (file rotation / new source) resets the cursor
  to ``0`` and emits a ``status_change: feed_reset`` event.
- **Raw content never copied.** Only typed scalars + a role/tool-derived note
  are emitted; ``content`` is reduced to a character/byte count, tool arguments
  to a count of top-level keys, and tool results to an ``ok|error`` status and
  byte size. Nothing free-text from the source ever reaches ``append``.
- **Status machine.** ``active`` / ``idle`` / ``source_error``. ``idle`` fires
  once after ``idle_threshold`` seconds of silence; ``source_error`` is emitted
  at most once per ``error_throttle`` seconds and never crashes the worker;
  recovery and rotation emit immediately.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import UTC
from pathlib import Path

from spectator.db.db import SpectatorDB
from spectator.feed.engine import FeedEngine, privacy_mask

log = logging.getLogger("spectator.feed.poller")

# One-line intent notes derived from the role only (never from raw content).
_ROLE_NOTES = {
    "user": "user message",
    "assistant": "assistant reply",
    "system": "system message",
}

# Maximum bytes of a tool-result content we will parse to classify ok/error.
# The size summary still reports the FULL byte length; only the classification
# reads the head.
_CLASSIFY_PARSE_CAP = 65_536


class TranscriptPoller:
    """Tail-poll the host transcript and feed structured summaries to the engine.

    Thread-safe. ``poll_once`` never raises (source errors are recorded and
    throttled); ``start``/``stop`` manage the background worker thread.
    """

    def __init__(
        self,
        engine: FeedEngine,
        db: SpectatorDB,
        state_db_path: Path,
        poll_interval: float = 2.0,
        idle_threshold: float = 10.0,
        error_throttle: float = 60.0,
        max_rows_per_poll: int = 1000,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.engine = engine
        self.db = db
        self.session_id = engine.session_id
        self.state_db_path = Path(state_db_path)
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold
        self.error_throttle = error_throttle
        self.max_rows_per_poll = max_rows_per_poll
        self._clock = clock

        # Live status / throttle bookkeeping.
        self.in_error = False
        self._status = "active"  # active | idle | source_error
        self._last_activity = self._clock()
        # -inf so the FIRST error always emits immediately.
        self._last_error_emit = float("-inf")

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Live source status (exposed to plugin_api /status)
    # ------------------------------------------------------------------

    @property
    def source_status(self) -> str:
        """Live source truth: ``"transcript"`` when readable, ``"error"`` when
        dead, ``"unconfigured"`` when no host session identity exists to tail."""
        if not self.session_id:
            return "unconfigured"
        return "error" if self.in_error else "transcript"

    # ------------------------------------------------------------------
    # Cursor persistence (transcript-tail cursor, distinct from guest feed seq)
    # ------------------------------------------------------------------

    def _load_cursor(self) -> tuple[str | None, int]:
        # Short-lived read connection: never share the module write connection
        # across the background poller thread and request threads.
        conn = sqlite3.connect(str(self.db.db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT file_identity, cursor FROM feed_cursor WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None, 0
        return row["file_identity"], int(row["cursor"])

    def _save_cursor(self, file_identity: str, cursor: int) -> None:
        with self.db.write_txn() as cur:
            cur.execute(
                """
                INSERT INTO feed_cursor (session_id, file_identity, cursor, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    file_identity = excluded.file_identity,
                    cursor = excluded.cursor,
                    updated_at = excluded.updated_at
                """,
                (self.session_id, file_identity, cursor, self._now_iso()),
            )

    def _now_iso(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self._clock(), tz=UTC).isoformat(
            timespec="microseconds"
        )

    def _file_identity(self) -> str:
        st = os.stat(str(self.state_db_path))
        return f"{st.st_dev}:{st.st_ino}"

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    def poll_once(self) -> None:
        """One synchronous pass. Never raises — errors degrade to source_error."""
        try:
            self._poll_once_inner()
        except Exception:
            log.exception("TranscriptPoller.poll_once failed; swallowing to keep worker alive")
            self._record_error()

    def _poll_once_inner(self) -> None:
        if not self.session_id:
            # No host session identity — nothing to tail.
            return

        now = self._clock()

        # 1. Compute current file identity (stat fails -> source error path).
        try:
            identity = self._file_identity()
        except OSError as exc:
            log.debug("Transcript source unreadable (stat): %s", exc)
            self._record_error(now)
            return

        # 2. Rotation check: only when a prior identity exists and differs.
        stored_identity, stored_cursor = self._load_cursor()
        if stored_identity is None:
            # First sighting — baseline cursor 0, no reset event.
            self._save_cursor(identity, 0)
            cursor = 0
        elif stored_identity != identity:
            log.info(
                "Transcript source rotated (%s -> %s); resetting cursor",
                stored_identity, identity,
            )
            self._save_cursor(identity, 0)
            self._emit_status_change(self._status, "feed_reset")
            self._status = "active"
            self._last_activity = now
            cursor = 0
        else:
            cursor = stored_cursor

        # 3. Read new rows (read-only connection, fresh each poll).
        try:
            rows = self._read_new_rows(cursor)
        except (sqlite3.Error, OSError) as exc:
            log.debug("Transcript source unreadable/locked: %s", exc)
            self._record_error(now)
            return

        # 4. Emit summaries for each row, in id order.
        new_max_id = cursor
        for row in rows:
            for event_type, summary in self._row_to_events(row):
                self.engine.append(event_type, summary)
            new_max_id = max(new_max_id, int(row["id"]))

        # 5. Advance cursor only for rows actually consumed.
        if new_max_id > cursor:
            self._save_cursor(identity, new_max_id)
            self._last_activity = now
            if self._status != "active":
                self._emit_status_change(self._status, "active")
                self._status = "active"
        elif (
            self._status == "active"
            and (now - self._last_activity) > self.idle_threshold
        ):
            self._emit_status_change("active", "idle")
            self._status = "idle"

        # 6. Successful poll -> source healthy. Recover from error state if a
        #    prior poll failed but this one read fine (even with no new rows).
        if self.in_error or self._status == "source_error":
            self.in_error = False
            if self._status == "source_error":
                self._emit_status_change("source_error", "active")
                self._status = "active"
                self._last_activity = now

    def _read_new_rows(self, cursor: int) -> list[sqlite3.Row]:
        uri = f"file:{self.state_db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id, role, content, tool_calls, tool_name
                FROM messages
                WHERE session_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (self.session_id, cursor, self.max_rows_per_poll),
            ).fetchall()
        finally:
            conn.close()
        return list(rows)

    # ------------------------------------------------------------------
    # Error / status-change helpers
    # ------------------------------------------------------------------

    def _record_error(self, now: float | None = None) -> None:
        """Mark the source dead and emit source_error at most once per throttle."""
        if now is None:
            now = self._clock()
        prev = self._status
        self.in_error = True
        self._status = "source_error"
        if (now - self._last_error_emit) >= self.error_throttle:
            self._emit_status_change(prev, "source_error")
            self._last_error_emit = now

    def _emit_status_change(self, from_: str, to: str) -> None:
        try:
            self.engine.append("status_change", {"from": from_, "to": to})
        except Exception:
            log.exception("Failed to emit status_change %s -> %s", from_, to)

    # ------------------------------------------------------------------
    # Row -> structured-summary mapping (raw content never copied)
    # ------------------------------------------------------------------

    def _row_to_events(self, row: sqlite3.Row):
        role = row["role"]
        content = row["content"] or ""
        tool_calls = row["tool_calls"]
        tool_name = row["tool_name"]

        if role == "assistant" and tool_calls:
            for call in self._parse_tool_calls(tool_calls):
                name = (call.get("function") or {}).get("name") or "tool"
                # Tool/function names are source-derived free text — mask them
                # before they reach the feed. A crafted tool name can embed a
                # path or secret; the `tool` field is a typed scalar and would
                # otherwise bypass the note-only mask in mask_summary.
                safe_name = privacy_mask(str(name)) or "tool"
                raw_args = (call.get("function") or {}).get("arguments") or ""
                yield "tool_call", {
                    "tool": safe_name,
                    "args": self._count_args(raw_args),
                    "note": f"invoked {safe_name}",
                }
            return

        if role == "tool":
            yield "tool_result", {
                "tool": privacy_mask(str(tool_name or "tool")) or "tool",
                "status": self._classify_result(content),
                "size": len(content.encode("utf-8", errors="replace")),
            }
            return

        if role in _ROLE_NOTES:
            yield "message", {
                "role": role,
                "chars": len(content),
                "note": _ROLE_NOTES[role],
            }
            return

        # session_meta and any unknown internal role: skip (not host activity).

    @staticmethod
    def _parse_tool_calls(tool_calls_json: str) -> list[dict]:
        try:
            parsed = json.loads(tool_calls_json)
        except Exception:
            return []
        if not isinstance(parsed, list):
            return []
        return [c for c in parsed if isinstance(c, dict)]

    @staticmethod
    def _count_args(raw_args: str) -> int:
        if not raw_args:
            return 0
        try:
            obj = json.loads(raw_args)
        except Exception:
            return 0
        if isinstance(obj, dict):
            return len(obj)
        return 1

    @staticmethod
    def _classify_result(content: str) -> str:
        if not content:
            return "ok"
        head = content[:_CLASSIFY_PARSE_CAP].lstrip()
        if head.startswith("{"):
            try:
                obj = json.loads(head)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                if obj.get("is_error"):
                    return "error"
                if obj.get("error"):
                    return "error"
                ec = obj.get("exit_code")
                if ec not in (None, 0, "0", False):
                    return "error"
                return "ok"
        low = head.lower()
        if low.startswith(("error", "refused", "skipped", "tool '")):
            return "error"
        return "ok"

    # ------------------------------------------------------------------
    # Background worker thread
    # ------------------------------------------------------------------

    def start(self) -> threading.Thread:
        """Start the background poll loop (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="spectator-transcript-poller", daemon=True
        )
        self._thread.start()
        return self._thread

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and join (idempotent)."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self.poll_interval)
