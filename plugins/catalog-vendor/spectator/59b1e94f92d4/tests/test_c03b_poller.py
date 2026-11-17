"""C3b tests — TranscriptPoller (transcript-tail feed producer, P7-safe).

AC requirements:
- test_transcript_fallback_degradation: unreadable/locked/missing source →
  source_error ≤1/min, worker survives, resumes on restore.
- test_poller_emits_structured_summaries: seeded state.db rows → message /
  tool_call / tool_result events; raw content NEVER appears in any summary.
- test_feed_reset_on_rotation: new file_identity resets cursor + feed_reset.
- test_idle_status_change: silence >10s → idle event.
- P7: poller module imports zero duckwork_* / agent_peer symbols.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from spectator.feed.engine import FeedEngine
from spectator.feed.poller import TranscriptPoller

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

class _FakeClock:
    """Injectable monotonic clock for deterministic idle/throttle tests."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _seed_state_db(path: Path, session_id: str, rows: list[dict]) -> Path:
    """Create a minimal Duckwork-style state.db with a messages table."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL NOT NULL
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO messages (id, session_id, role, content, tool_call_id, tool_calls, tool_name, timestamp)
        VALUES (:id, :session_id, :role, :content, :tool_call_id, :tool_calls, :tool_name, :timestamp)
        """,
        [
            {
                "id": r.get("id"),
                "session_id": session_id,
                "role": r["role"],
                "content": r.get("content"),
                "tool_call_id": r.get("tool_call_id"),
                "tool_calls": r.get("tool_calls"),
                "tool_name": r.get("tool_name"),
                "timestamp": r.get("timestamp", 1_000_000.0),
            }
            for r in rows
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def feed_engine(db):
    return FeedEngine(db, session_id="host-session-1")


@pytest.fixture
def state_db(tmp_path):
    """A seeded state.db and its path."""
    path = tmp_path / "state.db"
    return path


def _make_poller(db, feed_engine, state_db_path, clock=None, **kwargs):
    clock = clock or _FakeClock()
    poller = TranscriptPoller(
        feed_engine,
        db,
        state_db_path,
        poll_interval=2.0,
        idle_threshold=10.0,
        error_throttle=60.0,
        max_rows_per_poll=1000,
        clock=clock,
    )
    return poller, clock


def _feed_events(feed_engine):
    return feed_engine.query(since=0, limit=200)["events"]


def _summaries(feed_engine):
    return [json.loads(e["summary"]) for e in _feed_events(feed_engine)]


def _types(feed_engine):
    return [e["type"] for e in _feed_events(feed_engine)]


# ---------------------------------------------------------------------------
# AC: structured summaries, raw content never copied
# ---------------------------------------------------------------------------

class TestPollerEmitsStructuredSummaries:
    def test_message_tool_call_tool_result_emitted(self, db, feed_engine, state_db):
        _seed_state_db(
            state_db,
            "host-session-1",
            [
                {"id": 1, "role": "user", "content": "please run the build"},
                {
                    "id": 2,
                    "role": "assistant",
                    "content": None,
                    "tool_calls": json.dumps([
                        {"function": {"name": "terminal", "arguments": json.dumps({"command": "make build", "timeout": 30})}}
                    ]),
                },
                {"id": 3, "role": "tool", "tool_name": "terminal", "content": json.dumps({"output": "ok", "exit_code": 0})},
            ],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        types = _types(feed_engine)
        assert "message" in types
        assert "tool_call" in types
        assert "tool_result" in types

        summaries = _summaries(feed_engine)
        msg = next(s for s in summaries if "role" in s)
        assert msg["role"] == "user"
        assert msg["chars"] == len("please run the build")

        tc = next(s for s in summaries if "args" in s)
        assert tc["tool"] == "terminal"
        assert tc["args"] == 2

        tr = next(s for s in summaries if "status" in s)
        assert tr["tool"] == "terminal"
        assert tr["status"] == "ok"
        assert tr["size"] == len(json.dumps({"output": "ok", "exit_code": 0}).encode("utf-8"))

    def test_raw_content_never_appears(self, db, feed_engine, state_db):
        raw_message = "SUPERSECRETRAWPATH /home/user/secret token=abc123def456"
        raw_result = json.dumps({"output": "SECRET_OUTPUT_VALUE /etc/passwd", "exit_code": 0})
        _seed_state_db(
            state_db,
            "host-session-1",
            [
                {"id": 1, "role": "user", "content": raw_message},
                {
                    "id": 2,
                    "role": "assistant",
                    "content": None,
                    "tool_calls": json.dumps([
                        {"function": {"name": "write_file", "arguments": json.dumps({"path": "/home/user/secret.txt", "content": "RAW_ARGS_SECRET"})}}
                    ]),
                },
                {"id": 3, "role": "tool", "tool_name": "write_file", "content": raw_result},
            ],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        all_summary_text = json.dumps(_summaries(feed_engine))
        for raw in ["SUPERSECRETRAWPATH", "SECRET_OUTPUT_VALUE", "RAW_ARGS_SECRET",
                    "/home/user/secret", "/etc/passwd", "token=abc123def456"]:
            assert raw not in all_summary_text, f"raw content leaked: {raw!r}"

    def test_tool_result_error_classified(self, db, feed_engine, state_db):
        _seed_state_db(
            state_db,
            "host-session-1",
            [
                {"id": 1, "role": "tool", "tool_name": "terminal", "content": json.dumps({"output": "", "exit_code": 1})},
                {"id": 2, "role": "tool", "tool_name": "web_search", "content": json.dumps({"error": "timeout"})},
            ],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        results = [s for s in _summaries(feed_engine) if "status" in s]
        assert all(s["status"] == "error" for s in results), results

    def test_tool_name_with_embedded_path_or_secret_is_masked(self, db, feed_engine, state_db):
        """Regression (hermaguard HIGH): source-derived tool/function names are
        free text. A crafted tool name embedding a path or secret must not
        reach the feed unmasked through the typed `tool` field."""
        _seed_state_db(
            state_db,
            "host-session-1",
            [
                {
                    "id": 1,
                    "role": "assistant",
                    "content": None,
                    "tool_calls": json.dumps([
                        {"function": {"name": "/home/sahil/secret-project", "arguments": "{}"}}
                    ]),
                },
                {"id": 2, "role": "tool", "tool_name": "/etc/passwd-leak", "content": "{}"},
            ],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        all_text = json.dumps(_summaries(feed_engine))
        assert "/home/sahil/secret-project" not in all_text, "tool_call name leaked a path"
        assert "/etc/passwd-leak" not in all_text, "tool_result name leaked a path"

    def test_plain_tool_name_survives_masking(self, db, feed_engine, state_db):
        """Normal tool names (terminal, read_file, web_search) are not over-redacted."""
        _seed_state_db(
            state_db,
            "host-session-1",
            [
                {
                    "id": 1,
                    "role": "assistant",
                    "content": None,
                    "tool_calls": json.dumps([
                        {"function": {"name": "read_file", "arguments": json.dumps({"path": "x"})}}
                    ]),
                },
            ],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        tc = next(s for s in _summaries(feed_engine) if "args" in s)
        assert tc["tool"] == "read_file"

    def test_cursor_advances_and_no_redelivery(self, db, feed_engine, state_db):
        _seed_state_db(
            state_db,
            "host-session-1",
            [{"id": 1, "role": "user", "content": "hello"}],
        )
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()
        assert len(_feed_events(feed_engine)) == 1

        # Append a new row; only the NEW row is emitted on the next poll.
        conn = sqlite3.connect(str(state_db))
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (2, 'host-session-1', 'user', 'second', 1000001.0)"
        )
        conn.commit()
        conn.close()

        poller.poll_once()
        assert len(_feed_events(feed_engine)) == 2


# ---------------------------------------------------------------------------
# AC: degradation — unreadable/locked/missing, throttle ≤1/min, resume
# ---------------------------------------------------------------------------

class TestTranscriptFallbackDegradation:
    def test_missing_source_emits_error_and_resumes(self, db, feed_engine, state_db):
        # state_db does not exist yet.
        assert not state_db.exists()
        poller, clock = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        assert poller.source_status == "error"
        sc = [json.loads(e["summary"]) for e in _feed_events(feed_engine) if e["type"] == "status_change"]
        assert any(s.get("to") == "source_error" for s in sc)

        # Restore: create the file. Next poll resumes and emits message events.
        _seed_state_db(state_db, "host-session-1", [{"id": 1, "role": "user", "content": "back online"}])
        clock.advance(61.0)
        poller.poll_once()

        assert poller.source_status == "transcript"
        assert "message" in _types(feed_engine)
        sc = [json.loads(e["summary"]) for e in _feed_events(feed_engine) if e["type"] == "status_change"]
        assert any(s.get("to") == "active" for s in sc)

    def test_source_error_throttled_to_one_per_minute(self, db, feed_engine, state_db):
        assert not state_db.exists()
        poller, clock = _make_poller(db, feed_engine, state_db)

        # Three rapid failed polls within the throttle window.
        poller.poll_once()
        clock.advance(1.0)
        poller.poll_once()
        clock.advance(1.0)
        poller.poll_once()

        error_events = [e for e in _feed_events(feed_engine) if e["type"] == "status_change"
                        and json.loads(e["summary"]).get("to") == "source_error"]
        assert len(error_events) == 1, f"expected 1 source_error, got {len(error_events)}"

        # After the throttle window elapses, another error may emit.
        clock.advance(60.0)
        poller.poll_once()
        error_events = [e for e in _feed_events(feed_engine) if e["type"] == "status_change"
                        and json.loads(e["summary"]).get("to") == "source_error"]
        assert len(error_events) == 2

    def test_worker_survives_and_never_raises(self, db, feed_engine, state_db):
        """poll_once never raises even with an unreadable/missing source."""
        poller, _ = _make_poller(db, feed_engine, state_db)
        for _ in range(5):
            poller.poll_once()  # must not raise

    def test_source_status_unconfigured_when_no_session_id(self, db, feed_engine, state_db):
        """Regression: with no host session identity the poller tails nothing,
        so it must not misreport the source as 'transcript'."""
        engine_no_session = FeedEngine(db, session_id="")
        poller, _ = _make_poller(db, engine_no_session, state_db)
        poller.poll_once()
        assert poller.source_status == "unconfigured"


# ---------------------------------------------------------------------------
# AC: feed_reset on file_identity rotation
# ---------------------------------------------------------------------------

class TestFeedResetOnRotation:
    def test_new_file_identity_resets_cursor(self, db, feed_engine, state_db):
        _seed_state_db(state_db, "host-session-1", [{"id": 1, "role": "user", "content": "first file"}])
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()
        assert len(_feed_events(feed_engine)) == 1

        # Rotate: replace state.db with a NEW file (new inode) seeded with a
        # DIFFERENT row id. New file_identity -> cursor reset + feed_reset.
        new_path = state_db.with_name("state_rotated.db")
        _seed_state_db(new_path, "host-session-1", [{"id": 100, "role": "user", "content": "rotated file"}])
        new_path.replace(state_db)

        poller.poll_once()

        sc = [json.loads(e["summary"]) for e in _feed_events(feed_engine) if e["type"] == "status_change"]
        assert any(s.get("to") == "feed_reset" for s in sc), "feed_reset event not emitted on rotation"
        # The rotated row (id 100) is emitted after reset.
        assert "message" in _types(feed_engine)

    def test_feed_reset_event_payload(self, db, feed_engine, state_db):
        _seed_state_db(state_db, "host-session-1", [{"id": 1, "role": "user", "content": "a"}])
        poller, _ = _make_poller(db, feed_engine, state_db)
        poller.poll_once()

        new_path = state_db.with_name("state_rotated2.db")
        _seed_state_db(new_path, "host-session-1", [{"id": 1, "role": "user", "content": "b"}])
        new_path.replace(state_db)
        poller.poll_once()

        reset_events = [json.loads(e["summary"]) for e in _feed_events(feed_engine)
                        if e["type"] == "status_change" and json.loads(e["summary"]).get("to") == "feed_reset"]
        assert reset_events, "feed_reset event not emitted on rotation"
        assert reset_events[0]["from"] in ("active", "idle", "source_error")


# ---------------------------------------------------------------------------
# AC: idle status change after >10s silence
# ---------------------------------------------------------------------------

class TestIdleStatusChange:
    def test_idle_after_silence(self, db, feed_engine, state_db):
        _seed_state_db(state_db, "host-session-1", [{"id": 1, "role": "user", "content": "only message"}])
        poller, clock = _make_poller(db, feed_engine, state_db)
        poller.poll_once()  # consumes the row, last_activity = now

        # No new rows, but silence < threshold -> no idle yet.
        clock.advance(5.0)
        poller.poll_once()
        assert "idle" not in [json.loads(e["summary"]).get("to") for e in _feed_events(feed_engine) if e["type"] == "status_change"]

        # Silence > threshold -> idle emitted exactly once.
        clock.advance(6.0)
        poller.poll_once()
        idle_events = [e for e in _feed_events(feed_engine) if e["type"] == "status_change"
                       and json.loads(e["summary"]).get("to") == "idle"]
        assert len(idle_events) == 1

        # Continued silence does not re-emit idle (status already idle).
        clock.advance(60.0)
        poller.poll_once()
        idle_events = [e for e in _feed_events(feed_engine) if e["type"] == "status_change"
                       and json.loads(e["summary"]).get("to") == "idle"]
        assert len(idle_events) == 1


# ---------------------------------------------------------------------------
# AC: P7 — zero duckwork_* / agent_peer imports
# ---------------------------------------------------------------------------

class TestP7NoDuckworkImports:
    def test_poller_imports_zero_duckwork_symbols(self):
        import importlib.util

        poller_path = Path(__file__).resolve().parent.parent / "src" / "spectator" / "feed" / "poller.py"
        src = poller_path.read_text(encoding="utf-8")

        import_lines = [ln for ln in src.splitlines() if ln.lstrip().startswith(("import ", "from "))]
        for ln in import_lines:
            assert "duckwork_" not in ln, f"duckwork_ import in poller: {ln!r}"
            assert "agent_peer" not in ln, f"agent_peer import in poller: {ln!r}"
            assert "duckwork_agent" not in ln, f"duckwork_agent import in poller: {ln!r}"

        # Also assert the module imports cleanly without any duckwork package.
        poller = importlib.import_module("spectator.feed.poller")
        assert poller is not None


# ---------------------------------------------------------------------------
# AC: cross-thread connection safety (hermaguard HIGH)
# ---------------------------------------------------------------------------

class TestCrossThreadConnectionSafety:
    def test_background_writer_and_reader_do_not_corrupt_shared_connection(self, db):
        """Regression (hermaguard HIGH): the poller writes from a background
        thread while request threads read. A single shared sqlite3 connection
        across threads corrupts transaction state. Each thread must get its own
        connection; concurrent write_txn + read must not raise."""
        import threading

        stop = threading.Event()
        errors: list[tuple] = []

        def writer():
            while not stop.is_set():
                try:
                    with db.write_txn() as cur:
                        cur.execute(
                            "INSERT INTO events (session_id, type, summary, timestamp) "
                            "VALUES (?, ?, ?, ?)",
                            ("s", "message", '{"role":"user","chars":1,"note":"x"}',
                             "2026-01-01T00:00:00.000000+00:00"),
                        )
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(("writer", type(exc).__name__, str(exc)[:120]))

        def reader():
            while not stop.is_set():
                try:
                    with db.conn as conn:
                        conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ?", ("s",)).fetchone()
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(("reader", type(exc).__name__, str(exc)[:120]))

        t1 = threading.Thread(target=writer, daemon=True)
        t2 = threading.Thread(target=reader, daemon=True)
        t1.start()
        t2.start()
        import time as _time
        _time.sleep(1.0)
        stop.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"cross-thread connection corruption: {errors}"
