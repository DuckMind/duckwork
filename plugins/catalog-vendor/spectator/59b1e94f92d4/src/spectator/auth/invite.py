"""Invite lifecycle management for duckwork-spectator.

Invite flow:
  1. Host mints a 256-bit random token → stores SHA-256 hash in DB
  2. Token exists ONLY in the invite link fragment (#invite=…)
  3. Guest POSTs token in join body → single-use consume → gets guest_id + guest_token
  4. Host revokes by invite_id (internal UUID, never the raw token in a URL)

Guest token derivation:
  guest_token = guest_id + ":" + HMAC-SHA256(host_secret, guest_id || ":" || token_hash)
  - O(1) verification via guest_id prefix (PK index lookup)
  - Unforgeable: requires host_secret to recompute HMAC
  - Revocation: guests.revoked = 1 fails verification

Session-gen binding:
  Each invite stores session_gen; stale invites (from a previous session_gen)
  are invalidated on plugin init (host_gone semantics).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from spectator.auth.auth import HostSecretManager, derive_guest_token
from spectator.db.db import SpectatorDB, utcnow

log = logging.getLogger("spectator.invite")


class InviteError(Exception):
    """Raised on invite lifecycle errors."""
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class InviteManager:
    """Manages the invite lifecycle: mint, join, revoke, expire.

    All DB writes go through SpectatorDB.write_txn() for single-writer
    discipline (BEGIN IMMEDIATE + threading.Lock).
    """

    def __init__(self, db: SpectatorDB, secret_mgr: HostSecretManager, current_session_gen: str = "") -> None:
        self.db = db
        self.secret_mgr = secret_mgr
        self._current_session_gen = current_session_gen

    # -----------------------------------------------------------------------
    # Mint
    # -----------------------------------------------------------------------

    def mint_invite(
        self,
        session_id: str,
        session_gen: str,
        ttl_seconds: int = 86400,
        session_label: str = "",
    ) -> dict:
        """Mint a new invite token. Returns dict with token, invite_id, etc.

        The raw token is returned ONCE and never stored — only its SHA-256
        hash is persisted. The caller constructs the invite URL with the
        token in the fragment only (#invite=…).

        Host-only: caller must verify host auth before calling this.
        """
        if self.secret_mgr.degraded:
            raise InviteError("Cannot mint invites while backend is degraded", 503)

        # Generate 256-bit random token
        raw_token = secrets.token_hex(32)  # 256 bits = 32 bytes = 64 hex chars
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        invite_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        with self.db.write_txn() as cur:
            cur.execute(
                """INSERT INTO invites
                   (invite_id, token_hash, session_id, session_gen, session_label,
                    created_at, expires_at, revoked, joined)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)""",
                (
                    invite_id,
                    token_hash,
                    session_id,
                    session_gen,
                    session_label,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            # Audit
            cur.execute(
                """INSERT INTO audit_log
                   (at, actor_role, actor_id, action, target_id, outcome)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (utcnow(), "host", "host", "invite_mint", invite_id, "ok"),
            )

        log.info("Minted invite %s for session %s (ttl=%ds)", invite_id[:8], session_id[:8], ttl_seconds)

        return {
            "invite_id": invite_id,
            "token": raw_token,  # Returned ONCE, never stored
            "token_hash_prefix": token_hash[:8],  # For display only
            "expires_at": expires_at.isoformat(),
            "session_label": session_label,
        }

    # -----------------------------------------------------------------------
    # Join
    # -----------------------------------------------------------------------

    def join_invite(
        self,
        raw_token: str,
        guest_name: str = "",
    ) -> dict:
        """Consume an invite token and create a guest session.

        Single-use: the invite is marked as joined after first use.
        Returns {guest_id, guest_token, session_id, feed_cursor}.

        The raw_token comes from the URL fragment, POSTed in the request body.
        """
        if self.secret_mgr.degraded:
            raise InviteError("Cannot join while backend is degraded", 503)

        host_secret = self.secret_mgr.secret
        if host_secret is None:
            raise InviteError("Host secret unavailable", 503)

        # Hash the provided token to look up the invite
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Pre-check: revoke stale-gen invites in their own transaction so the
        # revocation persists even if the join raises InviteError.
        # This prevents the rollback-inside-write_txn defense-in-depth gap.
        with self.db.write_txn() as pre_cur:
            pre_cur.execute(
                "SELECT invite_id, session_gen FROM invites WHERE token_hash = ?",
                (token_hash,),
            )
            stale_row = pre_cur.fetchone()
            if stale_row is not None:
                stale_gen = stale_row["session_gen"]
                if self._current_session_gen and stale_gen and stale_gen != self._current_session_gen:
                    # Revoke stale invite in its own committed transaction
                    pre_cur.execute(
                        "UPDATE invites SET revoked = 1 WHERE invite_id = ?",
                        (stale_row["invite_id"],),
                    )
                    # Transaction commits on clean exit

        with self.db.write_txn() as cur:
            # Look up invite by token_hash
            cur.execute(
                "SELECT invite_id, session_id, session_gen, expires_at, revoked, joined FROM invites WHERE token_hash = ?",
                (token_hash,),
            )
            row = cur.fetchone()
            if row is None:
                raise InviteError("Invalid invite token", 401)

            invite_id = row["invite_id"]
            session_id = row["session_id"]
            row["session_gen"]
            expires_at = row["expires_at"]
            revoked = row["revoked"]
            joined = row["joined"]

            # Runtime session-gen check (AC#3 fail-closed) is handled above in
            # the pre-check transaction. If the invite was stale, it's already
            # revoked and the `if revoked` check below will catch it with 410.

            # Validate invite state
            if revoked:
                raise InviteError("Invite has been revoked", 410)
            if joined:
                raise InviteError("Invite already used (single-use)", 401)

            # Check expiry
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.now(UTC) > expires_dt:
                # Mark as expired
                cur.execute(
                    "UPDATE invites SET revoked = 1 WHERE invite_id = ?",
                    (invite_id,),
                )
                raise InviteError("Invite has expired", 401)

            # Create guest
            guest_id = str(uuid.uuid4())
            now_iso = utcnow()

            cur.execute(
                """INSERT INTO guests
                   (guest_id, invite_id, name, joined_at, last_seen_at, revoked)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (guest_id, invite_id, guest_name or "", now_iso, now_iso),
            )

            # Mark invite as joined
            cur.execute(
                "UPDATE invites SET joined = 1 WHERE invite_id = ?",
                (invite_id,),
            )

            # Audit
            cur.execute(
                """INSERT INTO audit_log
                   (at, actor_role, actor_id, action, target_id, outcome)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (utcnow(), "guest", guest_id, "invite_join", invite_id, "ok"),
            )

        # Derive guest token
        guest_token = derive_guest_token(host_secret, guest_id, token_hash)

        log.info("Guest %s joined via invite %s", guest_id[:8], invite_id[:8])

        return {
            "guest_id": guest_id,
            "guest_token": guest_token,
            "session_id": session_id,
            "feed_cursor": 0,
        }

    # -----------------------------------------------------------------------
    # Revoke
    # -----------------------------------------------------------------------

    def revoke_invite(self, invite_id: str, actor_id: str = "host") -> dict:
        """Revoke an invite by its internal invite_id (NOT the raw token).

        Sets revoked=1 on the invite and all associated guests.
        The raw invite token never appears in any URL path.

        Host-only: caller must verify host auth before calling this.
        """
        with self.db.write_txn() as cur:
            cur.execute(
                "SELECT invite_id, revoked FROM invites WHERE invite_id = ?",
                (invite_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise InviteError("Invite not found", 404)
            if row["revoked"]:
                raise InviteError("Invite already revoked", 410)

            # Revoke invite
            cur.execute(
                "UPDATE invites SET revoked = 1 WHERE invite_id = ?",
                (invite_id,),
            )

            # Revoke all guests associated with this invite
            cur.execute(
                "UPDATE guests SET revoked = 1 WHERE invite_id = ?",
                (invite_id,),
            )

            # Expire any pending suggestions from these guests
            cur.execute(
                """UPDATE suggestions SET status = 'expired', receipt_state = 'host_gone'
                   WHERE guest_id IN (
                       SELECT guest_id FROM guests WHERE invite_id = ?
                   ) AND status = 'pending'""",
                (invite_id,),
            )

            # Audit
            cur.execute(
                """INSERT INTO audit_log
                   (at, actor_role, actor_id, action, target_id, outcome)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (utcnow(), "host", actor_id, "invite_revoke", invite_id, "ok"),
            )

        log.info("Revoked invite %s", invite_id[:8])

        return {"status": "revoked", "invite_id": invite_id}

    # -----------------------------------------------------------------------
    # List invites
    # -----------------------------------------------------------------------

    def list_invites(self, session_id: str) -> list[dict]:
        """List active (non-revoked) invites for a session.

        Returns token_hash_prefix (not the full hash) and metadata.
        Host-only: caller must verify host auth before calling this.
        """
        with self.db.conn as conn:
            cur = conn.execute(
                """SELECT invite_id, token_hash, session_id, session_label,
                          created_at, expires_at, revoked, joined
                   FROM invites WHERE session_id = ?
                   ORDER BY created_at DESC""",
                (session_id,),
            )
            rows = cur.fetchall()

        result = []
        for row in rows:
            # Count guests for this invite
            gcur = self.db.conn.execute(
                "SELECT COUNT(*) as cnt FROM guests WHERE invite_id = ? AND revoked = 0",
                (row["invite_id"],),
            )
            guest_count = gcur.fetchone()["cnt"]

            result.append({
                "invite_id": row["invite_id"],
                "token_hash_prefix": row["token_hash"][:8],
                "session_label": row["session_label"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "revoked": bool(row["revoked"]),
                "joined": bool(row["joined"]),
                "guest_count": guest_count,
            })

        return result

    # -----------------------------------------------------------------------
    # Guest token verification
    # -----------------------------------------------------------------------

    def verify_guest_token(self, guest_token: str) -> dict:
        """Verify a guest token and return the guest's info.

        Returns dict with guest_id, invite_id, session_id on success.
        Raises InviteError on invalid/expired/revoked tokens.
        """
        if self.secret_mgr.degraded:
            raise InviteError("Backend degraded", 503)

        host_secret = self.secret_mgr.secret
        if host_secret is None:
            raise InviteError("Host secret unavailable", 503)

        if not guest_token or ":" not in guest_token:
            raise InviteError("Invalid guest token format", 401)

        # Split on first colon: guest_id:mac
        idx = guest_token.index(":")
        guest_id = guest_token[:idx]
        guest_token[idx + 1:]

        # Look up guest by PK (O(1) via index)
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT guest_id, invite_id, revoked FROM guests WHERE guest_id = ?",
                (guest_id,),
            )
            guest_row = cur.fetchone()

        if guest_row is None:
            raise InviteError("Invalid guest token", 401)

        if guest_row["revoked"]:
            raise InviteError("Guest access revoked", 410)

        # Look up the invite to get token_hash for HMAC verification
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT token_hash, session_gen, revoked FROM invites WHERE invite_id = ?",
                (guest_row["invite_id"],),
            )
            invite_row = cur.fetchone()

        if invite_row is None:
            raise InviteError("Invite not found", 401)

        if invite_row["revoked"]:
            raise InviteError("Invite revoked", 410)

        # Runtime session-gen check (AC#3 fail-closed):
        # Reject guest tokens bound to stale invites from a previous session.
        if self._current_session_gen and invite_row["session_gen"] and invite_row["session_gen"] != self._current_session_gen:
            raise InviteError("Guest session expired (host_gone)", 410)

        # Recompute expected token and compare in constant time
        expected = derive_guest_token(host_secret, guest_id, invite_row["token_hash"])
        import hmac
        if not hmac.compare_digest(guest_token, expected):
            raise InviteError("Invalid guest token", 401)

        # Get session_id from invite
        with self.db.conn as conn:
            cur = conn.execute(
                "SELECT session_id FROM invites WHERE invite_id = ?",
                (guest_row["invite_id"],),
            )
            session_row = cur.fetchone()

        # Update last_seen_at (non-critical, don't block on failure)
        try:
            with self.db.conn as conn:
                conn.execute(
                    "UPDATE guests SET last_seen_at = ? WHERE guest_id = ?",
                    (utcnow(), guest_id),
                )
        except Exception:
            log.warning("Failed to update last_seen_at for guest %s", guest_id[:8])

        return {
            "guest_id": guest_id,
            "invite_id": guest_row["invite_id"],
            "session_id": session_row["session_id"] if session_row else "",
            "role": "guest",
        }

    def is_guest_revoked(self, guest_id: str) -> bool:
        """Cheap O(1) revocation check for live-socket re-validation.

        True if the guest row OR its invite is revoked (or the guest no longer
        exists — fail-closed). Used by the WS ``/events`` heartbeat so a revoked
        socket is closed within one heartbeat interval without re-deriving the
        HMAC on every push.
        """
        with self.db.conn as conn:
            row = conn.execute(
                "SELECT g.revoked AS grev, i.revoked AS irev "
                "FROM guests g JOIN invites i ON g.invite_id = i.invite_id "
                "WHERE g.guest_id = ?",
                (guest_id,),
            ).fetchone()
        if row is None:
            return True
        return bool(row["grev"]) or bool(row["irev"])

    # -----------------------------------------------------------------------
    # Host secret verification (for CLI bearer auth)
    # -----------------------------------------------------------------------

    def verify_host_bearer(self, bearer_token: str) -> dict:
        """Verify a host_secret bearer token (hex-encoded).

        Returns dict with role='host' on success.
        Raises InviteError on failure.
        """
        if not self.secret_mgr.verify_host_bearer(bearer_token):
            raise InviteError("Invalid host credentials", 401)

        return {
            "role": "host",
            "actor_id": "host",
        }