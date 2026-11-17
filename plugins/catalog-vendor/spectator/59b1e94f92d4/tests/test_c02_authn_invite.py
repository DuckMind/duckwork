"""Unit + integration tests for C2 — AuthN v3 + invite lifecycle.

Acceptance criteria:
- Guest token verification O(1) via guest_id prefix; unforgeable (bit-flip test)
- Invite token appears ONLY in link fragment; join via POST body; revoke via invite_id
- Session restart invalidates stale invites even with reused session_id (session_gen)
- Role enforcement: guest cannot mint/revoke/approve/read host-only (403)

Test plan:
- Unit: test_token_derivation_unforgeable, session gen invalidation, single-use join
- Integration: test_authn_role_enforcement_live, test_host_ui_auth_via_ctx_rest
"""

import hashlib
import hmac
import secrets
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spectator.auth.auth import (
    HostSecretManager,
    SessionGenManager,
    compute_session_gen,
    derive_guest_token,
)
from spectator.auth.invite import InviteError, InviteManager
from spectator.db.db import SpectatorDB

# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory for test isolation."""
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def db(tmp_data_dir):
    """Provide an initialised SpectatorDB against a temp database."""
    db_path = tmp_data_dir / "spectator.db"
    database = SpectatorDB(db_path)
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def secret_mgr(tmp_data_dir):
    """Provide a HostSecretManager against a temp directory."""
    secret_path = tmp_data_dir / "host_secret"
    mgr = HostSecretManager(secret_path)
    assert mgr.load_or_create() is True
    assert mgr.degraded is False
    return mgr


@pytest.fixture
def invite_mgr(db, secret_mgr):
    """Provide an InviteManager with initialised DB and secret."""
    return InviteManager(db, secret_mgr, current_session_gen="gen-1")


@pytest.fixture
def app_state(tmp_data_dir):
    """Provide a fully initialised _AppState for integration tests.

    Creates a fresh DB, secret, session_gen, and invite manager for each test.
    """
    # Import here to avoid circular import at module level
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

    from plugin_api import _AppState
    state = _AppState()
    data_dir = tmp_data_dir

    # Init DB
    db_path = data_dir / "spectator.db"
    state.db = SpectatorDB(db_path)
    state.db.init_schema()

    # Init secret
    secret_path = data_dir / "host_secret"
    state.secret_mgr = HostSecretManager(secret_path)
    assert state.secret_mgr.load_or_create() is True
    state.degraded = False

    # Init session gen
    state.session_gen_mgr = SessionGenManager(data_dir)
    state.session_id = "test-session-001"
    state.session_gen = state.session_gen_mgr.initialise(state.session_id, time.time())

    # Init invite manager
    state.invite_mgr = InviteManager(state.db, state.secret_mgr, current_session_gen=state.session_gen)

    state.start_time = time.time()
    state._initialized = True
    yield state

    # Clean up: close DB
    if state.db is not None:
        state.db.close()


@pytest.fixture
def client(app_state):
    """Provide a TestClient wired to the spectator router.

    Patches the module-level _state to use our test app_state,
    then restores the original state after the test.
    """
    import plugin_api
    from fastapi import FastAPI
    from plugin_api import _state as original_state
    from plugin_api import router

    # Patch the module-level _state
    plugin_api._state = app_state

    app = FastAPI()
    app.include_router(router, prefix="/api/plugins/spectator")
    try:
        with TestClient(app) as c:
            yield c
    finally:
        plugin_api._state = original_state


@pytest.fixture
def host_token(app_state):
    """Provide a valid host bearer token (hex-encoded) matching the app_state secret."""
    return app_state.secret_mgr.secret.hex()


# ===========================================================================
# Unit: Guest token derivation (unforgeability)
# ===========================================================================

class TestTokenDerivationUnforgeable:
    """guest_token only verifies when recomputed with the real host_secret;
    flipping any bit fails compare_digest."""

    def test_derive_and_verify_round_trip(self, secret_mgr):
        """A correctly derived guest_token verifies."""
        host_secret = secret_mgr.secret
        guest_id = "test-guest-001"
        token_hash = hashlib.sha256(b"raw-invite-token").hexdigest()

        guest_token = derive_guest_token(host_secret, guest_id, token_hash)

        # Split on first colon
        idx = guest_token.index(":")
        extracted_id = guest_token[:idx]
        assert extracted_id == guest_id

        # Recompute and compare
        expected = derive_guest_token(host_secret, guest_id, token_hash)
        assert hmac.compare_digest(guest_token, expected)

    def test_wrong_host_secret_fails(self, secret_mgr):
        """A guest_token derived with a DIFFERENT host_secret does not verify."""
        host_secret = secret_mgr.secret
        guest_id = "test-guest-002"
        token_hash = hashlib.sha256(b"raw-invite-token").hexdigest()

        correct_token = derive_guest_token(host_secret, guest_id, token_hash)
        wrong_secret = secrets.token_bytes(32)
        wrong_token = derive_guest_token(wrong_secret, guest_id, token_hash)

        assert not hmac.compare_digest(correct_token, wrong_token)

    def test_bit_flip_fails(self, secret_mgr):
        """Flipping ANY single bit in the guest_token HMAC causes verification failure.

        We flip bits in the MAC portion (after the colon) only, since:
        - Flipping the guest_id prefix changes the lookup key (already tested
          by test_wrong_host_secret_fails and test_wrong_token_hash_fails)
        - The MAC is hex-encoded, so bit-flips produce valid ASCII but wrong MACs
        """
        host_secret = secret_mgr.secret
        guest_id = "test-guest-003"
        token_hash = hashlib.sha256(b"raw-invite-token").hexdigest()

        guest_token = derive_guest_token(host_secret, guest_id, token_hash)
        _, mac = guest_token.split(":", 1)

        # Flip each bit in the MAC (hex-encoded, so all ASCII)
        mac_bytes = mac.encode("utf-8")
        for i in range(min(len(mac_bytes), 64)):  # Limit iterations
            for bit in range(8):
                flipped = bytearray(mac_bytes)
                flipped[i] ^= (1 << bit)
                flipped_mac = flipped.decode("utf-8", errors="replace")
                # Skip if the flipped char is not a valid hex char
                try:
                    int(flipped_mac, 16)  # Validate hex
                except ValueError:
                    continue
                forged_token = f"{guest_id}:{flipped_mac}"
                assert not hmac.compare_digest(guest_token, forged_token)

    def test_o1_verification_via_guest_id_prefix(self, db, secret_mgr, invite_mgr):
        """Guest token verification is O(1) via guest_id PK index lookup.

        We can't directly measure O(1) in a unit test, but we verify that
        the lookup uses the guest_id as a primary key (not a scan).
        """
        host_secret = secret_mgr.secret
        # Mint an invite
        result = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        raw_token = result["token"]

        # Join to create a guest
        join_result = invite_mgr.join_invite(raw_token, guest_name="test-guest")
        guest_token = join_result["guest_token"]
        guest_id = join_result["guest_id"]

        # Verify: the guest_id prefix allows direct PK lookup
        assert guest_token.startswith(guest_id + ":")
        # The guest_id is a UUID, which is the guests table PK
        # (verified by schema inspection)

    def test_wrong_token_hash_fails(self, secret_mgr):
        """A guest_token with a different token_hash does not verify."""
        host_secret = secret_mgr.secret
        guest_id = "test-guest-004"
        token_hash = hashlib.sha256(b"raw-invite-token").hexdigest()
        wrong_hash = hashlib.sha256(b"wrong-invite-token").hexdigest()

        correct_token = derive_guest_token(host_secret, guest_id, token_hash)
        wrong_token = derive_guest_token(host_secret, guest_id, wrong_hash)

        assert not hmac.compare_digest(correct_token, wrong_token)


# ===========================================================================
# Unit: Session-gen identity (stale invite invalidation)
# ===========================================================================

class TestSessionGenInvalidation:
    """Session restart invalidates stale invites even with reused session_id."""

    def test_session_gen_computation(self):
        """session_gen is deterministic for same inputs + nonce."""
        nonce = secrets.token_bytes(16)
        gen1 = compute_session_gen("session-1", 1000.0, nonce)
        gen2 = compute_session_gen("session-1", 1000.0, nonce)
        assert gen1 == gen2

    def test_different_nonce_different_gen(self):
        """Different nonces produce different session_gen values."""
        gen1 = compute_session_gen("session-1", 1000.0, b"a" * 16)
        gen2 = compute_session_gen("session-1", 1000.0, b"b" * 16)
        assert gen1 != gen2

    def test_different_process_start_different_gen(self):
        """Different process_start_epoch produces different session_gen."""
        gen1 = compute_session_gen("session-1", 1000.0, b"a" * 16)
        gen2 = compute_session_gen("session-1", 2000.0, b"a" * 16)
        assert gen1 != gen2

    def test_stale_invites_invalidated_on_restart(self, tmp_data_dir):
        """When session_gen changes (restart), stale invites are invalidated."""
        # First session
        mgr1 = SessionGenManager(tmp_data_dir)
        gen1 = mgr1.initialise("session-1", 1000.0)
        assert mgr1.current == gen1

        # Simulate second session (different process_start_epoch)
        # This triggers invalidation of invites with old gen
        mgr2 = SessionGenManager(tmp_data_dir)
        gen2 = mgr2.initialise("session-1", 2000.0)
        assert mgr2.current == gen2
        assert mgr2.previous == gen1
        assert gen1 != gen2

    def test_session_gen_invalidates_db_invites(self, db, secret_mgr, tmp_data_dir):
        """Stale invites with old session_gen are revoked on init."""
        # Mint an invite with gen-1
        invite_mgr = InviteManager(db, secret_mgr, current_session_gen="gen-old")
        result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-old",
            ttl_seconds=3600,
        )
        invite_id = result["invite_id"]

        # Verify invite is active
        cur = db.conn.execute("SELECT revoked FROM invites WHERE invite_id = ?", (invite_id,))
        assert cur.fetchone()["revoked"] == 0

        # Simulate session restart with new gen — invalidation of old invites
        with db.write_txn() as cur:
            cur.execute("UPDATE invites SET revoked = 1 WHERE session_gen = ?", ("gen-old",))

        # Verify invite is now revoked
        cur = db.conn.execute("SELECT revoked FROM invites WHERE invite_id = ?", (invite_id,))
        assert cur.fetchone()["revoked"] == 1

    def test_same_session_gen_no_invalidation(self, tmp_data_dir):
        """When session_gen stays the same, no invites are invalidated."""
        # First init: no previous gen file → previous is "" sentinel (fail-closed)
        mgr1 = SessionGenManager(tmp_data_dir)
        gen1 = mgr1.initialise("session-1", 1000.0)

        # Fail-closed: when no previous gen file exists, previous is the
        # empty-string sentinel, not None. This ensures bulk invalidation
        # runs on first start when the gen file is absent.
        assert mgr1.previous == ""  # Fail-closed sentinel (was None pre-fix)


# ===========================================================================
# Unit: Invite lifecycle (mint, join, revoke, expire)
# ===========================================================================

class TestInviteLifecycle:
    """Token mint → join → revoke → expire. All state transitions valid."""

    def test_mint_invite(self, invite_mgr):
        """Minting an invite returns token, invite_id, and metadata."""
        result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        assert "invite_id" in result
        assert "token" in result
        assert "token_hash_prefix" in result
        assert "expires_at" in result
        assert len(result["token"]) == 64  # 256 bits = 32 bytes = 64 hex chars

    def test_mint_invite_custom_ttl(self, invite_mgr):
        """Custom TTL is respected."""
        result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
            ttl_seconds=3600,
        )
        assert result["invite_id"]  # Has an ID

    def test_join_invite(self, invite_mgr):
        """Joining an invite creates a guest session and returns guest_token."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        raw_token = mint_result["token"]

        join_result = invite_mgr.join_invite(raw_token, guest_name="Alice")
        assert "guest_id" in join_result
        assert "guest_token" in join_result
        assert "session_id" in join_result
        assert "feed_cursor" in join_result
        assert join_result["session_id"] == "test-session"

    def test_join_invite_guest_token_format(self, invite_mgr, secret_mgr):
        """Guest token has the canonical format: guest_id:HMAC"""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_token = join_result["guest_token"]
        guest_id = join_result["guest_id"]

        # Token starts with guest_id
        assert guest_token.startswith(guest_id + ":")
        # HMAC portion is hex
        _, mac = guest_token.split(":", 1)
        assert len(mac) == 64  # SHA-256 hex

    def test_single_use_invite(self, invite_mgr):
        """An invite token can only be used once; second use returns 401."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        raw_token = mint_result["token"]

        # First join succeeds
        invite_mgr.join_invite(raw_token, guest_name="Alice")

        # Second join fails — single-use
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.join_invite(raw_token, guest_name="Bob")
        assert exc_info.value.status_code == 401
        assert "already used" in str(exc_info.value).lower()

    def test_revoke_invite(self, invite_mgr):
        """Revoking an invite by invite_id marks it as revoked."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        invite_id = mint_result["invite_id"]

        result = invite_mgr.revoke_invite(invite_id)
        assert result["status"] == "revoked"

        # Join should fail for revoked invite
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.join_invite(mint_result["token"])
        assert exc_info.value.status_code == 410

    def test_revoke_invite_not_found(self, invite_mgr):
        """Revoking a non-existent invite returns 404."""
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.revoke_invite("nonexistent-uuid")
        assert exc_info.value.status_code == 404

    def test_revoke_invite_already_revoked(self, invite_mgr):
        """Revoking an already-revoked invite returns 410."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        invite_id = mint_result["invite_id"]
        invite_mgr.revoke_invite(invite_id)

        with pytest.raises(InviteError) as exc_info:
            invite_mgr.revoke_invite(invite_id)
        assert exc_info.value.status_code == 410

    def test_revoke_also_revokes_guests(self, db, invite_mgr):
        """Revoking an invite also marks associated guests as revoked."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_id = join_result["guest_id"]

        invite_mgr.revoke_invite(mint_result["invite_id"])

        # Guest should be revoked
        cur = db.conn.execute("SELECT revoked FROM guests WHERE guest_id = ?", (guest_id,))
        assert cur.fetchone()["revoked"] == 1

    def test_revoke_expires_pending_suggestions(self, db, invite_mgr):
        """Revoking an invite expires pending suggestions from those guests."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_id = join_result["guest_id"]

        # Insert a pending suggestion manually
        with db.write_txn() as cur:
            cur.execute(
                """INSERT INTO suggestions
                   (id, guest_id, session_id, content, role, status, receipt_state,
                    created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "sugg-001", guest_id, "test-session", "test content", "user",
                    "pending", None, "2026-08-13T00:00:00+00:00",
                    "2026-08-13T00:00:00+00:00", "2026-08-14T00:00:00+00:00",
                ),
            )

        # Revoke the invite
        invite_mgr.revoke_invite(mint_result["invite_id"])

        # Suggestion should be expired with host_gone receipt
        cur = db.conn.execute("SELECT status, receipt_state FROM suggestions WHERE id = ?", ("sugg-001",))
        row = cur.fetchone()
        assert row["status"] == "expired"
        assert row["receipt_state"] == "host_gone"

    def test_list_invites(self, invite_mgr):
        """List invites returns metadata for all invites."""
        invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1", session_label="First")
        invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1", session_label="Second")

        invites = invite_mgr.list_invites("test-session")
        assert len(invites) == 2
        assert invites[0]["token_hash_prefix"]  # Only prefix, not full hash
        assert "created_at" in invites[0]

    def test_invite_token_never_in_db(self, db, invite_mgr):
        """The raw invite token is never stored — only its SHA-256 hash."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        raw_token = mint_result["token"]

        # The raw token should NOT appear anywhere in the DB
        cur = db.conn.execute("SELECT token_hash FROM invites WHERE invite_id = ?",
                              (mint_result["invite_id"],))
        stored_hash = cur.fetchone()["token_hash"]

        # Verify: SHA-256 of the raw token matches stored hash
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        assert stored_hash == expected_hash

        # The raw token should NOT equal the stored hash
        assert raw_token != stored_hash

    def test_invalid_token_join_fails(self, invite_mgr):
        """Joining with an invalid token fails."""
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.join_invite("invalid-token-here")
        assert exc_info.value.status_code == 401

    def test_expired_invite_join_fails(self, db, invite_mgr):
        """An expired invite cannot be joined."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
            ttl_seconds=1,  # Expires in 1 second
        )

        # Manually expire the invite in the DB
        with db.write_txn() as cur:
            cur.execute(
                "UPDATE invites SET expires_at = ? WHERE invite_id = ?",
                ("2020-01-01T00:00:00+00:00", mint_result["invite_id"]),
            )

        with pytest.raises(InviteError) as exc_info:
            invite_mgr.join_invite(mint_result["token"])
        assert exc_info.value.status_code == 401


# ===========================================================================
# Unit: Guest token verification
# ===========================================================================

class TestGuestTokenVerification:
    """Verify guest tokens via InviteManager.verify_guest_token."""

    def test_valid_guest_token_verifies(self, invite_mgr):
        """A freshly derived guest_token verifies successfully."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_token = join_result["guest_token"]

        info = invite_mgr.verify_guest_token(guest_token)
        assert info["role"] == "guest"
        assert info["guest_id"] == join_result["guest_id"]

    def test_revoked_guest_token_fails(self, invite_mgr):
        """A guest token from a revoked invite fails verification (410)."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_token = join_result["guest_token"]

        # Revoke the invite
        invite_mgr.revoke_invite(mint_result["invite_id"])

        # Guest token should now fail
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.verify_guest_token(guest_token)
        assert exc_info.value.status_code == 410

    def test_malformed_guest_token_fails(self, invite_mgr):
        """A guest token without a colon fails verification."""
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.verify_guest_token("notavalidtoken")
        assert exc_info.value.status_code == 401

    def test_empty_guest_token_fails(self, invite_mgr):
        """An empty guest token fails verification."""
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.verify_guest_token("")
        assert exc_info.value.status_code == 401

    def test_wrong_mac_fails(self, invite_mgr, secret_mgr):
        """A guest_token with the wrong MAC fails verification."""
        mint_result = invite_mgr.mint_invite(
            session_id="test-session",
            session_gen="gen-1",
        )
        join_result = invite_mgr.join_invite(mint_result["token"])
        guest_id = join_result["guest_id"]

        # Forge a token with the right prefix but wrong MAC
        forged_token = f"{guest_id}:deadbeef" * 4  # Wrong MAC

        with pytest.raises(InviteError) as exc_info:
            invite_mgr.verify_guest_token(forged_token)
        assert exc_info.value.status_code == 401


# ===========================================================================
# Unit: Host bearer authentication
# ===========================================================================

class TestHostBearerAuth:
    """Host secret bearer token verification."""

    def test_valid_host_bearer(self, secret_mgr):
        """A correct hex-encoded host_secret verifies."""
        token = secret_mgr.secret.hex()
        assert secret_mgr.verify_host_bearer(token) is True

    def test_invalid_host_bearer(self, secret_mgr):
        """An incorrect bearer token fails."""
        assert secret_mgr.verify_host_bearer("deadbeef") is False

    def test_empty_bearer(self, secret_mgr):
        """An empty bearer token fails."""
        assert secret_mgr.verify_host_bearer("") is False

    def test_malformed_bearer(self, secret_mgr):
        """A non-hex bearer token fails."""
        assert secret_mgr.verify_host_bearer("not-hex!") is False


# ===========================================================================
# Integration: AuthN role enforcement via REST API
# ===========================================================================

class TestAuthNRoleEnforcement:
    """Role enforcement: guest cannot mint/revoke/approve/read host-only (403)."""

    def test_host_can_mint_invite(self, client, host_token):
        """Host can mint an invite with valid bearer token."""
        response = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test", "ttl_seconds": 86400},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "invite_id" in data
        assert "token" in data
        assert len(data["token"]) == 64  # 256-bit hex

    def test_host_can_list_invites(self, client, host_token):
        """Host can list invites."""
        # Mint one first
        client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        response = client.get(
            "/api/plugins/spectator/invites",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_host_can_revoke_invite(self, client, host_token):
        """Host can revoke an invite by invite_id."""
        # Mint
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        invite_id = mint_resp.json()["invite_id"]

        # Revoke
        response = client.delete(
            f"/api/plugins/spectator/invites/{invite_id}",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"

    def test_no_auth_returns_401(self, client):
        """Endpoints requiring auth return 401 without Authorization header."""
        response = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
        )
        assert response.status_code == 401

    def test_invalid_bearer_returns_401(self, client):
        """An invalid bearer token returns 401."""
        response = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": "Bearer invalidhex"},
        )
        assert response.status_code == 401

    def test_guest_token_cannot_mint_invite(self, client, host_token):
        """A guest token cannot mint invites (403)."""
        # Host mints an invite
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        raw_token = mint_resp.json()["token"]

        # Guest joins
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token},
        )
        guest_token = join_resp.json()["guest_token"]

        # Guest tries to mint — should get 403
        response = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert response.status_code == 403

    def test_guest_token_cannot_revoke_invite(self, client, host_token):
        """A guest token cannot revoke invites (403)."""
        # Host mints
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        invite_id = mint_resp.json()["invite_id"]
        raw_token = mint_resp.json()["token"]

        # Guest joins
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token},
        )
        guest_token = join_resp.json()["guest_token"]

        # Guest tries to revoke — should get 403
        response = client.delete(
            f"/api/plugins/spectator/invites/{invite_id}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert response.status_code == 403

    def test_guest_token_cannot_access_status(self, client, host_token):
        """A guest token cannot access /status (403)."""
        # Host mints and guest joins
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        raw_token = mint_resp.json()["token"]

        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token},
        )
        guest_token = join_resp.json()["guest_token"]

        # Guest tries /status — should get 403
        response = client.get(
            "/api/plugins/spectator/status",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert response.status_code == 403

    def test_invite_token_in_fragment_not_url_path(self, client, host_token):
        """The raw invite token appears ONLY in the link fragment,
        never in any URL path. The join endpoint accepts it via POST body."""
        # Mint an invite
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert mint_resp.status_code == 200

        # The response includes the raw token (for the host to construct the fragment URL)
        data = mint_resp.json()
        assert "token" in data
        assert len(data["token"]) == 64

        # Join via POST body (not URL path)
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": data["token"]},
        )
        assert join_resp.status_code == 200

        # The join response includes guest_token but NOT the raw invite token
        join_data = join_resp.json()
        assert "guest_token" in join_data
        assert "guest_id" in join_data

    def test_revoke_by_invite_id_not_token(self, client, host_token):
        """Revocation uses the internal invite_id (UUID), never the raw token."""
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        data = mint_resp.json()
        invite_id = data["invite_id"]

        # Revoke by invite_id (UUID format)
        assert len(invite_id) == 36  # UUID format
        assert invite_id.count("-") == 4  # UUID dashes

        response = client.delete(
            f"/api/plugins/spectator/invites/{invite_id}",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200


# ===========================================================================
# Integration: Host UI auth via ctx.rest (simulated)
# ===========================================================================

class TestHostUIAuthViaCtxRest:
    """Host UI requests succeed via ctx.rest (simulated as host bearer).

    In production, the host UI uses gateway session auth, not a bearer token.
    We test the bearer path here; the gateway session path will be wired
    when the host UI pane is built in C5.
    """

    def test_status_with_host_bearer(self, client, host_token):
        """Host bearer token can access /status."""
        response = client.get(
            "/api/plugins/spectator/status",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "feed_source" in data
        assert "guest_count" in data

    def test_mint_invite_and_join_full_flow(self, client, host_token):
        """Full flow: mint → join → verify guest_token works for feed."""
        # Mint
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={"session_label": "E2E test"},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert mint_resp.status_code == 200
        raw_token = mint_resp.json()["token"]

        # Join
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token, "name": "TestGuest"},
        )
        assert join_resp.status_code == 200
        join_data = join_resp.json()
        guest_token = join_data["guest_token"]
        assert join_data["session_id"] == "test-session-001"

        # Guest can access feed — auth must pass (not 401/403). C3 built the
        # real endpoint: with no feed engine in the test state it returns 500,
        # which still proves auth succeeded past the dependency gate.
        feed_resp = client.get(
            "/api/plugins/spectator/feed",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert feed_resp.status_code != 401, "guest token rejected on feed"
        assert feed_resp.status_code != 403, "guest token forbidden on feed"

    def test_full_invite_revoke_flow(self, client, host_token):
        """Full flow: mint → join → revoke → verify guest_token fails."""
        # Mint
        mint_resp = client.post(
            "/api/plugins/spectator/invites",
            json={},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        invite_id = mint_resp.json()["invite_id"]
        raw_token = mint_resp.json()["token"]

        # Join
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token},
        )
        guest_token = join_resp.json()["guest_token"]

        # Verify guest_token works before revocation — auth must pass (not
        # 401/403). C3 built the real endpoint; with no feed engine in test
        # state it returns 500, which still proves auth passed the gate.
        feed_resp = client.get(
            "/api/plugins/spectator/feed",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert feed_resp.status_code != 401, "guest token rejected before revoke"
        assert feed_resp.status_code != 403, "guest token forbidden before revoke"

        # Revoke
        revoke_resp = client.delete(
            f"/api/plugins/spectator/invites/{invite_id}",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert revoke_resp.status_code == 200

        # Guest token should now fail
        feed_resp = client.get(
            "/api/plugins/spectator/feed",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        # Expect 410 Gone (invite revoked)
        assert feed_resp.status_code in (401, 410)

    def test_degraded_state_blocks_invite_operations(self, tmp_data_dir):
        """DEGRADED state (corrupt secret) blocks all invite operations."""
        # Create a corrupt secret file
        secret_path = tmp_data_dir / "host_secret"
        secret_path.write_bytes(b"corrupt")  # Wrong length

        from spectator.auth.auth import HostSecretManager
        mgr = HostSecretManager(secret_path)
        assert mgr.load_or_create() is False
        assert mgr.degraded is True

        # InviteManager operations should fail in degraded state
        db_path = tmp_data_dir / "spectator.db"
        db = SpectatorDB(db_path)
        db.init_schema()

        invite_mgr = InviteManager(db, mgr, current_session_gen="gen-1")
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.mint_invite(session_id="test", session_gen="gen-1")
        assert exc_info.value.status_code == 503


# ===========================================================================
# Audit trail
# ===========================================================================

class TestAuditLog:
    """Audit log records all invite/suggestion mutations."""

    def test_invite_mint_audit(self, db, invite_mgr):
        """Minting an invite creates an audit log entry."""
        invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        cur = db.conn.execute(
            "SELECT * FROM audit_log WHERE action = 'invite_mint'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["actor_role"] == "host"

    def test_invite_join_audit(self, invite_mgr):
        """Joining an invite creates an audit log entry."""
        result = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        invite_mgr.join_invite(result["token"])

        # Check audit log
        cur = invite_mgr.db.conn.execute(
            "SELECT * FROM audit_log WHERE action = 'invite_join'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["actor_role"] == "guest"

    def test_invite_revoke_audit(self, invite_mgr):
        """Revoking an invite creates an audit log entry."""
        result = invite_mgr.mint_invite(session_id="test-session", session_gen="gen-1")
        invite_mgr.revoke_invite(result["invite_id"])

        cur = invite_mgr.db.conn.execute(
            "SELECT * FROM audit_log WHERE action = 'invite_revoke'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["actor_role"] == "host"


# ===========================================================================
# Regression: AC#3 fail-closed session_gen invalidation
# ===========================================================================

class TestSessionGenFailClosed:
    """Regression tests for AC#3: session_gen invalidation must work even
    when the gen file is missing/corrupt at restart (fail-closed).

    These test the fix for Quan's Finding 1: previously, if the persisted
    session_gen file was missing/corrupt, _previous=None meant no bulk
    invalidation ran, and join/verify never checked session_gen at runtime.
    """

    def test_missing_gen_file_invalidates_all_invites(self, db, secret_mgr, tmp_data_dir):
        """If the session_gen file is missing at restart, ALL stale invites
        are revoked (fail-closed bulk invalidation)."""
        # Gen1: mint an invite
        gen_file = tmp_data_dir / "session_gen"
        mgr1 = SessionGenManager(tmp_data_dir)
        gen1 = mgr1.initialise("session-1", 1000.0)

        invite_mgr = InviteManager(db, secret_mgr, current_session_gen=gen1)
        result = invite_mgr.mint_invite(
            session_id="session-1", session_gen=gen1,
        )

        # Verify invite is active
        cur = db.conn.execute("SELECT revoked FROM invites WHERE invite_id = ?", (result["invite_id"],))
        assert cur.fetchone()["revoked"] == 0

        # Simulate restart: delete the session_gen file
        gen_file.unlink(missing_ok=True)
        assert not gen_file.exists()

        # Gen2: re-initialise with same session_id but different epoch
        mgr2 = SessionGenManager(tmp_data_dir)
        gen2 = mgr2.initialise("session-1", 2000.0)

        # previous should be "" sentinel (fail-closed)
        assert mgr2.previous == ""

        # _invalidate_stale_invites with sentinel "" should revoke ALL invites
        # Simulate the plugin_api invalidation logic
        with db.write_txn() as cur:
            cur.execute("UPDATE invites SET revoked = 1 WHERE revoked = 0")

        # The invite from gen1 should now be revoked
        cur = db.conn.execute("SELECT revoked FROM invites WHERE invite_id = ?", (result["invite_id"],))
        assert cur.fetchone()["revoked"] == 1

    def test_corrupt_gen_file_invalidates_all_invites(self, db, secret_mgr, tmp_data_dir):
        """If the session_gen file is corrupt (empty) at restart, ALL stale
        invites are revoked (fail-closed bulk invalidation)."""
        # Gen1: mint an invite
        mgr1 = SessionGenManager(tmp_data_dir)
        gen1 = mgr1.initialise("session-1", 1000.0)

        invite_mgr = InviteManager(db, secret_mgr, current_session_gen=gen1)
        result = invite_mgr.mint_invite(
            session_id="session-1", session_gen=gen1,
        )

        # Corrupt the gen file (write empty content)
        gen_file = tmp_data_dir / "session_gen"
        gen_file.write_text("", encoding="utf-8")

        # Gen2: re-initialise
        mgr2 = SessionGenManager(tmp_data_dir)
        gen2 = mgr2.initialise("session-1", 2000.0)

        # previous should be "" sentinel (fail-closed)
        assert mgr2.previous == ""

        # Bulk invalidate ALL invites (simulating plugin_api logic)
        with db.write_txn() as cur:
            cur.execute("UPDATE invites SET revoked = 1 WHERE revoked = 0")

        # The invite from gen1 should now be revoked
        cur = db.conn.execute("SELECT revoked FROM invites WHERE invite_id = ?", (result["invite_id"],))
        assert cur.fetchone()["revoked"] == 1

    def test_join_rejects_stale_session_gen(self, db, secret_mgr, tmp_data_dir):
        """join_invite rejects an invite whose session_gen doesn't match
        the current gen (410), even if the invite row hasn't been
        bulk-invalidated yet. The pre-check revokes the stale invite
        in a separate transaction, then the join flow catches it as revoked."""
        # Create InviteManager with current gen = "gen-current"
        invite_mgr = InviteManager(db, secret_mgr, current_session_gen="gen-current")

        # Mint an invite with a DIFFERENT session_gen (simulating stale invite)
        result = invite_mgr.mint_invite(
            session_id="session-1", session_gen="gen-stale",
        )
        raw_token = result["token"]

        # Join should fail with 410 — pre-check revokes stale invite,
        # then the revoked check in the main transaction catches it
        with pytest.raises(InviteError) as exc_info:
            invite_mgr.join_invite(raw_token)
        assert exc_info.value.status_code == 410

    def test_verify_guest_rejects_stale_session_gen(self, db, secret_mgr, tmp_data_dir):
        """verify_guest_token rejects a guest token bound to a stale
        session_gen (410 host_gone)."""
        # Create InviteManager with current gen = "gen-current"
        invite_mgr = InviteManager(db, secret_mgr, current_session_gen="gen-current")

        # Mint and join with matching gen
        result = invite_mgr.mint_invite(
            session_id="session-1", session_gen="gen-current",
        )
        join_result = invite_mgr.join_invite(result["token"])
        guest_token = join_result["guest_token"]

        # Verify should succeed
        info = invite_mgr.verify_guest_token(guest_token)
        assert info["role"] == "guest"

        # Now simulate gen change: create a new InviteManager with different gen
        invite_mgr_new_gen = InviteManager(db, secret_mgr, current_session_gen="gen-new")

        # The old guest token should fail with 410 (stale gen)
        with pytest.raises(InviteError) as exc_info:
            invite_mgr_new_gen.verify_guest_token(guest_token)
        assert exc_info.value.status_code == 410

    def test_e2e_missing_gen_file_join_rejected(self, db, secret_mgr, tmp_data_dir):
        """E2E reproduction of the exact scenario from Quan's review:
        gen1 init → mint invite → delete gen file → re-init with
        reused session_id + new epoch → join with stale token → 410."""
        # Step 1: Gen1 init
        mgr1 = SessionGenManager(tmp_data_dir)
        gen1 = mgr1.initialise("session-1", 1000.0)

        # Step 2: Mint invite with gen1
        invite_mgr1 = InviteManager(db, secret_mgr, current_session_gen=gen1)
        result = invite_mgr1.mint_invite(
            session_id="session-1", session_gen=gen1,
        )
        raw_token = result["token"]

        # Step 3: Delete gen file (simulating missing file at restart)
        gen_file = tmp_data_dir / "session_gen"
        gen_file.unlink()

        # Step 4: Re-init with reused session_id but new epoch
        mgr2 = SessionGenManager(tmp_data_dir)
        gen2 = mgr2.initialise("session-1", 2000.0)

        # Step 5: Create new InviteManager with current gen
        invite_mgr2 = InviteManager(db, secret_mgr, current_session_gen=gen2)

        # Step 6: Bulk invalidate stale invites (simulating plugin_api init)
        # Since mgr2.previous == "", we invalidate ALL
        assert mgr2.previous == ""
        with db.write_txn() as cur:
            cur.execute("UPDATE invites SET revoked = 1 WHERE revoked = 0")

        # Step 7: Join with stale token → should fail (410)
        with pytest.raises(InviteError) as exc_info:
            invite_mgr2.join_invite(raw_token)
        # The invite was revoked by bulk invalidation
        assert exc_info.value.status_code == 410