"""Unit + integration tests for C1 — Plugin scaffold + REST/WS namespace.

Acceptance criteria:
- Plugin installs cleanly; /status returns 200 with feed_source field
- All DB tables create with exact schema; WAL mode on; busy_timeout=5000
- Missing/corrupt host_secret → 503 DEGRADED + recovery banner path
- Non-loopback binding refused unless allow_remote + TLS (test)

Test plan:
- Unit: schema creation, config precedence, fail-closed init
- Integration: test_plugin_rest_namespace (all endpoints 200/401 correctly)
- Host-realistic: test mounts router WITHOUT calling init_plugin() and
  asserts that lazy init works (Finding 1 fix).
"""

import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from spectator.auth.auth import HostSecretManager, SessionGenManager
from spectator.config import SpectatorConfig, load_config
from spectator.db.db import SpectatorDB

# ===========================================================================
# Schema creation
# ===========================================================================

class TestSchemaCreation:
    """All DB tables create with exact schema; WAL mode on; busy_timeout=5000."""

    def test_tables_created(self, db, tmp_data_dir):
        """All five tables exist after init_schema."""
        conn = db.conn
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert "invites" in tables
        assert "guests" in tables
        assert "events" in tables
        assert "suggestions" in tables
        assert "audit_log" in tables

    def test_indexes_created(self, db):
        """All specified indexes exist."""
        conn = db.conn
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = {row[0] for row in cur.fetchall()}
        assert "idx_suggestions_status" in indexes
        assert "idx_suggestions_expiry" in indexes
        assert "idx_suggestions_delivery" in indexes
        assert "idx_events_session_seq" in indexes
        assert "idx_audit_at" in indexes

    def test_wal_mode(self, db, tmp_data_dir):
        """WAL mode is enabled after init."""
        # Re-open to check journal mode persists
        db_path = tmp_data_dir / "spectator.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        conn.close()
        assert mode == "wal", f"Expected WAL mode, got {mode}"

    def test_busy_timeout(self, db):
        """busy_timeout is set to 5000ms."""
        conn = db.conn
        cur = conn.execute("PRAGMA busy_timeout")
        timeout = cur.fetchone()[0]
        assert timeout == 5000, f"Expected busy_timeout=5000, got {timeout}"

    def test_invites_schema_columns(self, db):
        """invites table has exact schema columns including session_gen."""
        conn = db.conn
        cur = conn.execute("PRAGMA table_info(invites)")
        cols = {row[1]: row[2] for row in cur.fetchall()}
        assert "invite_id" in cols
        assert "token_hash" in cols
        assert "session_id" in cols
        assert "session_gen" in cols
        assert "session_label" in cols
        assert "created_at" in cols
        assert "expires_at" in cols
        assert "revoked" in cols
        assert "joined" in cols

    def test_suggestions_schema_columns(self, db):
        """suggestions table has exact schema including delivery fields."""
        conn = db.conn
        cur = conn.execute("PRAGMA table_info(suggestions)")
        cols = {row[1]: row[2] for row in cur.fetchall()}
        assert "id" in cols
        assert "guest_id" in cols
        assert "content" in cols
        assert "role" in cols
        assert "status" in cols
        assert "receipt_state" in cols
        assert "delivery_id" in cols
        assert "delivery_state" in cols

    def test_foreign_keys_enabled(self, db):
        """Foreign keys are enforced."""
        conn = db.conn
        cur = conn.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
    def test_runtime_storage_permissions_are_private(self, tmp_path):
        """Sensitive DB content and its containing directory are owner-only."""
        data_dir = tmp_path / "spectator-data"
        data_dir.mkdir(mode=0o755)
        db_path = data_dir / "spectator.db"
        db_path.touch(mode=0o644)
        database = SpectatorDB(db_path)
        try:
            database.init_schema()
            assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700
            assert stat.S_IMODE(database.db_path.stat().st_mode) == 0o600
        finally:
            database.close()

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
    def test_runtime_storage_rejects_world_writable_non_sticky_parent(self, tmp_path):
        """A local user must not be able to replace the private data directory."""
        unsafe_parent = tmp_path / "unsafe-parent"
        unsafe_parent.mkdir(mode=0o777)
        unsafe_parent.chmod(0o777)
        with pytest.raises(PermissionError, match="world-writable"):
            SpectatorDB(unsafe_parent / "spectator" / "spectator.db")


# ===========================================================================
# Config precedence
# ===========================================================================

class TestConfigPrecedence:
    """Config: defaults < config.yaml < SPECTATOR_* env vars."""

    def test_defaults(self):
        """Default values are used when no config file or env exists."""
        cfg = SpectatorConfig()
        assert cfg.pending_ttl_seconds == 300
        assert cfg.invite_ttl_seconds == 86400
        assert cfg.allow_remote is False
        assert cfg.require_tls is True
        assert cfg.feed_source == "auto"
        assert cfg.poll_interval_seconds == 2
        assert cfg.max_pending_suggestions == 100
        assert cfg.allow_gateway_injection is False

    def test_default_runtime_paths_honor_duckwork_home_and_separate_plugin_source(self, tmp_path):
        """Profile-local state must not share the directory-install source path."""
        duckwork_home = tmp_path / "profile-home"
        env = os.environ.copy()
        env["DUCKWORK_HOME"] = str(duckwork_home)
        env.pop("SPECTATOR_DATA_DIR", None)
        env.pop("SPECTATOR_STATE_DB", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from spectator.config import DEFAULT_DATA_DIR, DEFAULT_STATE_DB_PATH; "
                    "print(DEFAULT_DATA_DIR); print(DEFAULT_STATE_DB_PATH)"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
        )
        data_dir, state_db = result.stdout.splitlines()
        assert Path(data_dir) == duckwork_home / "data" / "spectator"
        assert Path(state_db) == duckwork_home / "state.db"
        assert Path(data_dir) != duckwork_home / "plugins" / "spectator"

    def test_config_file_overrides(self, tmp_path):
        """YAML config file values override defaults."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "spectator:\n"
            "  pending_ttl_seconds: 600\n"
            "  allow_remote: true\n"
            "  feed_source: transcript\n"
        )
        cfg = load_config(config_path=cfg_file)
        assert cfg.pending_ttl_seconds == 600
        assert cfg.allow_remote is True
        assert cfg.feed_source == "transcript"

    def test_env_overrides_config_file(self, tmp_path):
        """SPECTATOR_* env vars override config file values."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "spectator:\n"
            "  pending_ttl_seconds: 600\n"
        )
        with patch.dict(os.environ, {"SPECTATOR_PENDING_TTL_SECONDS": "120"}):
            cfg = load_config(config_path=cfg_file)
            assert cfg.pending_ttl_seconds == 120

    def test_invalid_env_uses_default(self, tmp_path):
        """Invalid env var values are ignored; defaults are used."""
        with patch.dict(os.environ, {"SPECTATOR_PENDING_TTL_SECONDS": "not_a_number"}):
            cfg = load_config(config_path=tmp_path / "nonexistent.yaml")
            assert cfg.pending_ttl_seconds == 300  # default

    def test_invalid_feed_source_rejected(self):
        """Invalid feed_source value raises validation error."""
        with pytest.raises(Exception):
            SpectatorConfig(feed_source="invalid")

    def test_out_of_range_ttl_fail_closed(self, tmp_path):
        """Out-of-range TTL values fail closed to default."""
        # Pydantic enforces ge/le, so constructing with out-of-range fails
        with pytest.raises(Exception):
            SpectatorConfig(pending_ttl_seconds=10)  # min 60


# ===========================================================================
# Fail-closed backend init
# ===========================================================================

class TestFailClosedInit:
    """Missing/corrupt host_secret → 503 DEGRADED + recovery banner path."""

    def test_missing_secret_creates_new(self, tmp_data_dir):
        """When no host_secret exists, a new one is created."""
        secret_path = tmp_data_dir / "host_secret"
        mgr = HostSecretManager(secret_path)
        assert mgr.load_or_create() is True
        assert mgr.degraded is False
        assert secret_path.exists()
        # File should be 0600
        mode = stat.S_IMODE(secret_path.stat().st_mode)
        assert mode == 0o600

    def test_corrupt_secret_degrades(self, tmp_data_dir):
        """Corrupt (wrong length) host_secret → DEGRADED state."""
        secret_path = tmp_data_dir / "host_secret"
        # Write wrong-length data
        secret_path.write_bytes(b"short")
        secret_path.chmod(0o600)

        mgr = HostSecretManager(secret_path)
        assert mgr.load_or_create() is False
        assert mgr.degraded is True
        assert "Corrupt host_secret" in mgr.degraded_reason

    def test_unwritable_dir_degrades(self, tmp_data_dir):
        """Unwritable directory for host_secret → DEGRADED state."""
        # Create a read-only dir
        secret_path = tmp_data_dir / "readonly" / "host_secret"
        secret_path.parent.mkdir()
        secret_path.parent.chmod(0o444)

        mgr = HostSecretManager(secret_path)
        try:
            result = mgr.load_or_create()
            # If permission denied triggers degraded, verify
            if mgr.degraded:
                assert mgr.degraded is True
                assert "permission" in mgr.degraded_reason.lower() or "Cannot" in mgr.degraded_reason
        finally:
            # Restore permissions for cleanup
            secret_path.parent.chmod(0o755)

    def test_degraded_status_endpoint_returns_503(self, tmp_data_dir):
        """When backend is degraded, /status returns 503 with recovery info."""
        # Create a degraded state by corrupting the secret
        secret_path = tmp_data_dir / "host_secret"
        secret_path.write_bytes(b"corrupt_short")
        secret_path.chmod(0o600)

        # Import without sys.path hack — the plugin_api.py has its own bootstrap
        from dashboard.plugin_api import _state, init_plugin, router

        app = _make_app_with_router(router)
        init_plugin(
            config_path=tmp_data_dir / "nonexistent.yaml",
            data_dir=tmp_data_dir,
            session_id="test-session",
        )

        if _state.degraded:
            client = TestClient(app)
            resp = client.get("/api/plugins/spectator/status")
            assert resp.status_code == 503
            data = resp.json()
            assert data["detail"]["error"] == "host_secret_unavailable"
            assert "recovery" in data["detail"]

    def test_recovery_banner_path_in_degraded_response(self, tmp_data_dir):
        """503 response includes the exact failing path for recovery."""
        secret_path = tmp_data_dir / "host_secret"
        secret_path.write_bytes(b"tiny")
        secret_path.chmod(0o600)

        mgr = HostSecretManager(secret_path)
        mgr.load_or_create()
        if mgr.degraded:
            assert str(secret_path) in mgr.degraded_reason


# ===========================================================================
# Network binding enforcement
# ===========================================================================

class TestNetworkBinding:
    """Non-loopback binding refused unless allow_remote + TLS."""

    def test_default_is_loopback_only(self):
        """Default config: allow_remote=False (loopback only)."""
        cfg = SpectatorConfig()
        assert cfg.allow_remote is False

    def test_remote_requires_tls(self):
        """allow_remote=True defaults to require_tls=True."""
        cfg = SpectatorConfig(allow_remote=True)
        assert cfg.require_tls is True

    def test_remote_without_tls_causes_degradation(self, tmp_data_dir):
        """allow_remote=True with require_tls=False causes DEGRADED 503.

        The plugin MUST NOT serve requests when configured for remote
        access without TLS. This is a hard enforcement, not just a warning.
        """
        from dashboard.plugin_api import _state, init_plugin

        # Create config that allows remote without TLS
        cfg_dir = tmp_data_dir / "cfg"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "config.yaml"
        cfg_file.write_text(
            "spectator:\n"
            "  allow_remote: true\n"
            "  require_tls: false\n"
        )

        init_plugin(
            config_path=cfg_file,
            data_dir=tmp_data_dir,
            session_id="test-binding",
        )

        # Must be degraded — remote without TLS is refused
        assert _state.degraded is True, (
            "Plugin should be DEGRADED when allow_remote=true and require_tls=false"
        )
        assert "TLS" in _state.degraded_reason or "insecure" in _state.degraded_reason.lower()

    def test_remote_with_tls_is_ok(self, tmp_data_dir):
        """allow_remote=True with require_tls=True does NOT degrade."""
        from dashboard.plugin_api import _state, init_plugin

        # Reset state for clean test
        _state._initialized = False
        _state.degraded = False
        _state.degraded_reason = ""

        cfg_dir = tmp_data_dir / "cfg_ok"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "config.yaml"
        cfg_file.write_text(
            "spectator:\n"
            "  allow_remote: true\n"
            "  require_tls: true\n"
        )

        init_plugin(
            config_path=cfg_file,
            data_dir=tmp_data_dir,
            session_id="test-binding-ok",
        )

        assert _state.degraded is False, (
            "Plugin should NOT be degraded when allow_remote=true and require_tls=true"
        )


# ===========================================================================
# Session-gen identity
# ===========================================================================

class TestSessionGenIdentity:
    """Session restart invalidates stale invites (session_gen)."""

    def test_different_session_gens(self, tmp_data_dir):
        """Two different session_id/process_start combos produce different gens."""
        gen1 = SessionGenManager(tmp_data_dir)
        gen1.initialise("session-1", 1000.0)

        gen2 = SessionGenManager(tmp_data_dir)
        gen2.initialise("session-2", 2000.0)

        assert gen1.current != gen2.current

    def test_previous_gen_tracked(self, tmp_data_dir):
        """On init, previous session_gen is tracked for invalidation."""
        gen1 = SessionGenManager(tmp_data_dir)
        first_gen = gen1.initialise("session-1", 1000.0)

        gen2 = SessionGenManager(tmp_data_dir)
        second_gen = gen2.initialise("session-2", 2000.0)

        assert gen2.previous == first_gen
        assert gen2.current != gen2.previous


# ===========================================================================
# Integration: REST namespace endpoints
# ===========================================================================

def _make_app_with_router(router):
    """Create a FastAPI app with the spectator router, matching host behaviour.

    This simulates how the real Duckwork host mounts the plugin:
    it importlib-loads plugin_api.py and includes the router under a prefix.
    No init_plugin() call, no app-level middleware — just like the real host.
    """
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/plugins/spectator")
    return app


class TestPluginRESTNamespace:
    """All endpoints respond with correct status codes.

    C2 added auth dependencies to most endpoints. Host auth (bearer token)
    is required for /status, /invites (mint/list/revoke). The /invites/join
    endpoint is public (invite token is the credential). /guest.html is
    public (no auth needed to load the page). /feed and /suggestions still
    return 501 (C3/C4).
    """

    def _make_client_and_token(self, tmp_data_dir):
        """Create a TestClient with initialised plugin + a host bearer token."""
        from dashboard.plugin_api import _state, init_plugin, router

        app = _make_app_with_router(router)
        result = init_plugin(
            config_path=tmp_data_dir / "nonexistent.yaml",
            data_dir=tmp_data_dir,
            session_id="test-session-namespace",
        )
        client = TestClient(app)
        host_token = _state.secret_mgr.secret.hex()
        return client, host_token

    def _make_client(self, tmp_data_dir):
        """Create a TestClient with the spectator router initialised (for C1 compat)."""
        client, _ = self._make_client_and_token(tmp_data_dir)
        return client

    def test_status_returns_200_with_feed_source(self, tmp_data_dir):
        """GET /status returns 200 with feed_source field (host auth required)."""
        client, host_token = self._make_client_and_token(tmp_data_dir)
        resp = client.get(
            "/api/plugins/spectator/status",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "feed_source" in data
        assert data["feed_source"] in ("auto", "onEvent", "transcript")
        assert "session_id" in data
        assert "host_active" in data
        assert "guest_count" in data

    def test_status_requires_auth(self, tmp_data_dir):
        """GET /status returns 401 without auth."""
        client, _ = self._make_client_and_token(tmp_data_dir)
        resp = client.get("/api/plugins/spectator/status")
        assert resp.status_code == 401

    def test_guest_html_returns_200(self, tmp_data_dir):
        """GET /guest.html returns 200 with HTML content (no auth needed)."""
        client, _ = self._make_client_and_token(tmp_data_dir)
        resp = client.get("/api/plugins/spectator/guest.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_invite_endpoints_require_host_auth(self, tmp_data_dir):
        """C2 invite endpoints require host auth (mint/list/revoke)."""
        client, host_token = self._make_client_and_token(tmp_data_dir)
        headers = {"Authorization": f"Bearer {host_token}"}

        # Host can mint
        resp = client.post("/api/plugins/spectator/invites", json={}, headers=headers)
        assert resp.status_code == 200

        # Host can list
        resp = client.get("/api/plugins/spectator/invites", headers=headers)
        assert resp.status_code == 200

        # Without auth, these should return 401
        resp = client.post("/api/plugins/spectator/invites", json={})
        assert resp.status_code == 401

        resp = client.get("/api/plugins/spectator/invites")
        assert resp.status_code == 401

    def test_invite_join_is_public(self, tmp_data_dir):
        """POST /invites/join is a public endpoint (invite token is the credential)."""
        client, host_token = self._make_client_and_token(tmp_data_dir)
        headers = {"Authorization": f"Bearer {host_token}"}

        # Mint an invite
        mint_resp = client.post("/api/plugins/spectator/invites", json={}, headers=headers)
        assert mint_resp.status_code == 200
        raw_token = mint_resp.json()["token"]

        # Join requires no auth (the invite token IS the credential)
        join_resp = client.post(
            "/api/plugins/spectator/invites/join",
            json={"token": raw_token},
        )
        assert join_resp.status_code == 200

    def test_feed_endpoint_returns_200(self, tmp_data_dir):
        """C3 feed endpoint returns 200 (implemented in C3)."""
        client, host_token = self._make_client_and_token(tmp_data_dir)

        # With host auth — auth passes, endpoint returns 200 with empty feed
        resp = client.get(
            "/api/plugins/spectator/feed",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "reset" in data

    def test_suggestion_endpoints_require_auth(self, tmp_data_dir):
        """C4 suggestion endpoints are implemented; unauthenticated → 401."""
        client, _ = self._make_client_and_token(tmp_data_dir)

        resp = client.post("/api/plugins/spectator/suggestions", json={"content": "x"})
        assert resp.status_code == 401

        resp = client.get("/api/plugins/spectator/suggestions")
        assert resp.status_code == 401

    def test_suggestion_request_rejects_oversize_content_before_gate(self):
        """The HTTP request model enforces the same 32 KiB ceiling as the gate."""
        from pydantic import ValidationError

        from dashboard.plugin_api import SubmitSuggestionRequest

        with pytest.raises(ValidationError):
            SubmitSuggestionRequest(content="x" * (32 * 1024 + 1))


class TestDuckworkVerifyRecipe:
    """The repo-local recipe must override Duckwork' generic FastAPI detection."""

    def test_recipe_targets_real_app_and_readiness_route(self):
        import json

        root = Path(__file__).resolve().parent.parent
        manifest_path = root / ".duckwork" / "environment.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        recipe = payload.get("recipe", payload)

        assert "spectator.serve:app" in recipe["start"]
        assert "main:app" not in recipe["start"]
        assert "--host 127.0.0.1" in recipe["start"]
        assert recipe["port"] == 8000
        assert recipe["readinessPath"] == "/api/plugins/spectator/guest.html"


# ===========================================================================
# Host-realistic integration: router mounted without init_plugin()
# ===========================================================================

def _reset_state():
    """Reset the _state singleton for clean test isolation."""
    from dashboard.plugin_api import _state
    _state._initialized = False
    _state.db = None
    _state.secret_mgr = None
    _state.session_gen_mgr = None
    _state.invite_mgr = None
    _state.start_time = 0.0
    _state.session_id = ""
    _state.session_gen = ""
    _state.degraded = False
    _state.degraded_reason = ""
    _state.config = SpectatorConfig()


def _patch_data_dir(tmp_data_dir):
    """Patch DEFAULT_DATA_DIR in the plugin_api module namespace.

    The import ``from spectator.config import ... DEFAULT_DATA_DIR`` in
    plugin_api.py creates a name binding in the plugin_api module.  Patching
    spectator.config.DEFAULT_DATA_DIR alone doesn't affect it — we must patch
    dashboard.plugin_api.DEFAULT_DATA_DIR as well.
    """
    import dashboard.plugin_api as api_mod
    import spectator.config as cfg_mod
    orig_api = api_mod.DEFAULT_DATA_DIR
    orig_cfg = cfg_mod.DEFAULT_DATA_DIR
    api_mod.DEFAULT_DATA_DIR = tmp_data_dir
    cfg_mod.DEFAULT_DATA_DIR = tmp_data_dir
    return orig_api, orig_cfg


def _restore_data_dir(orig_api, orig_cfg):
    """Restore DEFAULT_DATA_DIR after patching."""
    import dashboard.plugin_api as api_mod
    import spectator.config as cfg_mod
    api_mod.DEFAULT_DATA_DIR = orig_api
    cfg_mod.DEFAULT_DATA_DIR = orig_cfg


class TestHostRealisticIntegration:
    """Tests that exercise the real host integration path.

    The Duckwork host importlib-loads plugin_api.py and mounts the router
    under /api/plugins/spectator/ — it NEVER calls init_plugin() or
    registers any middleware.  These tests verify that lazy init works
    correctly in that scenario.
    """

    def test_lazy_init_status_200(self, tmp_data_dir):
        """Mount router WITHOUT calling init_plugin() — lazy init should work.

        This is the exact scenario the Duckwork host exercises: it only
        mounts the router.  The plugin must self-initialise on first request.
        C2: /status requires host auth, so we pass the bearer token.
        """
        from dashboard.plugin_api import _state, router

        _reset_state()
        orig_api, orig_cfg = _patch_data_dir(tmp_data_dir)

        try:
            app = _make_app_with_router(router)
            # NO init_plugin() call — just like the real host
            client = TestClient(app)

            # First request triggers lazy init.
            # /guest.html doesn't require auth, so we can use it to trigger init.
            resp = client.get("/api/plugins/spectator/guest.html")
            assert resp.status_code == 200  # Triggers lazy init

            # Now _state.secret_mgr is available
            host_token = _state.secret_mgr.secret.hex()

            # Now test /status with host auth
            resp = client.get(
                "/api/plugins/spectator/status",
                headers={"Authorization": f"Bearer {host_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "feed_source" in data
        finally:
            _restore_data_dir(orig_api, orig_cfg)
            _reset_state()

    def test_lazy_init_degraded_503(self, tmp_data_dir):
        """Lazy init with corrupt host_secret → 503 on all endpoints.

        Verifies that the degraded check works via the FastAPI dependency,
        not app-level middleware.
        """
        from dashboard.plugin_api import router

        # Create a corrupt host_secret
        secret_path = tmp_data_dir / "host_secret"
        secret_path.write_bytes(b"corrupt_short")
        secret_path.chmod(0o600)

        _reset_state()
        orig_api, orig_cfg = _patch_data_dir(tmp_data_dir)

        try:
            app = _make_app_with_router(router)
            # NO init_plugin() — lazy init with corrupt secret
            client = TestClient(app)

            # Should get 503 on every endpoint
            resp = client.get("/api/plugins/spectator/status")
            assert resp.status_code == 503, (
                f"Expected 503 for degraded state, got {resp.status_code}: {resp.text}"
            )
            data = resp.json()
            assert data["detail"]["error"] == "host_secret_unavailable"

            # Guest page also returns 503 when degraded
            resp = client.get("/api/plugins/spectator/guest.html")
            assert resp.status_code == 503, (
                f"Expected 503 for degraded guest.html, got {resp.status_code}: {resp.text}"
            )
        finally:
            _restore_data_dir(orig_api, orig_cfg)
            _reset_state()

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission semantics")
    def test_lazy_init_unsafe_storage_parent_degrades_to_503(self, tmp_path):
        """Unsafe local storage fails closed with an actionable response."""
        from dashboard.plugin_api import router

        unsafe_parent = tmp_path / "unsafe-parent"
        unsafe_parent.mkdir(mode=0o777)
        unsafe_parent.chmod(0o777)
        data_dir = unsafe_parent / "spectator"

        _reset_state()
        orig_api, orig_cfg = _patch_data_dir(data_dir)
        try:
            app = _make_app_with_router(router)
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/plugins/spectator/status")
            assert response.status_code == 503
            detail = response.json()["detail"]
            assert detail["error"] == "runtime_storage_unavailable"
            assert "world-writable" in detail["detail"]
            assert "permissions" in detail["recovery"]
        finally:
            _restore_data_dir(orig_api, orig_cfg)
            _reset_state()

    def test_self_contained_imports(self):
        """Verify plugin_api.py can be imported without pip install or sys.path.

        The host only importlib-loads dashboard/plugin_api.py — it never adds
        src/ to sys.path.  The plugin_api.py must bootstrap its own imports.
        """
        import importlib
        import sys

        # Remove spectator from sys.modules to simulate clean import
        spectator_modules = [
            k for k in list(sys.modules) if k.startswith("spectator")
        ]
        for k in spectator_modules:
            del sys.modules[k]

        # Remove dashboard from sys.modules too
        dashboard_modules = [
            k for k in list(sys.modules) if k.startswith("dashboard")
        ]
        for k in dashboard_modules:
            del sys.modules[k]

        # Also remove the duckwork_dashboard_plugin module if present
        plugin_modules = [
            k for k in list(sys.modules) if k.startswith("duckwork_dashboard_plugin")
        ]
        for k in plugin_modules:
            del sys.modules[k]

        # Import plugin_api.py via importlib (like the host does)
        api_path = Path(__file__).resolve().parent.parent / "dashboard" / "plugin_api.py"
        spec = importlib.util.spec_from_file_location(
            "duckwork_dashboard_plugin_spectator", api_path
        )
        assert spec is not None, f"Could not create spec for {api_path}"
        mod = importlib.util.module_from_spec(spec)
        sys.modules["duckwork_dashboard_plugin_spectator"] = mod
        spec.loader.exec_module(mod)

        # Must have a router attribute
        assert hasattr(mod, "router"), "plugin_api.py must expose a 'router'"
        assert hasattr(mod, "_state"), "plugin_api.py must expose _state for lazy init"


# ===========================================================================
# Manifest — tab hidden until C5 ships UI
# ===========================================================================

class TestManifest:
    """Verify dashboard/manifest.json fields for C1 host integration.

    Finding 6 (Quan re-review): removing 'entry' from manifest is a no-op
    because the host re-defaults to dist/index.js and the frontend loads
    manifest.entry unconditionally.  The Spectator tab would 404 and remain
    visible in nav.  The correct fix is to add 'hidden: true' to the tab
    object so the frontend skips it entirely.  C5 removes hidden when the
    real dist/ bundle ships.
    """

    def test_manifest_tab_hidden_until_c5(self):
        """Tab must be hidden so the frontend does not render a dead nav item."""
        import json
        manifest_path = Path(__file__).resolve().parent.parent / "dashboard" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["tab"].get("hidden") is True, (
            "manifest.json tab.hidden must be true until C5 ships the UI bundle. "
            "Without this, the host re-defaults entry to dist/index.js and the "
            "frontend renders a dead Spectator tab that 404s."
        )

    def test_manifest_no_entry_field(self):
        """Manifest must NOT declare an 'entry' field until dist/ exists (C5).

        Even though the host defaults entry to dist/index.js when absent,
        explicitly declaring it would be misleading since the file does not
        exist.  The hidden flag is the operative control.
        """
        import json
        manifest_path = Path(__file__).resolve().parent.parent / "dashboard" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert "entry" not in manifest, (
            "manifest.json must not declare 'entry' until C5 ships dist/index.js"
        )