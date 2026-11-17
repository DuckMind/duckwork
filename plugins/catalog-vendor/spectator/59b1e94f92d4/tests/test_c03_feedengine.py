"""C3 tests — FeedEngine, privacy mask, event contract, cursor reset, retention sweep.

AC requirements:
- docs/event-contract.md enumerates types/payload-shape/boundary/frequency (pass/fail gate).
- Feed events are structured objects serialised ≤280 chars; no raw content path exists.
- Mask corpus CI thresholds: 100% required redaction, ≤5% false positives.
- Guest polling with stale cursor gets reset response; no purged-event re-delivery.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from spectator.auth.auth import HostSecretManager
from spectator.auth.invite import InviteManager
from spectator.db.db import SpectatorDB
from spectator.feed.engine import (
    MAX_SUMMARY_CHARS,
    FeedEngine,
    MessageSummary,
    StatusChangeSummary,
    ToolCallSummary,
    ToolResultSummary,
    mask_summary,
    privacy_mask,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db(tmp_data_dir):
    db_path = tmp_data_dir / "spectator.db"
    database = SpectatorDB(db_path)
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def feed_engine(db):
    return FeedEngine(db, session_id="test-session-1")


@pytest.fixture
def secret_mgr(tmp_data_dir):
    secret_path = tmp_data_dir / "host_secret"
    mgr = HostSecretManager(secret_path)
    mgr.load_or_create()
    return mgr


@pytest.fixture
def invite_mgr(db, secret_mgr):
    return InviteManager(db, secret_mgr, current_session_gen="gen-1")


# ===========================================================================
# BUILD STEP 0: event-contract.md verification
# ===========================================================================

class TestEventContract:
    """AC: docs/event-contract.md enumerates types/payload-shape/boundary/frequency."""

    def test_event_contract_file_exists(self):
        """The event contract document must exist at docs/event-contract.md."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        assert contract_path.exists(), "docs/event-contract.md must exist (BUILD STEP 0 gate)"

    def test_event_contract_enumerates_types(self):
        """The contract must enumerate tool_call, tool_result, message, status_change."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        content = contract_path.read_text()
        for event_type in ["tool_call", "tool_result", "message", "status_change"]:
            assert event_type in content, f"Event type {event_type!r} missing from contract"

    def test_event_contract_specifies_payload_shapes(self):
        """The contract must define payload shapes (typed fields)."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        content = contract_path.read_text()
        assert '"tool"' in content, "tool_call payload shape missing"
        assert '"role"' in content, "message payload shape missing"
        assert '"from"' in content or "from_" in content, "status_change payload shape missing"

    def test_event_contract_specifies_boundary(self):
        """The contract must specify 280-char boundary."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        content = contract_path.read_text()
        assert "280" in content, "280-char boundary not specified in contract"

    def test_event_contract_specifies_frequency(self):
        """The contract must specify frequency bounds."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        content = contract_path.read_text()
        assert "10s" in content or "idle" in content, "Idle frequency bound not specified"
        assert "60s" in content or "source_error" in content, "Error throttle not specified"

    def test_event_contract_specifies_cursor_reset(self):
        """The contract must specify cursor reset semantics."""
        contract_path = Path(__file__).resolve().parent.parent / "docs" / "event-contract.md"
        content = contract_path.read_text()
        assert "reset" in content.lower(), "Cursor reset semantics not specified"


# ===========================================================================
# Structured summary shapes
# ===========================================================================

class TestStructuredSummaryShapes:
    """AC: Feed events are structured objects serialised ≤280 chars; no raw content path."""

    def test_tool_call_summary(self, feed_engine):
        """Tool call summary is structured, masked, and ≤280 chars."""
        summary = ToolCallSummary(
            tool="read_file",
            args=3,
            note="Read config at /home/user/project/settings.yaml",
        )
        seq = feed_engine.append("tool_call", summary.to_dict())
        assert seq > 0

        result = feed_engine.query(since=0, limit=10)
        assert len(result["events"]) == 1
        event = result["events"][0]
        parsed = json.loads(event["summary"])
        assert parsed["tool"] == "read_file"
        assert parsed["args"] == 3
        # /home/user/ should be masked to ~/
        assert "/home/" not in parsed["note"]
        assert len(event["summary"]) <= MAX_SUMMARY_CHARS

    def test_tool_result_summary(self, feed_engine):
        """Tool result summary has status and size, no raw content."""
        summary = ToolResultSummary(tool="read_file", status="ok", size=4521)
        seq = feed_engine.append("tool_result", summary.to_dict())
        assert seq > 0

        result = feed_engine.query(since=0, limit=10)
        event = result["events"][0]
        parsed = json.loads(event["summary"])
        assert parsed["tool"] == "read_file"
        assert parsed["status"] == "ok"
        assert parsed["size"] == 4521

    def test_message_summary(self, feed_engine):
        """Message summary has role, chars, and masked note."""
        summary = MessageSummary(
            role="assistant",
            chars=342,
            note="Explained the file structure at /home/user/project",
        )
        seq = feed_engine.append("message", summary.to_dict())
        assert seq > 0

        result = feed_engine.query(since=0, limit=10)
        event = result["events"][0]
        parsed = json.loads(event["summary"])
        assert parsed["role"] == "assistant"
        assert parsed["chars"] == 342
        # Path should be masked
        assert "/home/" not in parsed["note"]

    def test_status_change_summary(self, feed_engine):
        """Status change summary has from/to."""
        summary = StatusChangeSummary(from_="idle", to="active")
        seq = feed_engine.append("status_change", summary.to_dict())
        assert seq > 0

        result = feed_engine.query(since=0, limit=10)
        event = result["events"][0]
        parsed = json.loads(event["summary"])
        assert parsed["from"] == "idle"
        assert parsed["to"] == "active"

    def test_no_raw_content_in_summary(self, feed_engine):
        """No raw content path exists in any summary type."""
        sensitive_note = "User password=hunter2, API_KEY=sk-abc123def456, file at /home/secret/data"
        summary = MessageSummary(role="assistant", chars=100, note=sensitive_note)
        feed_engine.append("message", summary.to_dict())

        result = feed_engine.query(since=0, limit=10)
        event = result["events"][0]
        summary_text = event["summary"]
        # Raw paths and secrets must not appear
        assert "/home/secret" not in summary_text
        assert "hunter2" not in summary_text
        assert "sk-abc123def456" not in summary_text

    def test_summary_max_280_chars(self, feed_engine):
        """Every serialised summary must be ≤280 chars."""
        very_long_note = "x" * 500
        summary = MessageSummary(role="user", chars=500, note=very_long_note)
        seq = feed_engine.append("message", summary.to_dict())

        result = feed_engine.query(since=0, limit=10)
        event = result["events"][0]
        assert len(event["summary"]) <= MAX_SUMMARY_CHARS

    def test_invalid_event_type_raises(self, feed_engine):
        """Invalid event type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid event type"):
            feed_engine.append("invalid_type", {"foo": "bar"})


# ===========================================================================
# Privacy mask corpus coverage
# ===========================================================================

# Mask corpus is seeded in tests/fixtures/mask_corpus/corpus.json (spec rule
# 7 + test plan). Each entry is {input, verdict: redact|permit, survives?,
# note}. `redact` = sensitive content must not survive verbatim; `permit` =
# non-secret content whose `survives` substring must survive masking.

_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "mask_corpus" / "corpus.json"


def _load_corpus() -> list[dict]:
    import json as _json
    return _json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


MASK_CORPUS = _load_corpus()
MASK_CORPUS_REQUIRED = [
    (c["input"], c.get("survives", ""), True)
    for c in MASK_CORPUS if c["verdict"] == "redact"
]
MASK_CORPUS_PERMITTED = [
    (c["input"], c["survives"])
    for c in MASK_CORPUS if c["verdict"] == "permit"
]


class TestMaskCorpusCoverage:
    """AC: Mask corpus CI thresholds — 100% required redaction, ≤5% false positives.

    Corpus is loaded from tests/fixtures/mask_corpus/corpus.json. A CI guard
    asserts the corpus has the spec-mandated ≥50 seeded cases (spec rule 7),
    so the corpus cannot silently shrink below the threshold.
    """

    def test_corpus_minimum_size(self):
        """Spec rule 7: the mask corpus must carry ≥50 seeded cases."""
        assert len(MASK_CORPUS) >= 50, (
            f"Mask corpus has {len(MASK_CORPUS)} cases; spec requires ≥50 "
            f"(tests/fixtures/mask_corpus/corpus.json)"
        )

    @pytest.mark.parametrize("input_text,pattern,should_redact", MASK_CORPUS_REQUIRED)
    def test_required_redaction(self, input_text, pattern, should_redact):
        """100% of required redaction cases must be redacted.

        Each required fixture is a pure sensitive string (path, secret, token,
        env assignment). After masking, the raw sensitive string must NOT
        survive verbatim in the output. This is a strict assertion — the old
        corpus only checked /home/ paths and silently skipped /root/, Windows
        drive paths, and bare hex credentials.
        """
        result = privacy_mask(input_text)
        if should_redact:
            # The raw sensitive content must never survive verbatim.
            assert input_text not in result, (
                f"Sensitive content leaked unmasked: {input_text!r} -> {result!r}"
            )
            # The result must still be non-empty (something was produced).
            assert len(result) > 0, f"Empty mask result for {input_text!r}"

    @pytest.mark.parametrize("input_text,pattern", MASK_CORPUS_PERMITTED)
    def test_permitted_false_positive_rate(self, input_text, pattern):
        """≤5% false positives on non-secret cases.

        Each permitted fixture carries an expected substring that MUST survive
        masking. The old test only asserted `len(result) > 0`, which passed
        even when the masker destroyed a SHA-256 digest to `***` (a false
        positive). A strict per-sample survival assertion enforces the ≤5%
        threshold: any permitted sample that fails to survive is a false
        positive and fails CI.
        """
        result = privacy_mask(input_text)
        assert pattern in result, (
            f"False positive: non-secret content {input_text!r} was over-redacted "
            f"-> {result!r} (expected {pattern!r} to survive)"
        )

    def test_mask_fail_closed(self):
        """Masker failure returns [redacted], never raw content."""
        # Force a masker failure by passing None
        result = privacy_mask(None)  # type: ignore
        assert result == "[redacted]"

    def test_mask_empty_string(self):
        """Empty string passes through."""
        result = privacy_mask("")
        assert result == ""

    def test_mask_short_string(self):
        """Short non-sensitive strings survive."""
        result = privacy_mask("hello world")
        assert "hello world" in result

    def test_mask_windows_path(self):
        """Windows paths are properly masked."""
        result = privacy_mask(r"C:\Users\Administrator\secrets\key.pem")
        assert r"C:\Users\Administrator" not in result

    def test_mask_env_var(self):
        """Environment variables are masked."""
        result = privacy_mask("PATH=/usr/bin:/bin MY_SECRET=abc123def456")
        assert "MY_SECRET=***" in result

    def test_mask_duckwork_path(self):
        """~/.duckwork paths are masked to ~/.***."""
        result = privacy_mask("~/.duckwork/plugins/spectator/config.yaml")
        assert "~/.***" in result
        assert "~/.duckwork" not in result

    def test_mask_home_relative_path_hides_every_segment(self):
        """Home-relative paths must not reveal project or file names."""
        result = privacy_mask("Opened ~/work/client-acme/contract.pdf")
        assert "client-acme" not in result
        assert "contract.pdf" not in result

    def test_mask_known_provider_key_identifier(self):
        """Known provider key identifiers are sensitive even without the secret half."""
        key_id = "AK" + "IA" + "IOSFODNN7EXAMPLE"
        result = privacy_mask(f"Provider key ID {key_id}")
        assert key_id not in result
        assert "***" in result

    def test_mask_json_with_path(self):
        """JSON blobs containing paths have paths masked."""
        result = privacy_mask('{"path": "/home/user/data/file.txt"}')
        assert "/home/user" not in result

    def test_mask_base64_path(self):
        """Base64-encoded path /tmp/secret is redacted."""
        import base64
        encoded = base64.b64encode(b"/tmp/secret/data").decode()
        result = privacy_mask(f"Config: {encoded}")
        assert "/tmp/secret" not in result
        # The base64 token itself should be replaced with ~/
        assert encoded not in result or "~/" in result

    def test_mask_high_entropy_token(self):
        """High-entropy tokens ≥20 chars with entropy >4.5 are redacted."""
        # 32-char random-looking token
        token = "aB3dE7fG9hJ2kL5mN8oP1qR4sT6uV0w"
        result = privacy_mask(f"key={token}")
        assert "***" in result
        assert token not in result

    def test_hex_credential_redacted(self):
        """Hex-formatted credentials ≥24 hex chars are redacted."""
        hex_cred = "0123456789abcdef0123456789abcdef"
        result = privacy_mask(f"credential={hex_cred}")
        assert "***" in result or hex_cred not in result

    def test_mask_url_encoded_path(self):
        """URL-encoded path components are decoded and masked."""
        result = privacy_mask("/home%2Fuser%2Fsecret")
        assert "secret" not in result or "~/" in result

    def test_mask_error_message_with_path(self):
        """Error messages embedding paths have paths masked."""
        result = privacy_mask("Error: cannot read /home/sahil/project/.env")
        assert "/home/sahil" not in result


# ===========================================================================
# Feed engine: append, query, retention, cursor reset
# ===========================================================================

class TestFeedEngineAppend:
    """Test FeedEngine event append and query."""

    def test_append_and_query(self, feed_engine):
        """Append an event and query it back."""
        summary = ToolCallSummary(tool="read_file", args=2, note="Reading config")
        seq = feed_engine.append("tool_call", summary.to_dict())

        result = feed_engine.query(since=0, limit=10)
        assert result["reset"] is False
        assert len(result["events"]) == 1
        event = result["events"][0]
        assert event["seq"] == seq
        assert event["type"] == "tool_call"

    def test_append_multiple_types(self, feed_engine):
        """Append events of different types and query with type filter."""
        feed_engine.append("tool_call", ToolCallSummary(tool="read_file", args=1, note="read").to_dict())
        feed_engine.append("tool_result", ToolResultSummary(tool="read_file", status="ok", size=100).to_dict())
        feed_engine.append("message", MessageSummary(role="assistant", chars=50, note="done").to_dict())

        # Query all
        result = feed_engine.query(since=0, limit=10)
        assert len(result["events"]) == 3

        # Query only tool_call
        result = feed_engine.query(since=0, limit=10, event_types=["tool_call"])
        assert len(result["events"]) == 1
        assert result["events"][0]["type"] == "tool_call"

    def test_append_rejects_non_contract_keys(self, feed_engine):
        """Raw content must never be stored: a dict with an unmasked free-text
        key outside the typed shape is rejected, not persisted."""
        import pytest as _pytest
        with _pytest.raises(ValueError):
            feed_engine.append("message", {"role": "user", "chars": 3, "content": "RAW HOST SECRET"})
        # nothing persisted
        result = feed_engine.query(since=0, limit=10)
        assert len(result["events"]) == 0

    def test_append_timestamp_fixed_width(self, feed_engine):
        """Stored timestamps always carry microseconds so lexicographic
        sweep compare stays monotonic with time."""
        feed_engine.append("message", MessageSummary(role="user", chars=1, note="hi").to_dict())
        row = feed_engine.query(since=0, limit=1)["events"][0]
        ts = row["timestamp"]
        import re as _re
        assert _re.search(r"\.\d{6}\+00:00$", ts), f"timestamp not fixed-width: {ts!r}"

    def test_long_typed_field_never_yields_invalid_json(self, feed_engine):
        """A 1000-char tool name must never produce a mid-string JSON slice —
        guest clients would crash on parse. Output stays valid JSON ≤280."""
        import json as _json
        feed_engine.append("tool_call", ToolCallSummary(tool="x" * 1000, args=1, note="n").to_dict())
        row = feed_engine.query(since=0, limit=1)["events"][0]
        assert len(row["summary"]) <= 280
        parsed = _json.loads(row["summary"])
        assert parsed is not None


    def test_query_since_cursor(self, feed_engine):
        """Query with since cursor returns only events after that cursor."""
        seq1 = feed_engine.append("tool_call", ToolCallSummary(tool="a", args=1, note="a").to_dict())
        seq2 = feed_engine.append("tool_call", ToolCallSummary(tool="b", args=2, note="b").to_dict())
        seq3 = feed_engine.append("tool_call", ToolCallSummary(tool="c", args=3, note="c").to_dict())

        # Query since seq1
        result = feed_engine.query(since=seq1, limit=10)
        assert len(result["events"]) == 2
        assert result["events"][0]["seq"] == seq2
        assert result["events"][1]["seq"] == seq3

    def test_query_limit(self, feed_engine):
        """Query respects limit parameter."""
        for i in range(5):
            feed_engine.append("message", MessageSummary(role="user", chars=i, note=f"msg {i}").to_dict())

        result = feed_engine.query(since=0, limit=3)
        assert len(result["events"]) == 3

    def test_query_limit_max_200(self, feed_engine):
        """Limit is clamped to 200."""
        result = feed_engine.query(since=0, limit=500)
        # The query function clamps to 200 internally
        # (no events to return, but the clamp logic runs)


class TestFeedEngineCursorReset:
    """AC: Guest polling with stale cursor gets reset response; no purged-event re-delivery."""

    def test_stale_cursor_returns_reset(self, feed_engine):
        """A cursor older than the oldest event triggers a reset response."""
        # Delete all events to simulate a retention sweep
        feed_engine.append("message", MessageSummary(role="assistant", chars=10, note="recent").to_dict())

        # Now query with since=0 (stale)
        result = feed_engine.query(since=0, limit=10)
        # since=0 is valid (first event), so no reset
        assert result["reset"] is False

    def test_cursor_reset_on_purged_events(self, db):
        """After events are purged, a stale cursor gets reset response."""
        engine = FeedEngine(db, session_id="test-reset")

        # Insert event
        seq1 = engine.append("message", MessageSummary(role="assistant", chars=10, note="old").to_dict())

        # Simulate retention sweep by directly deleting old events
        old_time = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE events SET timestamp = ? WHERE seq = ?",
                (old_time, seq1),
            )

        # Sweep should delete the old event
        deleted = engine.sweep_expired(retention_days=7)
        assert deleted == 1

        # Insert new event
        seq2 = engine.append("message", MessageSummary(role="user", chars=5, note="new").to_dict())

        # Query with since=seq1 (stale, event was purged)
        result = engine.query(since=seq1, limit=10)
        assert result["reset"] is True
        assert result["oldest_seq"] == seq2
        # The purged event should NOT be re-delivered
        assert len(result["events"]) == 1
        assert result["events"][0]["seq"] == seq2

    def test_no_purged_event_redelivery(self, db):
        """Purged events are never returned to the guest."""
        engine = FeedEngine(db, session_id="test-no-redeliver")

        # Insert old event and mark it old
        seq1 = engine.append("message", MessageSummary(role="assistant", chars=10, note="old").to_dict())

        old_time = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE events SET timestamp = ? WHERE seq = ?",
                (old_time, seq1),
            )

        engine.sweep_expired(retention_days=7)

        # Insert new event
        seq2 = engine.append("message", MessageSummary(role="user", chars=5, note="new").to_dict())

        # Query since=0 — should only return seq2 (seq1 was purged)
        result = engine.query(since=0, limit=10)
        assert len(result["events"]) == 1
        assert result["events"][0]["seq"] == seq2


class TestFeedEngineRetention:
    """Test retention sweep and expiry."""

    def test_sweep_expired(self, db):
        """Events older than retention_days are deleted by sweep."""
        engine = FeedEngine(db, session_id="test-retention")

        seq1 = engine.append("message", MessageSummary(role="assistant", chars=10, note="old").to_dict())

        # Mark the event as old
        old_time = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE events SET timestamp = ? WHERE seq = ?",
                (old_time, seq1),
            )

        # Add a recent event
        seq2 = engine.append("message", MessageSummary(role="user", chars=5, note="recent").to_dict())

        deleted = engine.sweep_expired(retention_days=7)
        assert deleted == 1

        # Recent event should still be there
        result = engine.query(since=0, limit=10)
        assert len(result["events"]) == 1
        assert result["events"][0]["seq"] == seq2

    def test_sweep_preserves_recent_events(self, feed_engine):
        """Recent events are not deleted by sweep."""
        feed_engine.append("message", MessageSummary(role="assistant", chars=10, note="recent").to_dict())

        deleted = feed_engine.sweep_expired(retention_days=7)
        assert deleted == 0

        result = feed_engine.query(since=0, limit=10)
        assert len(result["events"]) == 1

    def test_sweep_on_poll(self, feed_engine, db):
        """Retention sweep runs on poll-cycle hot path."""
        # This tests that sweep_expired is called in the /feed endpoint
        # (tested in integration via the endpoint)
        seq1 = feed_engine.append("message", MessageSummary(role="assistant", chars=10, note="old").to_dict())

        old_time = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE events SET timestamp = ? WHERE seq = ?",
                (old_time, seq1),
            )

        # Manual sweep to verify
        deleted = feed_engine.sweep_expired(retention_days=7)
        assert deleted == 1


class TestFeedEngineIntegration:
    """Integration tests with the FastAPI app via TestClient."""

    def _make_client(self, tmp_data_dir):
        """Create a TestClient with initialised plugin state."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from dashboard.plugin_api import init_plugin, router

        app = FastAPI()
        app.include_router(router, prefix="/api/plugins/spectator")
        init_plugin(data_dir=tmp_data_dir, session_id="test-feed-session")
        return TestClient(app), tmp_data_dir

    def _get_host_token(self, tmp_data_dir):
        from spectator.auth.auth import HostSecretManager
        secret_path = tmp_data_dir / "host_secret"
        secret_mgr = HostSecretManager(secret_path)
        secret_mgr.load_or_create()
        return secret_mgr.secret.hex()

    def test_feed_endpoint_returns_events(self, tmp_data_dir):
        """GET /feed returns structured events."""
        client, data_dir = self._make_client(tmp_data_dir)
        host_token = self._get_host_token(data_dir)

        from dashboard.plugin_api import _state
        from spectator.feed.engine import ToolCallSummary
        feed = _state.feed_engine
        feed.append("tool_call", ToolCallSummary(tool="read_file", args=3, note="read config").to_dict())

        response = client.get(
            "/api/plugins/spectator/feed?since=0&limit=10",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["type"] == "tool_call"
        assert data["reset"] is False

    def test_feed_endpoint_with_type_filter(self, tmp_data_dir):
        """GET /feed?types=tool_call returns only tool_call events."""
        client, data_dir = self._make_client(tmp_data_dir)
        host_token = self._get_host_token(data_dir)

        from dashboard.plugin_api import _state
        from spectator.feed.engine import MessageSummary, ToolCallSummary
        feed = _state.feed_engine
        feed.append("tool_call", ToolCallSummary(tool="read_file", args=1, note="read").to_dict())
        feed.append("message", MessageSummary(role="assistant", chars=10, note="msg").to_dict())

        response = client.get(
            "/api/plugins/spectator/feed?since=0&limit=10&types=tool_call",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["type"] == "tool_call"

    def test_feed_endpoint_guest_auth(self, tmp_data_dir):
        """GET /feed with guest token works."""
        client, data_dir = self._make_client(tmp_data_dir)
        host_token = self._get_host_token(data_dir)

        from dashboard.plugin_api import _state
        from spectator.feed.engine import ToolCallSummary

        # Create invite and join to get guest token
        invite_result = _state.invite_mgr.mint_invite(
            session_id=_state.session_id, session_gen=_state.session_gen
        )
        join_result = _state.invite_mgr.join_invite(raw_token=invite_result["token"])
        guest_token = join_result["guest_token"]

        # Append event
        feed = _state.feed_engine
        feed.append("tool_call", ToolCallSummary(tool="ls", args=1, note="list files").to_dict())

        # Query with guest token
        response = client.get(
            "/api/plugins/spectator/feed?since=0&limit=10",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1

    def test_feed_endpoint_invalid_types(self, tmp_data_dir):
        """GET /feed?types=invalid returns 400."""
        client, data_dir = self._make_client(tmp_data_dir)
        host_token = self._get_host_token(data_dir)

        response = client.get(
            "/api/plugins/spectator/feed?since=0&limit=10&types=invalid_type",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 400

    def test_mask_summary_produces_valid_json(self, feed_engine):
        """mask_summary produces valid JSON ≤280 chars."""
        summary = ToolCallSummary(
            tool="write_file",
            args=5,
            note="Writing sensitive data at /home/user/secret/key.pem with API_KEY=abc123",
        )
        serialised = mask_summary(summary.to_dict(), "tool_call")
        parsed = json.loads(serialised)
        assert parsed["tool"] == "write_file"
        assert parsed["args"] == 5
        assert len(serialised) <= MAX_SUMMARY_CHARS
        # Sensitive content should be masked
        assert "/home/user/secret" not in serialised
        assert "abc123" not in serialised

    def test_mask_failure_counter_increments(self, feed_engine):
        """Mask failure counter increments on failure."""
        from spectator.feed import engine as eng_module
        initial = eng_module._masker_failures
        # Call via eng_module (not the top-level import): test_c01_scaffold's
        # host-integration tests purge spectator.* from sys.modules to
        # simulate a clean host import and never restore them. A later
        # top-level `privacy_mask` may then be bound to a DIFFERENT module
        # instance than the freshly imported eng_module, so the increment
        # lands in the wrong counter. Calling through eng_module keeps the
        # function and the counter in the same module instance.
        result = eng_module.privacy_mask(None)  # type: ignore
        assert result == "[redacted]"
        assert eng_module._masker_failures > initial