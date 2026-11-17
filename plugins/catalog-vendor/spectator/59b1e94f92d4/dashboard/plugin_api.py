"""duckwork-spectator plugin backend — FastAPI router.

Mounted at /api/plugins/spectator/ by the Duckwork dashboard plugin system.
Follows the pattern established by the kanban and achievements dashboard plugins.

The host importlib-loads this file and mounts ``router`` — it never calls
init_plugin() or registers middleware.  Therefore:
- All initialisation is lazy (``_ensure_initialized()``) so the router
  works the moment it is mounted.
- The degraded-state check is a FastAPI dependency, not app middleware.
- All imports are self-contained (stdlib + fastapi + pydantic only);
  the ``src/spectator`` package is imported via a sys.path bootstrap
  at module level.

C1 scope: /status, /guest.html static route, config loading, DB init,
fail-closed backend init, loopback binding enforcement.
C2 scope: AuthN v3 (host bearer + guest HMAC tokens), invite lifecycle
(mint/join/revoke), role enforcement on all endpoints.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# sys.path bootstrap — makes ``spectator.*`` importable without pip install.
# The host never adds the plugin's src/ to sys.path, so we do it ourselves.
# ---------------------------------------------------------------------------
_PLUGIN_DIR = Path(__file__).resolve().parent.parent  # repo root
_SRC_DIR = _PLUGIN_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from spectator.adapters.duckwork import discover_duckwork_descriptor
from spectator.adapters.native_host import inject_native_message
from spectator.adapters.stored import StoredSessionAdapter
from spectator.auth.auth import HostSecretManager, SessionGenManager
from spectator.auth.invite import InviteError, InviteManager
from spectator.config import (
    DEFAULT_DATA_DIR,
    DEFAULT_STATE_DB_PATH,
    SpectatorConfig,
    load_config,
)
from spectator.core.contracts import (
    BranchQueryError,
    EventInput,
    SessionDescriptor,
    SessionNotFoundError,
    WritableSessionAdapter,
)
from spectator.core.registry import AdapterRegistry
from spectator.core.service import SpectatorService
from spectator.db.db import SpectatorDB
from spectator.feed.engine import FeedEngine
from spectator.feed.poller import TranscriptPoller
from spectator.suggest.gate import MAX_CONTENT_BYTES, SuggestionError, SuggestionGate

log = logging.getLogger("spectator")

router = APIRouter()

# ---------------------------------------------------------------------------
# Application state (lazy-initialised on first request)
# ---------------------------------------------------------------------------

class _AppState:
    """Singleton app state — initialised lazily on first request."""

    config: SpectatorConfig = SpectatorConfig()
    db: SpectatorDB | None = None
    secret_mgr: HostSecretManager | None = None
    invite_mgr: InviteManager | None = None
    session_gen_mgr: SessionGenManager | None = None
    feed_engine: FeedEngine | None = None
    suggest_gate: SuggestionGate | None = None
    poller: TranscriptPoller | None = None
    adapter_registry: AdapterRegistry | None = None
    spectator_service: SpectatorService | None = None
    start_time: float = 0.0
    session_id: str = ""
    session_gen: str = ""
    degraded: bool = False
    degraded_reason: str = ""
    _initialized: bool = False

    @property
    def feed_source(self) -> str:
        # Live truth: when the poller exists and reports the transcript as its
        # source, reflect that; otherwise fall back to the configured value.
        poller = self.poller
        if poller is not None:
            return poller.source_status
        return self.config.feed_source

    def ensure_initialized(self) -> None:
        """Idempotent lazy init — called on first request or explicitly.

        Safe to call multiple times; only the first call runs init logic.
        """
        if self._initialized:
            return

        data_dir = DEFAULT_DATA_DIR

        # 1. Load config
        self.config = load_config()

        # 2. Init database. Storage failures degrade cleanly instead of
        # leaking an internal exception from the first HTTP request.
        db_path = data_dir / "spectator.db"
        try:
            self.db = SpectatorDB(db_path)
            self.db.init_schema()
        except (OSError, sqlite3.Error) as exc:
            self.db = None
            self.degraded = True
            self.degraded_reason = str(exc)
            self.start_time = time.time()
            self._initialized = True
            log.critical("Plugin entering DEGRADED state: %s", self.degraded_reason)
            return

        # 3. Host secret — fail-closed
        secret_path = data_dir / "host_secret"
        self.secret_mgr = HostSecretManager(secret_path)
        if not self.secret_mgr.load_or_create():
            self.degraded = True
            self.degraded_reason = self.secret_mgr.degraded_reason
            log.critical("Plugin entering DEGRADED state: %s", self.degraded_reason)
        else:
            self.degraded = False

        # 4. Session-gen identity
        self.session_gen_mgr = SessionGenManager(data_dir)
        process_start = time.time()
        self.session_id = (
            os.environ.get("SPECTATOR_SESSION_ID")
            or os.environ.get("DUCKWORK_SESSION_ID", "")
        )
        new_gen = self.session_gen_mgr.initialise(self.session_id, process_start)
        self.session_gen = new_gen

        # If previous session_gen differs, invalidate stale invites
        prev_gen = self.session_gen_mgr.previous
        if prev_gen is not None and prev_gen != new_gen:
            log.info("New session_gen detected; invalidating invites with old gen %s", prev_gen[:8])
            self._invalidate_stale_invites(prev_gen)

        # 5. Invite manager (receives current session_gen for runtime stale-check)
        self.invite_mgr = InviteManager(self.db, self.secret_mgr, current_session_gen=new_gen)

        # 6. Feed engine (append-only event store)
        self.feed_engine = FeedEngine(self.db, self.session_id)

        # 6a. Harness-neutral adapter registry and application service. Native
        # and portable integrations register one adapter per exact session.
        self.adapter_registry = AdapterRegistry()
        self.spectator_service = SpectatorService(self.adapter_registry)

        # 6b. Transcript-tail poller (producer). Constructed but NOT started
        # here — the worker thread is launched lazily on first /feed poll so a
        # degraded or session-less startup never spins a useless thread.
        self.poller = TranscriptPoller(
            self.feed_engine,
            self.db,
            DEFAULT_STATE_DB_PATH,
            poll_interval=self.config.poll_interval_seconds,
        )
        self._register_native_duckwork(DEFAULT_STATE_DB_PATH)

        # 6c. Suggestion gate (inject seam fail-closed until host wires it)
        self.suggest_gate = SuggestionGate(
            self.db,
            inject_fn=lambda content, role="user", mode="queue": inject_native_message(
                self.session_id,
                DEFAULT_STATE_DB_PATH,
                content,
                role,
                mode,
            ),
            inject_timeout_seconds=self.config.inject_timeout_seconds,
            capacity=self.config.max_pending_suggestions,
            pending_ttl_seconds=self.config.pending_ttl_seconds,
        )

        # 7. Network binding enforcement
        self._enforce_binding_config()

        self.start_time = time.time()
        self._initialized = True
        log.info(
            "Spectator plugin initialised: session=%s, feed_source=%s, degraded=%s",
            self.session_id[:8] if self.session_id else "(none)",
            self.feed_source,
            self.degraded,
        )

    def _invalidate_stale_invites(self, old_gen: str) -> None:
        """Mark all invites from the previous session_gen as revoked (host_gone).

        If old_gen is the empty-string sentinel (missing/corrupt gen file),
        invalidate ALL non-revoked invites — we cannot know which generation
        they belong to, so fail-closed (AC#3).
        """
        if self.db is None:
            return
        with self.db.write_txn() as cur:
            if old_gen == "":
                # Fail-closed: gen file was missing/corrupt — revoke everything
                cur.execute("UPDATE invites SET revoked = 1 WHERE revoked = 0")
                cur.execute(
                    """UPDATE suggestions SET status = 'expired', receipt_state = 'host_gone'
                    WHERE session_id = ? AND status = 'pending'""",
                    (self.session_id,),
                )
            else:
                cur.execute(
                    "UPDATE invites SET revoked = 1 WHERE session_gen = ?",
                    (old_gen,),
                )
                cur.execute(
                    """UPDATE suggestions SET status = 'expired', receipt_state = 'host_gone'
                    WHERE session_id = ? AND status = 'pending'""",
                    (self.session_id,),
                )
        if old_gen == "":
            log.info("Invalidated ALL stale invites (unknown previous gen)")
        else:
            log.info("Invalidated stale invites with old gen %s", old_gen[:8])

    def _register_native_duckwork(self, state_db_path: Path) -> None:
        """Register the current Duckwork session when its Git metadata is available."""
        if self.adapter_registry is None or self.feed_engine is None:
            return
        try:
            descriptor = discover_duckwork_descriptor(state_db_path, self.session_id)
            if descriptor is None:
                return
            adapter = StoredSessionAdapter(descriptor, self.feed_engine)
            self.adapter_registry.register(adapter, replace=True)
        except Exception as exc:
            # Native discovery is optional. The portable bridge remains usable,
            # so do not degrade the whole service when host metadata is absent.
            log.warning("Duckwork session adapter discovery failed: %s", exc)

    def _enforce_binding_config(self) -> None:
        """Enforce network binding config.

        - allow_remote=false: OK (loopback only)
        - allow_remote=true AND require_tls=true: OK (remote with TLS)
        - allow_remote=true AND require_tls=false: REFUSE to serve — force
          DEGRADED state.  The plugin MUST NOT accept remote connections
          without TLS.
        """
        cfg = self.config
        if cfg.allow_remote and not cfg.require_tls:
            self.degraded = True
            self.degraded_reason = (
                "Spectator config allows remote access without TLS "
                "(allow_remote=true, require_tls=false). "
                "This is insecure — set require_tls=true or allow_remote=false."
            )
            log.critical(self.degraded_reason)
        elif not cfg.allow_remote:
            log.info("Spectator: loopback-only binding (allow_remote=false)")


_state = _AppState()

# ---------------------------------------------------------------------------
# Startup / init (kept for explicit init if ever needed, e.g. tests)
# ---------------------------------------------------------------------------

def init_plugin(
    config_path: Path | None = None,
    data_dir: Path | None = None,
    session_id: str = "",
) -> dict:
    """Initialise the spectator plugin backend.

    Called explicitly in tests.  In production, lazy init via
    ``_ensure_initialized()`` handles everything on first request.
    """
    if config_path is not None:
        # Override defaults for test injection
        _state.config = load_config(config_path=config_path)
    if data_dir is not None:
        data_dir = Path(data_dir)

        # Re-init DB with explicit path
        db_path = data_dir / "spectator.db"
        _state.db = SpectatorDB(db_path)
        _state.db.init_schema()

        # Re-init secret manager
        secret_path = data_dir / "host_secret"
        _state.secret_mgr = HostSecretManager(secret_path)
        if not _state.secret_mgr.load_or_create():
            _state.degraded = True
            _state.degraded_reason = _state.secret_mgr.degraded_reason
            log.critical("Plugin entering DEGRADED state: %s", _state.degraded_reason)
        else:
            _state.degraded = False

        # Re-init session-gen
        _state.session_gen_mgr = SessionGenManager(data_dir)
        _state.session_id = session_id
        process_start = time.time()
        new_gen = _state.session_gen_mgr.initialise(session_id, process_start)
        _state.session_gen = new_gen
        prev_gen = _state.session_gen_mgr.previous
        if prev_gen is not None and prev_gen != new_gen:
            _state._invalidate_stale_invites(prev_gen)

        # Re-init invite manager (with current session_gen)
        _state.invite_mgr = InviteManager(_state.db, _state.secret_mgr, current_session_gen=new_gen)

        # Re-init feed engine
        _state.feed_engine = FeedEngine(_state.db, session_id)

        # Re-init harness-neutral registry and service
        _state.adapter_registry = AdapterRegistry()
        _state.spectator_service = SpectatorService(_state.adapter_registry)

        # Re-init transcript-tail poller (constructed, not started)
        _state.poller = TranscriptPoller(
            _state.feed_engine,
            _state.db,
            DEFAULT_STATE_DB_PATH,
            poll_interval=_state.config.poll_interval_seconds,
        )
        _state._register_native_duckwork(DEFAULT_STATE_DB_PATH)

        # Re-init suggestion gate
        _state.suggest_gate = SuggestionGate(
            _state.db,
            inject_fn=lambda content, role="user", mode="queue": inject_native_message(
                _state.session_id,
                DEFAULT_STATE_DB_PATH,
                content,
                role,
                mode,
            ),
            inject_timeout_seconds=_state.config.inject_timeout_seconds,
            capacity=_state.config.max_pending_suggestions,
            pending_ttl_seconds=_state.config.pending_ttl_seconds,
        )

        _state._enforce_binding_config()

        _state.start_time = time.time()
        _state._initialized = True

    return {
        "session_id": session_id,
        "feed_source": _state.feed_source,
        "degraded": _state.degraded,
    }


# ---------------------------------------------------------------------------
# AuthN dependencies (C2)
# ---------------------------------------------------------------------------

class _Identity(BaseModel):
    """Authenticated identity returned by auth dependencies."""
    role: str  # "host" or "guest"
    guest_id: str | None = None
    invite_id: str | None = None
    session_id: str | None = None


def _extract_bearer(request: Request) -> str | None:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


async def require_host(request: Request) -> _Identity:
    """FastAPI dependency: require host-role authentication.

    Two paths:
    1. CLI bearer: Authorization: Bearer <host_secret_hex>
    2. Gateway session: the host UI authenticates via ctx.rest which
       carries the desktop app's gateway session credentials automatically.

    For now, only the CLI bearer path is implemented. The gateway session
    path will be wired when C5 ships the host UI pane.
    """
    _state.ensure_initialized()
    _check_not_degraded()

    bearer = _extract_bearer(request)
    if bearer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_authorization", "message": "Authorization header required"},
        )

    # Try host secret verification
    if _state.secret_mgr and _state.secret_mgr.verify_host_bearer(bearer):
        return _Identity(role="host")

    # If the token looks like a guest token (has a colon), it's a guest
    # trying to access a host-only endpoint → 403
    if ":" in bearer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_role",
                "message": "Host role required; guest token rejected",
                "receipt_state": "invalid",
            },
        )

    # Neither a valid host secret nor a guest token → 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "invalid_credentials", "message": "Invalid bearer token"},
    )


async def require_any_auth(request: Request) -> _Identity:
    """FastAPI dependency: require any valid authentication (host or guest).

    Returns the identity with role='host' or role='guest'.
    Used for endpoints accessible by both roles (e.g. feed).
    """
    _state.ensure_initialized()
    _check_not_degraded()

    bearer = _extract_bearer(request)
    if bearer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_authorization", "message": "Authorization header required"},
        )

    # Try host secret first
    if _state.secret_mgr and _state.secret_mgr.verify_host_bearer(bearer):
        return _Identity(role="host")

    # Try guest token
    if _state.invite_mgr:
        try:
            guest_info = _state.invite_mgr.verify_guest_token(bearer)
            return _Identity(
                role="guest",
                guest_id=guest_info["guest_id"],
                invite_id=guest_info["invite_id"],
                session_id=guest_info["session_id"],
            )
        except Exception as exc:
            # InviteError (or any subclass) — convert to HTTPException
            # We catch broadly to avoid module-identity issues with
            # sys.path bootstrap and test isolation.
            status_code = getattr(exc, "status_code", 401)
            raise HTTPException(
                status_code=status_code,
                detail={"error": "invalid_credentials", "message": str(exc)},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "invalid_credentials", "message": "Invalid bearer token"},
    )


async def require_guest(request: Request) -> _Identity:
    """FastAPI dependency: require guest-role authentication.

    Only guest tokens are accepted. Host bearer tokens are rejected.
    """
    _state.ensure_initialized()
    _check_not_degraded()

    bearer = _extract_bearer(request)
    if bearer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_authorization", "message": "Authorization header required"},
        )

    # Reject host secret on guest-only endpoints
    if _state.secret_mgr and _state.secret_mgr.verify_host_bearer(bearer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "insufficient_role", "message": "Guest role required; host token rejected"},
        )

    # Try guest token
    if _state.invite_mgr:
        try:
            guest_info = _state.invite_mgr.verify_guest_token(bearer)
            return _Identity(
                role="guest",
                guest_id=guest_info["guest_id"],
                invite_id=guest_info["invite_id"],
                session_id=guest_info["session_id"],
            )
        except Exception as exc:
            # Same broad catch as require_any_auth — avoids module-identity
            # issues with sys.path bootstrap and test isolation.
            status_code = getattr(exc, "status_code", 401)
            raise HTTPException(
                status_code=status_code,
                detail={"error": "invalid_credentials", "message": str(exc)},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "invalid_credentials", "message": "Invalid bearer token"},
    )


# ---------------------------------------------------------------------------
# FastAPI dependency: degraded-state guard (router-internal, not app middleware)
# ---------------------------------------------------------------------------

def _degraded_detail() -> dict[str, str]:
    if _state.secret_mgr is None:
        return {
            "error": "runtime_storage_unavailable",
            "detail": _state.degraded_reason,
            "recovery": (
                "Fix permissions on the Spectator data directory and its parent, "
                "then restart the service"
            ),
        }
    if _state.secret_mgr.degraded:
        return {
            "error": "host_secret_unavailable",
            "detail": _state.degraded_reason,
            "recovery": (
                f"Ensure {_state.secret_mgr.secret_path} is writable or remove "
                "the corrupt file to regenerate it"
            ),
        }
    if _state.config.allow_remote and not _state.config.require_tls:
        return {
            "error": "insecure_network_binding",
            "detail": _state.degraded_reason,
            "recovery": "Set require_tls=true or allow_remote=false, then restart the service",
        }
    return {
        "error": "backend_unavailable",
        "detail": _state.degraded_reason,
        "recovery": "Review Spectator logs and configuration, then restart the service",
    }


async def _require_not_degraded(request: Request) -> None:
    """FastAPI dependency that returns 503 if the backend is degraded.

    Unlike app-level middleware, this dependency is scoped to the
    spectator router and works regardless of how the host mounts it.
    """
    if _state.degraded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_degraded_detail(),
        )


# ---------------------------------------------------------------------------
# Sync version for non-async endpoints
# ---------------------------------------------------------------------------

def _check_not_degraded() -> None:
    """Synchronous degraded check for non-async endpoints."""
    if _state.degraded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_degraded_detail(),
        )


# ---------------------------------------------------------------------------
# Endpoints — C1 scope
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    session_id: str
    host_active: bool
    guest_count: int
    pending_suggestions: int
    uptime_seconds: float
    feed_source: str


@router.get("/status", response_model=StatusResponse)
async def get_status(identity: _Identity = Depends(require_host)):
    """Plugin health + session info. Host-only."""
    db = _state.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Count guests and pending suggestions
    cur = db.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM guests WHERE revoked = 0")
    guest_count = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM suggestions WHERE session_id = ? AND status = 'pending'",
        (_state.session_id,),
    )
    pending = cur.fetchone()[0]

    return StatusResponse(
        session_id=_state.session_id,
        host_active=True,
        guest_count=guest_count,
        pending_suggestions=pending,
        uptime_seconds=time.time() - _state.start_time,
        feed_source=_state.feed_source,
    )


@router.get("/guest.html")
async def guest_html():
    """Serve the static guest client page.

    This is the bootstrap route for browser guest flow: contains JS that
    extracts the #invite= fragment, calls POST /invites/join, and renders
    the feed + submit UI. No build step, no CDN.
    """
    _state.ensure_initialized()
    _check_not_degraded()

    static_dir = Path(__file__).resolve().parent / "static"
    guest_page = static_dir / "guest.html"
    if guest_page.exists():
        return FileResponse(guest_page, media_type="text/html")
    # Fallback: inline minimal page
    return Response(
        content=_MINIMAL_GUEST_HTML,
        media_type="text/html",
    )


# Minimal fallback guest page (only served if static/guest.html is missing).
_MINIMAL_GUEST_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spectator Mode</title>
</head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:2em auto;padding:0 1em;">
<h1>Spectator Mode</h1>
<p>The guest client bundle is missing. Reinstall the duckwork-spectator plugin.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Endpoints — C2 scope: AuthN + Invite lifecycle
# ---------------------------------------------------------------------------

class MintInviteRequest(BaseModel):
    """Request body for POST /invites."""
    session_id: str | None = Field(default=None, min_length=1, max_length=200)
    session_label: str = ""
    ttl_seconds: int = Field(default=86400, ge=60, le=604800)


class MintInviteResponse(BaseModel):
    invite_id: str
    token: str  # Raw token — returned ONCE, never stored
    token_hash_prefix: str  # First 8 chars of SHA-256 hash (for display only)
    expires_at: str
    session_label: str


class JoinInviteRequest(BaseModel):
    """Request body for POST /invites/join.

    The invite token is in the BODY, never the URL path.
    """
    token: str
    name: str = ""


class JoinInviteResponse(BaseModel):
    guest_id: str
    guest_token: str
    session_id: str
    feed_cursor: int = 0


class RevokeInviteResponse(BaseModel):
    status: str
    invite_id: str


class InviteInfo(BaseModel):
    invite_id: str
    token_hash_prefix: str
    session_label: str = ""
    created_at: str
    expires_at: str
    revoked: bool
    joined: bool
    guest_count: int


@router.post("/invites", response_model=MintInviteResponse)
async def mint_invite(
    request: MintInviteRequest,
    identity: _Identity = Depends(require_host),
):
    """Mint a new invite token. Host-only.

    Returns the raw token ONCE — it is never stored; only its SHA-256
    hash is persisted. The token should appear ONLY in the invite link
    fragment (#invite=…), never in the URL path or query string.
    """
    invite_mgr = _state.invite_mgr
    if invite_mgr is None:
        raise HTTPException(status_code=500, detail="Invite manager not initialized")

    session_id = request.session_id or _state.session_id
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "session_id_required", "message": "Choose a registered session"},
        )
    if request.session_id and request.session_id != _state.session_id:
        try:
            _registry().get(request.session_id)
        except SessionNotFoundError:
            raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})

    try:
        result = invite_mgr.mint_invite(
            session_id=session_id,
            session_gen=_state.session_gen,
            ttl_seconds=request.ttl_seconds,
            session_label=request.session_label,
        )
    except InviteError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc)})

    return MintInviteResponse(**result)


@router.get("/invites", response_model=list[InviteInfo])
async def list_invites(identity: _Identity = Depends(require_host)):
    """List active invites for this session. Host-only.

    Returns token_hash_prefix (not the full hash) and metadata.
    The raw invite token never appears in any API response.
    """
    invite_mgr = _state.invite_mgr
    if invite_mgr is None:
        raise HTTPException(status_code=500, detail="Invite manager not initialized")

    invites = invite_mgr.list_invites(_state.session_id)
    return [InviteInfo(**inv) for inv in invites]


@router.delete("/invites/{invite_id}", response_model=RevokeInviteResponse)
async def revoke_invite(
    invite_id: str,
    identity: _Identity = Depends(require_host),
):
    """Revoke an invite by invite_id (internal UUID). Host-only.

    The raw invite token never appears in the URL path — invite_id is
    the internal UUID stored alongside token_hash, not the raw token.
    """
    invite_mgr = _state.invite_mgr
    if invite_mgr is None:
        raise HTTPException(status_code=500, detail="Invite manager not initialized")

    try:
        result = invite_mgr.revoke_invite(invite_id, actor_id="host")
    except InviteError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc)})

    return RevokeInviteResponse(**result)


@router.post("/invites/join", response_model=JoinInviteResponse)
async def join_invite(request: JoinInviteRequest):
    """Guest joins session. Invite token in request body, never URL.

    Public endpoint (no auth required — the invite token itself is the
    credential). Single-use: the token is consumed on first join.
    """
    invite_mgr = _state.invite_mgr
    if invite_mgr is None:
        raise HTTPException(status_code=500, detail="Invite manager not initialized")

    try:
        result = invite_mgr.join_invite(
            raw_token=request.token,
            guest_name=request.name,
        )
    except InviteError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc)})

    return JoinInviteResponse(**result)


# ---------------------------------------------------------------------------
# Harness-neutral session bridge + guest read models
# ---------------------------------------------------------------------------

class BridgeSessionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    owner_label: str = Field(min_length=1, max_length=120)
    harness: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    repository_root: str = Field(min_length=1, max_length=4096)
    branch: str = Field(min_length=1, max_length=255)
    head_sha: str = Field(min_length=40, max_length=40, pattern=r"^[0-9a-fA-F]{40}$")


class BridgeSessionResponse(BaseModel):
    session_id: str
    owner_label: str
    harness: str
    branch: str
    head_sha: str
    capabilities: list[str]


class BridgeEventRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    type: str = Field(pattern=r"^(message|tool_call|tool_result|status_change)$")
    summary: dict[str, object]


class BridgeEventsRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    events: list[BridgeEventRequest] = Field(min_length=1, max_length=200)


class BridgeEventsResponse(BaseModel):
    accepted: int
    duplicates: int
    cursor: int


class SessionInfoResponse(BridgeSessionResponse):
    pass


class StreamEventResponse(BaseModel):
    cursor: int
    type: str
    summary: dict[str, object]
    timestamp: str


class StreamPageResponse(BaseModel):
    events: list[StreamEventResponse]
    cursor: int
    reset: bool = False
    oldest_cursor: int | None = None


class SummaryEntryResponse(BaseModel):
    entry_id: str
    cursor: int
    title: str
    body: str
    kind: str
    timestamp: str


class SummaryPageResponse(BaseModel):
    entries: list[SummaryEntryResponse]
    cursor: int
    reset: bool = False
    oldest_cursor: int | None = None


class CodeQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=100)


class CodeMatchResponse(BaseModel):
    path: str
    line: int
    snippet: str


class CodeQueryResponse(BaseModel):
    query: str
    branch: str
    head_sha: str
    matches: list[CodeMatchResponse]
    truncated: bool = False


def _session_for(identity: _Identity) -> str:
    return identity.session_id if identity.role == "guest" and identity.session_id else _state.session_id


def _registry() -> AdapterRegistry:
    registry = _state.adapter_registry
    if registry is None:
        raise HTTPException(status_code=503, detail={"error": "adapter_registry_unavailable"})
    return registry


def _service() -> SpectatorService:
    service = _state.spectator_service
    if service is None:
        raise HTTPException(status_code=503, detail={"error": "spectator_service_unavailable"})
    return service


def _descriptor_response(descriptor: SessionDescriptor) -> BridgeSessionResponse:
    return BridgeSessionResponse(
        session_id=descriptor.session_id,
        owner_label=descriptor.owner_label,
        harness=descriptor.harness,
        branch=descriptor.branch,
        head_sha=descriptor.head_sha,
        capabilities=list(descriptor.capabilities),
    )


@router.get("/bridge/sessions", response_model=list[BridgeSessionResponse])
async def list_bridge_sessions(identity: _Identity = Depends(require_host)):
    """List every session currently registered in this process. Host-only."""
    return [
        _descriptor_response(descriptor)
        for descriptor in _registry().list_descriptors()
    ]


@router.delete("/bridge/session/{session_id}", status_code=204)
async def unregister_bridge_session(
    session_id: str,
    identity: _Identity = Depends(require_host),
):
    """Remove one portable session while preserving its stored event history."""
    if session_id == _state.session_id:
        raise HTTPException(
            status_code=409,
            detail={"error": "native_session_owned_by_process"},
        )
    registry = _registry()
    try:
        registry.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"})
    registry.unregister(session_id)
    return Response(status_code=204)


@router.put("/bridge/session", response_model=BridgeSessionResponse)
async def register_bridge_session(
    request: BridgeSessionRequest,
    identity: _Identity = Depends(require_host),
):
    """Register one exact session snapshot through the portable bridge."""
    database = _state.db
    if database is None:
        raise HTTPException(status_code=503, detail={"error": "database_unavailable"})
    feed = (
        _state.feed_engine
        if request.session_id == _state.session_id and _state.feed_engine is not None
        else FeedEngine(database, request.session_id)
    )
    try:
        descriptor = SessionDescriptor(
            session_id=request.session_id,
            owner_label=request.owner_label,
            harness=request.harness,
            repository_root=Path(request.repository_root),
            branch=request.branch,
            head_sha=request.head_sha.lower(),
        )
        adapter = await asyncio.to_thread(StoredSessionAdapter, descriptor, feed)
        _registry().register(adapter, replace=True)
    except (ValueError, BranchQueryError) as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_session_snapshot", "message": str(exc)})
    return _descriptor_response(descriptor)


@router.post("/bridge/events", response_model=BridgeEventsResponse)
async def ingest_bridge_events(
    request: BridgeEventsRequest,
    identity: _Identity = Depends(require_host),
):
    """Accept privacy-safe neutral events from any harness bridge."""
    try:
        adapter = _registry().get(request.session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})
    if not isinstance(adapter, WritableSessionAdapter):
        raise HTTPException(status_code=409, detail={"error": "adapter_is_read_only"})
    events = tuple(
        EventInput(source_id=item.source_id, type=item.type, summary=item.summary)
        for item in request.events
    )
    try:
        result = await asyncio.to_thread(adapter.ingest, events)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_event", "message": str(exc)})
    return BridgeEventsResponse(**asdict(result))


@router.get("/session", response_model=SessionInfoResponse)
async def get_shared_session(identity: _Identity = Depends(require_any_auth)):
    try:
        descriptor = _registry().get(_session_for(identity)).descriptor
    except SessionNotFoundError:
        raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})
    return SessionInfoResponse(**_descriptor_response(descriptor).model_dump())


@router.get("/stream", response_model=StreamPageResponse)
async def get_live_stream(
    after: int = 0,
    limit: int = 100,
    identity: _Identity = Depends(require_any_auth),
):
    session_id = _session_for(identity)
    if session_id == _state.session_id and _state.poller is not None:
        _state.poller.start()
    try:
        page = await asyncio.to_thread(
            _service().stream,
            session_id,
            after=max(0, after),
            limit=max(1, min(limit, 200)),
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})
    return StreamPageResponse(
        events=[StreamEventResponse(**asdict(event)) for event in page.events],
        cursor=page.cursor,
        reset=page.reset,
        oldest_cursor=page.oldest_cursor,
    )


@router.get("/summary-entries", response_model=SummaryPageResponse)
async def get_summary_entries(
    after: int = 0,
    limit: int = 100,
    identity: _Identity = Depends(require_any_auth),
):
    session_id = _session_for(identity)
    if session_id == _state.session_id and _state.poller is not None:
        _state.poller.start()
    try:
        page = await asyncio.to_thread(
            _service().summaries,
            session_id,
            after=max(0, after),
            limit=max(1, min(limit, 200)),
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})
    return SummaryPageResponse(
        entries=[SummaryEntryResponse(**asdict(entry)) for entry in page.entries],
        cursor=page.cursor,
        reset=page.reset,
        oldest_cursor=page.oldest_cursor,
    )


@router.post("/code/query", response_model=CodeQueryResponse)
async def query_branch_code(
    request: CodeQueryRequest,
    identity: _Identity = Depends(require_any_auth),
):
    session_id = _session_for(identity)
    try:
        result = await asyncio.to_thread(
            _service().query_code,
            session_id,
            request.query,
            limit=request.limit,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=409, detail={"error": "session_adapter_unavailable"})
    except (ValueError, BranchQueryError) as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_code_query", "message": str(exc)})
    return CodeQueryResponse(
        query=result.query,
        branch=result.branch,
        head_sha=result.head_sha,
        matches=[CodeMatchResponse(**asdict(match)) for match in result.matches],
        truncated=result.truncated,
    )


# ---------------------------------------------------------------------------
# Feed endpoints (C3 — FeedEngine + privacy)
# ---------------------------------------------------------------------------

class FeedEventResponse(BaseModel):
    seq: int
    type: str
    summary: str
    timestamp: str


class FeedResponse(BaseModel):
    events: list[FeedEventResponse]
    reset: bool = False
    oldest_seq: int | None = None


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    since: int = 0,
    limit: int = 50,
    types: str | None = None,
    identity: _Identity = Depends(require_any_auth),
):
    """Poll event feed. Guest/Host.

    Returns structured event summaries (masked, ≤280 chars).
    Cursor-based pagination via `since` parameter.

    If the `since` cursor is older than the oldest retained event,
    returns {reset: true, oldest_seq: N} — the client resets its cursor.

    Optional `types` filter: comma-separated list of event types
    (tool_call, tool_result, message, status_change).
    """
    feed_engine = _state.feed_engine
    if feed_engine is None:
        raise HTTPException(status_code=500, detail="Feed engine not initialized")

    # Also sweep expired events on poll-cycle hot path (lazy + sweep)
    retention_days = _state.config.event_retention_days
    feed_engine.sweep_expired(retention_days=retention_days)

    # Lazy-start the transcript-tail poller thread on first authenticated
    # feed poll (idempotent). This is the producer that populates the feed.
    if _state.poller is not None:
        _state.poller.start()

    # Sweep expired pending suggestions on the same poll-cycle hot path
    # (spec: expiry is lazy + sweep; no cron/thread dependency).
    if _state.suggest_gate is not None:
        _state.suggest_gate.sweep_expired(_state.session_id)

    # Parse types filter
    event_types = None
    if types:
        event_types = [t.strip() for t in types.split(",") if t.strip()]
        valid_types = {"tool_call", "tool_result", "message", "status_change"}
        invalid = set(event_types) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_event_types", "message": f"Invalid event types: {invalid}"},
            )

    # Clamp limit
    limit = max(1, min(limit, 200))

    result = feed_engine.query(since=since, limit=limit, event_types=event_types)
    return FeedResponse(
        events=[FeedEventResponse(**e) for e in result["events"]],
        reset=result["reset"],
        oldest_seq=result.get("oldest_seq"),
    )


# ---------------------------------------------------------------------------
# WebSocket event push (C5 — /events, browser-first auth)
# ---------------------------------------------------------------------------

_WS_AUTH_TIMEOUT_SECONDS = 5.0
_WS_HEARTBEAT_SECONDS = 2.0


@router.websocket("/events")
async def events_ws(ws: WebSocket) -> None:
    """Live feed push over WebSocket. Auth via FIRST FRAME only — never a
    query-string token (the token is sensitive and must not leak into server
    logs / proxy access logs via the URL).

    Protocol:
      client →  {"op":"auth", "token":"<guest_token>"}   (within 5s)
      server →  {"op":"auth_ok", "cursor":<seq>}
               | {"op":"auth_error", "code":"<reason>"}  then close
               | {"op":"auth_error", "code":"timeout"}   then close
      server →  {"op":"feed_event", "seq":N, "type":t, "summary":s, "timestamp":ts}
      server →  {"op":"revoked"}                          then close (≤2s heartbeat)
    """
    await ws.accept()

    # Auth: first frame only.
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=_WS_AUTH_TIMEOUT_SECONDS)
    except TimeoutError:
        with contextlib.suppress(Exception):
            await ws.send_json({"op": "auth_error", "code": "timeout"})
        await ws.close(code=4001)
        return
    except WebSocketDisconnect:
        return

    try:
        frame = json.loads(raw)
    except Exception:
        frame = {}

    token = frame.get("token", "") if isinstance(frame, dict) else ""

    _state.ensure_initialized()
    if _state.degraded:
        with contextlib.suppress(Exception):
            await ws.send_json({"op": "auth_error", "code": "degraded"})
        await ws.close(code=4003)
        return

    # Guest auth via first-frame token. Host bearer is NOT accepted here —
    # this surface is guest-only (host uses ctx.socket with gateway auth).
    invite_mgr = _state.invite_mgr
    if invite_mgr is None:
        with contextlib.suppress(Exception):
            await ws.send_json({"op": "auth_error", "code": "unavailable"})
        await ws.close(code=4003)
        return

    try:
        guest_info = invite_mgr.verify_guest_token(token)
    except Exception as exc:
        status_code = getattr(exc, "status_code", 401)
        with contextlib.suppress(Exception):
            await ws.send_json({"op": "auth_error", "code": "invalid", "status": status_code})
        await ws.close(code=4002)
        return

    guest_id = guest_info["guest_id"]
    session_id = guest_info["session_id"]
    adapter = None
    if _state.adapter_registry is not None:
        try:
            adapter = _state.adapter_registry.get(session_id)
        except SessionNotFoundError:
            adapter = None
    feed_engine = _state.feed_engine if session_id == _state.session_id else None
    if adapter is None and feed_engine is None:
        with contextlib.suppress(Exception):
            await ws.send_json({"op": "auth_error", "code": "unavailable"})
        await ws.close(code=4003)
        return

    if adapter is not None:
        cursor = adapter.current_cursor()
    else:
        assert feed_engine is not None
        cursor = feed_engine.latest_seq()
    await ws.send_json({"op": "auth_ok", "cursor": cursor})

    # Start only the native source owned by this process. Portable sources push
    # through /bridge/events and need no polling thread.
    if session_id == _state.session_id and _state.poller is not None:
        _state.poller.start()

    # Push loop: send new events, re-validate revocation on a 2s heartbeat so a
    # revoked socket closes within one interval (≤2s per spec).
    while True:
        try:
            incoming = await asyncio.wait_for(ws.receive_text(), timeout=_WS_HEARTBEAT_SECONDS)
        except TimeoutError:
            incoming = None
        except WebSocketDisconnect:
            return

        # Revocation re-validation (cheap, per heartbeat + per client frame).
        if invite_mgr.is_guest_revoked(guest_id):
            with contextlib.suppress(Exception):
                await ws.send_json({"op": "revoked"})
            await ws.close(code=4003)
            return

        if incoming is not None:
            # Client pings / cursor updates are ignored; the server drives seq.
            continue

        # Push any events past the client's cursor.
        if adapter is not None:
            page = adapter.read_events(after=cursor, limit=200)
            events = [
                {
                    "seq": event.cursor,
                    "type": event.type,
                    "summary": json.dumps(dict(event.summary), separators=(",", ":")),
                    "timestamp": event.timestamp,
                }
                for event in page.events
            ]
            reset = page.reset
            oldest_seq = page.oldest_cursor
        else:
            assert feed_engine is not None
            result = feed_engine.query(since=cursor, limit=200)
            events = result["events"]
            reset = bool(result.get("reset"))
            oldest_seq = result.get("oldest_seq")

        for ev in events:
            try:
                await ws.send_json(
                    {
                        "op": "feed_event",
                        "seq": ev["seq"],
                        "type": ev["type"],
                        "summary": ev["summary"],
                        "timestamp": ev["timestamp"],
                    }
                )
            except Exception:
                return
            cursor = ev["seq"]
        if reset:
            try:
                await ws.send_json({"op": "reset", "oldest_seq": oldest_seq})
            except Exception:
                return
            cursor = oldest_seq or cursor


# ---------------------------------------------------------------------------
# Suggestion endpoints (C4 — SuggestionGate + inject_message seam)
# ---------------------------------------------------------------------------

class SubmitSuggestionRequest(BaseModel):
    # Pydantic bounds characters before the gate applies the exact UTF-8 byte
    # ceiling. This prevents an unbounded content string reaching gate logic.
    content: str = Field(max_length=MAX_CONTENT_BYTES)
    role: str = "user"


class SuggestionReceiptResponse(BaseModel):
    suggestion_id: str
    status: str
    receipt: str
    injected: bool | None = None
    delivery_id: str | None = None
    reason: str | None = None


class SuggestionListItem(BaseModel):
    id: str
    guest_id: str
    content_truncated: str
    status: str
    receipt_state: str | None = None
    created_at: str


class SuggestionListResponse(BaseModel):
    items: list[SuggestionListItem]
    total: int
    offset: int
    limit: int


class SuggestionDetailResponse(BaseModel):
    id: str
    guest_id: str
    content: str
    role: str
    status: str
    receipt_state: str | None = None
    created_at: str


def _gate() -> SuggestionGate:
    gate = _state.suggest_gate
    if gate is None:
        _state.ensure_initialized()
        gate = _state.suggest_gate
    if gate is None:
        raise HTTPException(status_code=500, detail="Suggestion gate not initialized")
    return gate


@router.post("/suggestions", response_model=SuggestionReceiptResponse)
async def submit_suggestion(
    req: SubmitSuggestionRequest,
    identity: _Identity = Depends(require_guest),
):
    """Submit a suggestion. Guest-only. Role always coerced to 'user'."""
    gate = _gate()
    try:
        result = gate.submit(
            guest_id=identity.guest_id or "",
            session_id=_state.session_id,
            content=req.content,
            role=req.role,
        )
    except SuggestionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": str(exc), "receipt_state": exc.receipt_state},
        )
    return SuggestionReceiptResponse(**result)


@router.get("/suggestions", response_model=SuggestionListResponse)
async def list_suggestions(
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
    identity: _Identity = Depends(require_any_auth),
):
    """List suggestions. Host: all; Guest: own only."""
    gate = _gate()
    guest_id = identity.guest_id if identity.role == "guest" else None
    result = gate.list_suggestions(
        _state.session_id,
        status=status_filter,
        guest_id=guest_id,
        offset=offset,
        limit=limit,
    )
    return SuggestionListResponse(
        items=[SuggestionListItem(**i) for i in result["items"]],
        total=result["total"],
        offset=result["offset"],
        limit=result["limit"],
    )


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionDetailResponse)
async def get_suggestion(
    suggestion_id: str,
    identity: _Identity = Depends(require_any_auth),
):
    """Full suggestion detail. Host: unmasked; Guest: own masked."""
    gate = _gate()
    try:
        result = gate.get_suggestion(
            suggestion_id,
            actor_role=identity.role,
            guest_id=identity.guest_id,
            session_id=_state.session_id,
        )
    except SuggestionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": str(exc), "receipt_state": exc.receipt_state},
        )
    return SuggestionDetailResponse(**result)


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionReceiptResponse)
async def approve_suggestion(
    suggestion_id: str,
    identity: _Identity = Depends(require_host),
):
    """Approve and inject. Host-only. Atomic flip + inject with idempotent delivery_id."""
    gate = _gate()
    try:
        result = gate.approve(suggestion_id, actor_role="host", session_id=_state.session_id)
    except SuggestionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": str(exc), "receipt_state": exc.receipt_state},
        )
    return SuggestionReceiptResponse(**result)


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionReceiptResponse)
async def reject_suggestion(
    suggestion_id: str,
    identity: _Identity = Depends(require_host),
):
    """Reject suggestion. Host-only."""
    gate = _gate()
    try:
        result = gate.reject(suggestion_id, actor_role="host", session_id=_state.session_id)
    except SuggestionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": str(exc), "receipt_state": exc.receipt_state},
        )
    return SuggestionReceiptResponse(**result)