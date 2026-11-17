"""SuggestionGate — gated suggestion submission, approval, and injection.

The suggestion lifecycle:

    pending ── approve(inject True) ──> injected      (receipt queued)
    pending ── approve(inject False/Timeout) ──> approved  (receipt unreachable)
    pending ── reject ──> rejected                      (receipt refused)
    pending ── (TTL) ──> expired                        (receipt expired)

Durability / idempotency contract (normative, from spec):

- ``delivery_id`` is minted exactly once per suggestion, inside the same
  ``BEGIN IMMEDIATE`` transaction that flips ``status`` to ``approved`` and
  sets ``delivery_state='attempting'``. It is NEVER re-minted on retry.
- ``inject_fn`` is invoked ONLY after that transaction commits.
- On success a second transaction flips ``delivery_state='injected'`` and
  ``status='injected'`` — guarded by ``WHERE status='approved'`` so a
  concurrent reject/expire can never be overwritten.
- On failure/timeout a second transaction flips ``delivery_state='unreachable'``
  (status stays ``approved``) so the host may retry with the SAME delivery_id.
- ``delivery_state='injected'`` → any further approve raises 409 (never
  re-injected). ``delivery_state='attempting'`` after a crash → retry is
  permitted, re-invoking inject with the SAME delivery_id and SAME marker.

Concurrency guarantees (hardened from Hermaguard Gate 0 review):

- The capacity check runs INSIDE the ``write_txn`` (BEGIN IMMEDIATE) so the
  pending-count ceiling is a hard bound, not a TOCTOU advisory.
- An in-memory in-flight guard (``self._inflight`` keyed by ``delivery_id``)
  is held for the FULL lifetime of the inject worker thread (released in the
  thread's ``finally``, including abandoned threads on timeout). This means a
  concurrent approve of the same suggestion → 409, and a timeout-then-retry
  cannot double-inject while the abandoned thread is still running.
- Expiry is re-validated inside the approve transaction itself (not only by a
  separate pre-step), closing the approve-after-expiry race.
- All approve/reject/get lookups are scoped by ``session_id`` — no
  cross-session mutation.

No code path auto-injects: ``submit`` never touches ``inject_fn``. Pending
suggestions live only in the ``suggestions`` table until an explicit approve.

The plugin is zero-dependency over stdlib: ``ReceiptState`` carries the exact
wire values of ``agent_peer.models.ReceiptState`` plus the plugin-specific
``host_gone``, so the contract stays compatible without importing agent_peer.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

log = logging.getLogger("spectator.suggest")

MAX_CONTENT_BYTES = 32 * 1024  # 32 KiB UTF-8 ceiling (agent_peer bound)
_MAX_RATE_KEYS = 10000  # bound in-memory rate-limiter buckets


class ReceiptState(enum.StrEnum):
    """Immediate receipt states (wire-compatible with agent_peer)."""

    QUEUED = "queued"
    HELD = "held"
    REFUSED = "refused"
    UNREACHABLE = "unreachable"
    EXPIRED = "expired"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    OVER_CAPACITY = "over_capacity"
    HOST_GONE = "host_gone"  # plugin-specific


class SuggestionError(Exception):
    """Raised on suggestion lifecycle errors; carries HTTP status + receipt."""

    def __init__(self, message: str, status_code: int = 400, receipt_state: str = ReceiptState.INVALID.value) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.receipt_state = receipt_state


class RateLimiter:
    """Thread-safe sliding-window rate limiter per guest: burst 5 / sustained 20/min.

    Buckets are bounded to ``_MAX_RATE_KEYS`` so a long-lived process with many
    single-use guests cannot grow memory without bound.
    """

    def __init__(self, burst: int = 5, sustained_per_minute: int = 20, window_seconds: float = 60.0) -> None:
        self._burst = burst
        self._sustained = sustained_per_minute
        self._window = window_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= _MAX_RATE_KEYS:
                    self._evict()
                events = []
                self._events[key] = events
            cutoff = now - self._window
            while events and events[0] <= cutoff:
                events.pop(0)
            if len(events) >= self._sustained:
                return False
            if len(events) >= self._burst and (now - events[0]) < 1.0:
                return False
            events.append(now)
            return True

    def _evict(self) -> None:
        """Drop empty buckets, then prune oldest buckets to stay under the cap."""
        for k in [k for k, v in self._events.items() if not v]:
            self._events.pop(k, None)
        while len(self._events) >= _MAX_RATE_KEYS:
            # dict insertion order approximates "oldest guest first".
            oldest = next(iter(self._events))
            self._events.pop(oldest, None)


def _now_iso() -> str:
    """Fixed-width RFC3339 UTC timestamp (microseconds always present)."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


class SuggestionGate:
    """Gated suggestion submission + approval state machine.

    ``inject_fn`` is the host injection seam, shaped as
    ``inject_fn(content, role="user", mode="queue") -> bool``. It defaults to a
    fail-closed no-op returning ``False`` (the real ``DuckworkCLI.inject_message``
    is wired in by the host / demo layer, since the dashboard process has no
    live ``_cli_ref``). The plugin never auto-injects; only ``approve`` calls
    ``inject_fn``.
    """

    def __init__(
        self,
        db,
        inject_fn: Callable | None = None,
        *,
        rate_burst: int = 5,
        rate_per_minute: int = 20,
        capacity: int = 100,
        pending_ttl_seconds: int = 300,
        inject_timeout_seconds: float = 2.0,
    ) -> None:
        self.db = db
        self.inject_fn = inject_fn or (lambda content, role="user", mode="queue": False)
        self._limiter = RateLimiter(burst=rate_burst, sustained_per_minute=rate_per_minute)
        self._capacity = max(1, capacity)
        self._pending_ttl = pending_ttl_seconds
        self._inject_timeout = max(0.0, inject_timeout_seconds)
        self._inflight: set[str] = set()
        self._inflight_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(self, guest_id: str, session_id: str, content: str, role: str = "user") -> dict:
        """Create a pending suggestion. Role is ALWAYS coerced to 'user'."""
        if not guest_id:
            raise SuggestionError("guest_id required", 500, ReceiptState.INVALID.value)
        if not session_id:
            raise SuggestionError("session_id required", 500, ReceiptState.INVALID.value)
        if not isinstance(content, str) or not content.strip():
            raise SuggestionError("content is required", 422, ReceiptState.INVALID.value)

        # Role coercion: guest-controlled roles are never echoed or persisted.
        _ = role

        # Content bound (32 KiB UTF-8).
        if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
            raise SuggestionError(
                f"content exceeds {MAX_CONTENT_BYTES} bytes", 422, ReceiptState.INVALID.value
            )

        # Rate limit (per guest).
        if not self._limiter.allow(guest_id):
            raise SuggestionError("rate limit exceeded", 429, ReceiptState.RATE_LIMITED.value)

        suggestion_id = str(uuid.uuid4())
        now = _now_iso()
        expires_at = (datetime.now(UTC) + timedelta(seconds=self._pending_ttl)).isoformat(timespec="microseconds")

        # Capacity check + insert are serialized under the same BEGIN IMMEDIATE
        # transaction so the ceiling is a hard bound (no TOCTOU).
        with self.db.write_txn() as cur:
            pending = cur.execute(
                "SELECT COUNT(*) FROM suggestions WHERE session_id = ? AND status = 'pending'",
                (session_id,),
            ).fetchone()[0]
            if pending >= self._capacity:
                raise SuggestionError("inbox full", 503, ReceiptState.OVER_CAPACITY.value)

            cur.execute(
                """INSERT INTO suggestions
                   (id, guest_id, session_id, content, role, status, receipt_state,
                    created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, 'user', 'pending', ?, ?, ?, ?)""",
                (suggestion_id, guest_id, session_id, content, ReceiptState.HELD.value,
                 now, now, expires_at),
            )
            cur.execute(
                """INSERT INTO audit_log (at, actor_role, actor_id, action, target_id, outcome, receipt_state)
                   VALUES (?, 'guest', ?, 'suggestion_create', ?, 'ok', ?)""",
                (now, guest_id, suggestion_id, ReceiptState.HELD.value),
            )

        return {
            "suggestion_id": suggestion_id,
            "status": "pending",
            "receipt": ReceiptState.HELD.value,
        }

    # ------------------------------------------------------------------
    # Approve / reject (the state machine)
    # ------------------------------------------------------------------

    def approve(self, suggestion_id: str, *, actor_role: str = "host", session_id: str) -> dict:
        """Atomically flip pending → approved and inject. Idempotent via delivery_id.

        Returns {suggestion_id, status, receipt, injected, delivery_id, reason?}.
        """
        # Transaction 1: expire overdue pending rows for this session, then
        # verify state + mint delivery_id (exactly once) — all in one txn.
        with self.db.write_txn() as cur:
            now = _now_iso()
            cur.execute(
                "UPDATE suggestions SET status='expired', receipt_state=?, updated_at=? "
                "WHERE session_id = ? AND status = 'pending' AND expires_at < ?",
                (ReceiptState.EXPIRED.value, now, session_id, now),
            )

            row = cur.execute(
                "SELECT id, guest_id, session_id, content, status, delivery_id, delivery_state, expires_at "
                "FROM suggestions WHERE id = ? AND session_id = ?",
                (suggestion_id, session_id),
            ).fetchone()
            if row is None:
                raise SuggestionError("suggestion not found", 404, ReceiptState.INVALID.value)

            status_s = row["status"]
            delivery_id = row["delivery_id"]
            delivery_state = row["delivery_state"]

            if status_s == "injected" or delivery_state == "injected":
                raise SuggestionError("suggestion already injected", 409, ReceiptState.QUEUED.value)
            if status_s == "rejected":
                raise SuggestionError("suggestion already rejected", 409, ReceiptState.REFUSED.value)
            if status_s == "expired":
                raise SuggestionError("suggestion expired", 409, ReceiptState.EXPIRED.value)

            if status_s == "pending" and delivery_id is None:
                # First approval: mint delivery_id once, flip to approved/attempting.
                delivery_id = str(uuid.uuid4())
                cur.execute(
                    "UPDATE suggestions SET status='approved', delivery_id=?, delivery_state='attempting', "
                    "approved_at=? WHERE id=?",
                    (delivery_id, now, suggestion_id),
                )
            elif status_s == "approved" and delivery_state in ("attempting", "unreachable"):
                # Recovery / retry: reuse the SAME delivery_id.
                cur.execute(
                    "UPDATE suggestions SET delivery_state='attempting' WHERE id=?",
                    (suggestion_id,),
                )
            else:
                raise SuggestionError("suggestion in invalid state", 409, ReceiptState.INVALID.value)

            content = row["content"]

        # Claim the in-flight guard for the inject-thread lifetime. A concurrent
        # approve (or a retry while an abandoned timeout thread still runs)
        # hits this and 409s — no double injection.
        with self._inflight_lock:
            if delivery_id in self._inflight:
                raise SuggestionError("injection already in progress", 409, ReceiptState.QUEUED.value)
            self._inflight.add(delivery_id)

        def _release() -> None:
            with self._inflight_lock:
                self._inflight.discard(delivery_id)

        marker = f"[spectator:{delivery_id}]\n{content}"
        result = self._call_inject_bounded(marker, "user", "queue", self._inject_timeout, on_done=_release)

        # Transaction 2: persist delivery outcome (guarded by status='approved'
        # so a concurrent reject/expire is never overwritten).
        if result is True:
            with self.db.write_txn() as cur:
                cur.execute(
                    "UPDATE suggestions SET status='injected', delivery_state='injected', "
                    "receipt_state=?, updated_at=? WHERE id=? AND status='approved'",
                    (ReceiptState.QUEUED.value, _now_iso(), suggestion_id),
                )
                changed = cur.rowcount
                cur.execute(
                    "INSERT INTO audit_log (at, actor_role, actor_id, action, target_id, outcome, receipt_state) "
                    "VALUES (?, 'host', 'host', 'suggestion_approve', ?, 'ok', ?)",
                    (_now_iso(), suggestion_id, ReceiptState.QUEUED.value),
                )
            if changed == 0:
                # Rejected/expired concurrently mid-flight — do not claim injected.
                with self.db.conn as conn:
                    cur_status = conn.execute(
                        "SELECT status FROM suggestions WHERE id=?", (suggestion_id,)
                    ).fetchone()["status"]
                receipt = ReceiptState.REFUSED.value if cur_status == "rejected" else ReceiptState.EXPIRED.value
                raise SuggestionError(f"suggestion {cur_status} during injection", 409, receipt)

            return {
                "suggestion_id": suggestion_id,
                "status": "injected",
                "receipt": ReceiptState.QUEUED.value,
                "injected": True,
                "delivery_id": delivery_id,
            }

        # Failure (False) or timeout (None).
        reason = "timeout" if result is None else "unreachable"
        with self.db.write_txn() as cur:
            cur.execute(
                "UPDATE suggestions SET delivery_state='unreachable', receipt_state=?, updated_at=? "
                "WHERE id=? AND status='approved'",
                (ReceiptState.UNREACHABLE.value, _now_iso(), suggestion_id),
            )
            cur.execute(
                "INSERT INTO audit_log (at, actor_role, actor_id, action, target_id, outcome, receipt_state) "
                "VALUES (?, 'host', 'host', 'suggestion_approve', ?, 'error', ?)",
                (_now_iso(), suggestion_id, ReceiptState.UNREACHABLE.value),
            )
        return {
            "suggestion_id": suggestion_id,
            "status": "approved",
            "receipt": ReceiptState.UNREACHABLE.value,
            "injected": False,
            "delivery_id": delivery_id,
            "reason": reason,
        }

    def reject(self, suggestion_id: str, *, actor_role: str = "host", session_id: str) -> dict:
        """Reject a pending (or approved) suggestion. Injected/expired → 409."""
        with self.db.write_txn() as cur:
            now = _now_iso()
            cur.execute(
                "UPDATE suggestions SET status='expired', receipt_state=?, updated_at=? "
                "WHERE session_id = ? AND status = 'pending' AND expires_at < ?",
                (ReceiptState.EXPIRED.value, now, session_id, now),
            )

            row = cur.execute(
                "SELECT id, status FROM suggestions WHERE id = ? AND session_id = ?",
                (suggestion_id, session_id),
            ).fetchone()
            if row is None:
                raise SuggestionError("suggestion not found", 404, ReceiptState.INVALID.value)
            if row["status"] == "injected":
                raise SuggestionError("suggestion already injected", 409, ReceiptState.QUEUED.value)
            if row["status"] == "rejected":
                raise SuggestionError("suggestion already rejected", 409, ReceiptState.REFUSED.value)
            if row["status"] == "expired":
                raise SuggestionError("suggestion expired", 409, ReceiptState.EXPIRED.value)

            cur.execute(
                "UPDATE suggestions SET status='rejected', receipt_state=?, updated_at=? WHERE id=?",
                (ReceiptState.REFUSED.value, now, suggestion_id),
            )
            cur.execute(
                "INSERT INTO audit_log (at, actor_role, actor_id, action, target_id, outcome, receipt_state) "
                "VALUES (?, 'host', 'host', 'suggestion_reject', ?, 'ok', ?)",
                (now, suggestion_id, ReceiptState.REFUSED.value),
            )

        return {"suggestion_id": suggestion_id, "status": "rejected", "receipt": ReceiptState.REFUSED.value}

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_suggestion(self, suggestion_id: str, *, actor_role: str, guest_id: str | None = None, session_id: str) -> dict:
        """Full detail. Host: unmasked content. Guest: own suggestion, masked content.

        A guest requesting another guest's suggestion raises 403.
        """
        self._lazy_expire(session_id)
        with self.db.conn as conn:
            row = conn.execute(
                "SELECT id, guest_id, content, role, status, receipt_state, created_at "
                "FROM suggestions WHERE id = ? AND session_id = ?",
                (suggestion_id, session_id),
            ).fetchone()
        if row is None:
            raise SuggestionError("suggestion not found", 404, ReceiptState.INVALID.value)

        if actor_role == "guest":
            if row["guest_id"] != guest_id:
                raise SuggestionError("forbidden", 403, ReceiptState.INVALID.value)
            from spectator.feed.engine import privacy_mask
            content = privacy_mask(row["content"])
        else:
            content = row["content"]

        return {
            "id": row["id"],
            "guest_id": row["guest_id"],
            "content": content,
            "role": row["role"],
            "status": row["status"],
            "receipt_state": row["receipt_state"],
            "created_at": row["created_at"],
        }

    def list_suggestions(
        self,
        session_id: str,
        *,
        status: str | None = None,
        guest_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """List suggestions. Host: all; guest: own only (masked content_truncated).

        Per the spec, the list endpoint returns ``content_truncated`` (masked)
        for ALL roles — the host reads full content via the detail endpoint.
        """
        self._lazy_expire(session_id)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        params: list = [session_id]
        if status and guest_id:
            count_query = (
                "SELECT COUNT(*) FROM suggestions "
                "WHERE session_id = ? AND status = ? AND guest_id = ?"
            )
            list_query = (
                "SELECT id, guest_id, content, status, receipt_state, created_at "
                "FROM suggestions WHERE session_id = ? AND status = ? AND guest_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params.extend((status, guest_id))
        elif status:
            count_query = (
                "SELECT COUNT(*) FROM suggestions WHERE session_id = ? AND status = ?"
            )
            list_query = (
                "SELECT id, guest_id, content, status, receipt_state, created_at "
                "FROM suggestions WHERE session_id = ? AND status = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params.append(status)
        elif guest_id:
            count_query = (
                "SELECT COUNT(*) FROM suggestions WHERE session_id = ? AND guest_id = ?"
            )
            list_query = (
                "SELECT id, guest_id, content, status, receipt_state, created_at "
                "FROM suggestions WHERE session_id = ? AND guest_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params.append(guest_id)
        else:
            count_query = "SELECT COUNT(*) FROM suggestions WHERE session_id = ?"
            list_query = (
                "SELECT id, guest_id, content, status, receipt_state, created_at "
                "FROM suggestions WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )

        with self.db.conn as conn:
            total = conn.execute(count_query, params).fetchone()[0]
            rows = conn.execute(list_query, [*params, limit, offset]).fetchall()

        from spectator.feed.engine import privacy_mask
        items = []
        for r in rows:
            content = privacy_mask(r["content"])[:140]
            items.append({
                "id": r["id"],
                "guest_id": r["guest_id"],
                "content_truncated": content,
                "status": r["status"],
                "receipt_state": r["receipt_state"],
                "created_at": r["created_at"],
            })
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    # ------------------------------------------------------------------
    # Expiry (lazy + sweep, no background thread)
    # ------------------------------------------------------------------

    def _lazy_expire(self, session_id: str) -> int:
        """Flip overdue pending suggestions to expired. Runs on any read/write."""
        now = _now_iso()
        with self.db.write_txn() as cur:
            cur.execute(
                "UPDATE suggestions SET status='expired', receipt_state=?, updated_at=? "
                "WHERE session_id = ? AND status = 'pending' AND expires_at < ?",
                (ReceiptState.EXPIRED.value, now, session_id, now),
            )
            return cur.rowcount

    def sweep_expired(self, session_id: str) -> int:
        """Poll-cycle sweep: same UPDATE as lazy expiry. Returns rows flipped."""
        return self._lazy_expire(session_id)

    # ------------------------------------------------------------------
    # Injection seam (bounded)
    # ------------------------------------------------------------------

    def _call_inject_bounded(self, content: str, role: str, mode: str, timeout: float, on_done: Callable | None = None):
        """Invoke inject_fn in a daemon worker thread, waiting at most `timeout`.

        Returns True (accepted), False (rejected/closed), or None (timeout —
        the worker is abandoned, never joined, so a stuck seam can't block the
        request loop). ``on_done`` (if given) runs in the thread's ``finally``
        so the in-flight guard is released exactly when the seam finishes — even
        for abandoned timeout threads.
        """
        holder: dict = {}
        done = threading.Event()

        def _run() -> None:
            try:
                holder["ok"] = bool(self.inject_fn(content, role=role, mode=mode))
            except Exception:
                log.exception("inject_fn raised; treating injection as unreachable")
                holder["ok"] = False
            finally:
                done.set()
                if on_done is not None:
                    on_done()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        if done.wait(timeout):
            return holder.get("ok", False)
        return None
