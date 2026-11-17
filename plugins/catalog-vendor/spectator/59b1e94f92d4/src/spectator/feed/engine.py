"""FeedEngine — structured event summaries and privacy masking.

Produces append-only event summaries from host session activity for guest
consumption. Each summary is a structured object (typed scalars + masked note)
serialised to ≤280 chars. Raw content is NEVER copied.

BUILD STEP 0 gate: docs/event-contract.md verified.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spectator.db.db import SpectatorDB

log = logging.getLogger("spectator.feed")

# ---------------------------------------------------------------------------
# Structured summary types
# ---------------------------------------------------------------------------

@dataclass
class ToolCallSummary:
    """Structured summary for a tool_call event."""
    tool: str
    args: int
    note: str  # Already privacy-masked

    def to_dict(self) -> dict:
        return {"tool": self.tool[:64], "args": self.args, "note": self.note}


@dataclass
class ToolResultSummary:
    """Structured summary for a tool_result event."""
    tool: str
    status: str  # "ok" | "error"
    size: int

    def to_dict(self) -> dict:
        return {"tool": self.tool[:64], "status": self.status, "size": self.size}


@dataclass
class MessageSummary:
    """Structured summary for a message event."""
    role: str  # "assistant" | "user" | "system"
    chars: int
    note: str  # Already privacy-masked

    def to_dict(self) -> dict:
        return {"role": self.role, "chars": self.chars, "note": self.note}


@dataclass
class StatusChangeSummary:
    """Structured summary for a status_change event."""
    from_: str  # 'from' is a Python keyword
    to: str

    def to_dict(self) -> dict:
        return {"from": self.from_, "to": self.to}


# Maximum serialised length for a summary JSON string
MAX_SUMMARY_CHARS = 280

# ---------------------------------------------------------------------------
# Privacy mask
# ---------------------------------------------------------------------------

# Regex patterns for the privacy mask, applied in order.

# 1. Base64-encoded path detection (run BEFORE path redaction)
# Decode unspaced base64 tokens of length 8-200; if decoded output matches
# a path pattern, redact the whole token.
_BASE64_TOKEN_RE = re.compile(r'[A-Za-z0-9+/=]{8,200}')

# 2a. Absolute POSIX paths: home, root, macOS Users, and other sensitive roots → ~/
_POSIX_ABS_PATH_RE = re.compile(r'/(?:home|Users|root|etc|var|tmp|opt|srv|usr/local|usr|boot|mnt)/[^\s]*')

# 2b. Windows paths: C:\Users\user, D:\work\... → ~
_WINDOWS_PATH_RE = re.compile(r'(?<![A-Za-z0-9/])[A-Za-z]:[\\/][^\s]*')

# 2c. file:/// URLs
_FILE_URL_RE = re.compile(r'file:///[A-Za-z]:[^\s]*')

# 2d. ~/.duckwork paths
_DUCKWORK_OPT_RE = re.compile(r'~/\.duckwork/[^\s]*')

# 2e. Generic home-relative paths. Hide the complete path, not only its
# first segment. ``~/.***`` is the already-redacted Duckwork marker and stays.
_TILDE_POSIX_RE = re.compile(r'~/(?!\.\*\*\*)[^\s]+')

# 3. Uppercase env-var-like tokens (spec rule 2: ENVVAR=***). Lowercase
#    key=value config (host=, port=, name=) is NOT an env var and survives.
_ENV_VAR_RE = re.compile(r'[A-Z][A-Z0-9_]{2,}=[^\s]*')

# 3b. Natural-language secret key assignments (password=, api_key=, token=, …).
#     Case-insensitive key name + explicit = or : separator. This is what
#     redacts `password=hunter2` (spec rule 7 vector) without nuking benign
#     lowercase config like host=127.0.0.1.
_SECRET_KEY_RE = re.compile(
    r'(?i)\b(password|passwd|pwd|secret|secret_key|api_key|apikey|api_token|'
    r'access_key|access_token|token|credential|credentials|auth)\s*[=:]\s*[^\s,;]+'
)

# 4. Secret-shaped strings
# (a) High-entropy tokens ≥20 chars, Shannon entropy > 4.5 bits/char
# (b) HEX-formatted credentials ≥24 hex chars (lower entropy but credential shape)
# (c) Base64-ish ≥24 chars AND high-entropy (short IDs, commit-hash prefixes, SHA-256 digests survive)

def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((n / length) * math.log2(n / length) for n in freq.values() if n > 0)

_HIGH_ENTROPY_RE = re.compile(r'[A-Za-z0-9+/=_-]{20,}')
_HEX_CREDENTIAL_RE = re.compile(r'(?<![A-Za-z0-9])([0-9a-fA-F]{24,})(?![A-Za-z0-9])')

# AWS access-key identifiers are sensitive metadata but are not entropic
# enough for the generic token rule. Long-term IDs use AKIA; temporary IDs
# use ASIA. Match the complete 20-character identifier only.
_AWS_ACCESS_KEY_ID_RE = re.compile(
    r'(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])'
)

# Hash digests (sha256:, md5:, sha1:, …) are content hashes, NOT secrets.
# They are protected before redaction so they survive masking instead of
# being destroyed by the hex-credential / high-entropy rules.
_HASH_DIGEST_RE = re.compile(
    r'(?:sha256|sha512|sha384|sha224|sha1|sha|md5|blake2b|blake2s|crc32|crc64)'
    r':[0-9a-fA-F]{16,}'
)

# Mask failure counter for observability
_masker_failures: int = 0


def _redact_base64_paths(text: str) -> str:
    """Decode base64 tokens and redact any that decode to paths."""
    def _replace_match(m: re.Match) -> str:
        token = m.group(0)
        try:
            # Lenient decode: accept unpadded / mis-padded base64 tokens.
            # Python's strict b64decode raises on missing padding, so an
            # unpadded 16-char token (e.g. "L3RtcC9zZWNyZXQ" for /tmp/secret)
            # would survive redaction. Pad with "=" to a multiple of 4 first.
            _padded = token.rstrip("=")
            _pad_needed = (4 - len(_padded) % 4) % 4
            _padded += "=" * _pad_needed
            decoded = base64.b64decode(_padded).decode("utf-8", errors="replace")
            # Check if decoded content looks like a path
            if any(p.search(decoded) for p in (
                _POSIX_ABS_PATH_RE, _WINDOWS_PATH_RE,
                _FILE_URL_RE, re.compile(r'^/'), re.compile(r'^[A-Za-z]:\\'),
            )):
                return "~/…"
        except Exception:
            pass
        return token
    # Only match tokens that start with a letter/digit (not part of env-var assignment)
    # This avoids matching env-var values like abc123def456 as base64 tokens
    return _BASE64_TOKEN_RE.sub(_replace_match, text)


def privacy_mask(text: str) -> str:
    """Apply the privacy mask to a text string.

    Rules (in order):
    1. Base64-encoded path redaction
    2. Absolute path redaction (/home/user → ~/, etc.)
    3. Env-var-like token redaction
    4. Known provider identifiers and secret-shaped string redaction
    5. Truncate to MAX_SUMMARY_CHARS with ellipsis

    Fail-closed: if the masker throws or receives malformed input, return
    "[redacted]" and increment the masker_failure counter.
    """
    global _masker_failures
    try:
        result = text

        # Step 0: Protect hash digests (sha256:, md5:, …) so they survive.
        # Placeholders use a sentinel unlikely to occur in real input.
        _HASH_PLACEHOLDER = "\x00HASH\x00"
        _protected_hashes: list[str] = []
        def _protect_hash(m: re.Match) -> str:
            _protected_hashes.append(m.group(0))
            return _HASH_PLACEHOLDER + str(len(_protected_hashes) - 1) + _HASH_PLACEHOLDER
        result = _HASH_DIGEST_RE.sub(_protect_hash, result)

        # Step 1: Base64-encoded paths (decode and redact)
        result = _redact_base64_paths(result)

        # Step 2a: URL-encoded path components
        result = re.sub(r'%2F', '/', result)
        result = re.sub(r'%5C', r'\\', result)

        # Step 2b: file:/// URLs
        result = _FILE_URL_RE.sub('~', result)

        # Step 2c: Windows paths (C:\Users\user → ~)
        result = _WINDOWS_PATH_RE.sub('~', result)

        # Step 2d: POSIX absolute paths (/home/…, /root/…, /etc/…, /var/…, /tmp/… → ~/)
        result = _POSIX_ABS_PATH_RE.sub('~/', result)

        # Step 2e: ~/.duckwork paths — redacted to ~/.*** by default
        result = _DUCKWORK_OPT_RE.sub('~/.***', result)

        # Step 2f: Generic home-relative paths
        result = _TILDE_POSIX_RE.sub('~/…', result)

        # Step 3a: Uppercase env-var-like tokens (ENVVAR=***)
        result = _ENV_VAR_RE.sub(lambda m: m.group(0).split('=')[0] + '=***', result)

        # Step 3b: Natural-language secret key assignments (password=, api_key=, …)
        result = _SECRET_KEY_RE.sub(lambda m: m.group(1) + '=***', result)

        # Step 4a: Known provider key identifiers
        result = _AWS_ACCESS_KEY_ID_RE.sub("***", result)

        # Step 4b: Secret-shaped strings
        # (a) High-entropy tokens
        def _entropy_redact(m: re.Match) -> str:
            token = m.group(0)
            ent = _shannon_entropy(token)
            length = len(token)
            if length >= 20 and ent > 4.5:
                return "***"
            return token

        result = _HIGH_ENTROPY_RE.sub(_entropy_redact, result)

        # (b) HEX credentials ≥24 hex chars → replace the WHOLE credential
        #     with *** (not append — appending would still leak the value).
        result = _HEX_CREDENTIAL_RE.sub(lambda m: "***", result)

        # Step 5: Restore protected hash digests.
        def _restore_hash(m: re.Match) -> str:
            idx = int(m.group(1))
            return _protected_hashes[idx]
        result = re.sub(
            _HASH_PLACEHOLDER + r'(\d+)' + _HASH_PLACEHOLDER,
            _restore_hash,
            result,
        )

        # Step 6: Truncate to MAX_SUMMARY_CHARS
        if len(result) > MAX_SUMMARY_CHARS:
            result = result[:MAX_SUMMARY_CHARS - 3] + "..."

        return result

    except Exception:
        _masker_failures += 1
        log.error("Masker failure on input, returning [redacted]")
        return "[redacted]"


def mask_summary(summary: dict, event_type: str) -> str:
    """Mask a structured summary dict and serialise to JSON string.

    The `note` field (if present) is the only free-text field and is masked.
    All other fields are typed scalars that don't need masking.

    Returns a JSON string ≤280 chars. Fail-closed: on any error, returns
    '{"type":"<type>","summary":"[redacted]"}'.
    """
    global _masker_failures
    try:
        masked = dict(summary)
        if "note" in masked:
            masked["note"] = privacy_mask(str(masked["note"]))
        # Serialise
        result = json.dumps(masked, separators=(",", ":"))
        if len(result) > MAX_SUMMARY_CHARS:
            # Truncate the note field first (it's the free-text field)
            if "note" in masked:
                max_note = MAX_SUMMARY_CHARS - len(result) + len(masked["note"]) - 3
                masked["note"] = masked["note"][:max(max_note, 0)] + "..."
                result = json.dumps(masked, separators=(",", ":"))
            # If typed scalars (tool/role/from/to) are still too long,
            # truncate them progressively. NEVER slice the raw JSON — a
            # mid-string slice is invalid JSON and crashes guest parsers.
            if len(result) > MAX_SUMMARY_CHARS:
                for key in ("tool", "role", "from", "to", "status"):
                    if isinstance(masked.get(key), str) and len(masked[key]) > 8:
                        # trim to fit: total - overhead - "..." - other fields
                        overhead = len(result) - len(json.dumps(masked[key]))
                        budget = MAX_SUMMARY_CHARS - overhead - 3
                        if budget < 8:
                            continue
                        masked[key] = masked[key][:budget] + "..."
                        result = json.dumps(masked, separators=(",", ":"))
                        if len(result) <= MAX_SUMMARY_CHARS:
                            break
            # Absolute last resort: valid minimal JSON, never a broken slice
            if len(result) > MAX_SUMMARY_CHARS:
                result = json.dumps(
                    {"type": event_type, "summary": "[redacted]"},
                    separators=(",", ":"),
                )
        return result
    except Exception:
        _masker_failures += 1
        return json.dumps({"type": event_type, "summary": "[redacted]"}, separators=(",", ":"))


# ---------------------------------------------------------------------------
# FeedEngine — append-only event store
# ---------------------------------------------------------------------------

class FeedEngine:
    """Manages the append-only event feed for spectator guests.

    Events are stored in the SQLite `events` table as structured summaries.
    Each event has a monotonically increasing sequence number (seq), session_id,
    type, summary (≤280 chars JSON), and RFC3339 timestamp.

    The FeedEngine:
    - Appends events (after privacy masking)
    - Queries events by session_id with cursor-based pagination
    - Sweeps expired events (retention policy)
    - Handles cursor reset when stale
    """

    def __init__(self, db: SpectatorDB, session_id: str) -> None:
        self.db = db
        self.session_id = session_id

    def _serialise_event(self, event_type: str, summary: dict) -> str:
        """Validate and privacy-mask one event before it reaches storage."""
        valid_types = {"tool_call", "tool_result", "message", "status_change"}
        if event_type not in valid_types:
            raise ValueError(f"Invalid event type: {event_type!r}, must be one of {valid_types}")

        shapes: dict[str, frozenset[str]] = {
            "tool_call": frozenset({"tool", "args", "note"}),
            "tool_result": frozenset({"tool", "status", "size"}),
            "message": frozenset({"role", "chars", "note"}),
            "status_change": frozenset({"from", "to"}),
        }
        unknown = set(summary.keys()) - shapes[event_type]
        if unknown:
            raise ValueError(
                f"Summary for {event_type!r} has non-contract keys {sorted(unknown)}; "
                "raw content must never be stored — only typed fields + masked `note`"
            )
        return mask_summary(summary, event_type)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds")

    def append(self, event_type: str, summary: dict) -> int:
        """Append a local event and return its sequence number."""
        serialised = self._serialise_event(event_type, summary)
        timestamp = self._timestamp()

        with self.db.write_txn() as cur:
            cur.execute(
                """INSERT INTO events (session_id, type, summary, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (self.session_id, event_type, serialised, timestamp),
            )
            seq = int(cur.lastrowid or 0)
        if not seq:
            raise RuntimeError("event insert did not return a sequence number")

        log.debug("Appended event seq=%d type=%s", seq, event_type)
        return seq

    def append_external(self, source_id: str, event_type: str, summary: dict) -> tuple[int, bool]:
        """Idempotently append an event received through the portable bridge.

        The same ``(session_id, source_id)`` is accepted once. Retries return
        the original sequence number without creating duplicate feed entries.
        """
        source_id = source_id.strip()
        if not source_id or len(source_id) > 200 or any(c in source_id for c in "\r\n\x00"):
            raise ValueError("source_id must be 1-200 visible characters")
        serialised = self._serialise_event(event_type, summary)
        timestamp = self._timestamp()

        with self.db.write_txn() as cur:
            existing = cur.execute(
                "SELECT seq FROM event_sources WHERE session_id = ? AND source_id = ?",
                (self.session_id, source_id),
            ).fetchone()
            if existing is not None:
                return int(existing["seq"]), False

            cur.execute(
                """INSERT INTO events (session_id, type, summary, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (self.session_id, event_type, serialised, timestamp),
            )
            seq = int(cur.lastrowid or 0)
            if not seq:
                raise RuntimeError("event insert did not return a sequence number")
            cur.execute(
                "INSERT INTO event_sources (session_id, source_id, seq) VALUES (?, ?, ?)",
                (self.session_id, source_id, seq),
            )
        return seq, True

    def query(self, since: int = 0, limit: int = 50, event_types: list[str] | None = None) -> dict:
        """Query events with cursor-based pagination.

        Returns:
            {"events": [...], "reset": False} on normal pagination
            {"events": [...], "reset": True, "oldest_seq": N} if the since
            cursor is older than the oldest retained event (stale cursor).

        Each event: {"seq": int, "type": str, "summary": str, "timestamp": str}
        """
        limit = max(1, min(limit, 200))

        # Check if since cursor is stale (older than oldest retained event)
        # since=0 is always a valid "start from beginning" request — never stale
        with self.db.conn as conn:
            oldest = conn.execute(
                "SELECT MIN(seq) FROM events WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()[0]

            # since=0 means "from the beginning" — never a stale cursor
            if oldest is not None and since > 0 and since < oldest:
                # Stale cursor — return reset response with events from oldest
                base_query = """
                    SELECT seq, type, summary, timestamp FROM events
                    WHERE session_id = ? AND seq >= ?
                """
                params: list = [self.session_id, oldest]

                if event_types:
                    placeholders = ",".join("?" * len(event_types))
                    base_query += f" AND type IN ({placeholders})"
                    params.extend(event_types)

                base_query += " ORDER BY seq ASC LIMIT ?"
                params.append(limit)

                rows = conn.execute(base_query, params).fetchall()
                events = [
                    {
                        "seq": row["seq"],
                        "type": row["type"],
                        "summary": row["summary"],
                        "timestamp": row["timestamp"],
                    }
                    for row in rows
                ]
                return {"events": events, "reset": True, "oldest_seq": oldest}

            # Normal pagination
            query = """
                SELECT seq, type, summary, timestamp FROM events
                WHERE session_id = ? AND seq > ?
            """
            params = [self.session_id, since]

            if event_types:
                placeholders = ",".join("?" * len(event_types))
                query += f" AND type IN ({placeholders})"
                params.extend(event_types)

            query += " ORDER BY seq ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            events = [
                {
                    "seq": row["seq"],
                    "type": row["type"],
                    "summary": row["summary"],
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ]
            return {"events": events, "reset": False}

    def latest_seq(self) -> int:
        """Return the highest event seq for this session (0 when empty)."""
        with self.db.conn as conn:
            row = conn.execute(
                "SELECT MAX(seq) FROM events WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()
        return int(row[0] or 0)

    def sweep_expired(self, retention_days: int = 7) -> int:
        """Delete events older than retention_days. Called on the poll-cycle hot path.

        Returns the number of deleted events.
        """
        from datetime import timedelta
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()

        with self.db.write_txn() as cur:
            cur.execute(
                "DELETE FROM events WHERE session_id = ? AND timestamp < ?",
                (self.session_id, cutoff),
            )
            deleted = cur.rowcount

        if deleted > 0:
            log.info("Swept %d expired events for session %s", deleted, self.session_id[:8])
        return deleted

    @staticmethod
    def get_masker_failures() -> int:
        """Return the total count of masker failures for observability."""
        return _masker_failures