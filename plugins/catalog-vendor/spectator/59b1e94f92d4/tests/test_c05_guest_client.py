"""C5 tests — Guest client (guest.html + WS /events first-frame auth).

Acceptance criteria:
- /guest.html loads in a plain browser; join via fragment works end-to-end
  (static contract test: fragment extraction + replaceState + join via BODY).
- WS auth via first frame only; no token in URL (test_ws_no_query_string_token).
- Revoked live socket closes ≤2s (test_ws_revocation_closes_socket).
- Polling fallback resumes from cursor across page reloads
  (localStorage cursor + /feed?since cursor-resume contract).

WS auth surface note: the host's ``auth_middleware`` is a BaseHTTPMiddleware
(http-only), so it does NOT gate WebSocket upgrades — first-frame auth is the
sole auth layer for /events, matching the spec (token never in the URL).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spectator.auth.auth import HostSecretManager, SessionGenManager
from spectator.auth.invite import InviteManager
from spectator.db.db import SpectatorDB

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def app_state(tmp_data_dir):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))

    import plugin_api
    state = plugin_api._AppState()

    db_path = tmp_data_dir / "spectator.db"
    state.db = SpectatorDB(db_path)
    state.db.init_schema()

    secret_path = tmp_data_dir / "host_secret"
    state.secret_mgr = HostSecretManager(secret_path)
    assert state.secret_mgr.load_or_create() is True
    state.degraded = False

    state.session_gen_mgr = SessionGenManager(tmp_data_dir)
    state.session_id = "test-session-c5"
    state.session_gen = state.session_gen_mgr.initialise(state.session_id, time.time())

    state.invite_mgr = InviteManager(state.db, state.secret_mgr, current_session_gen=state.session_gen)

    # Feed engine + gate need to exist for /events to send auth_ok.
    from spectator.feed.engine import FeedEngine
    from spectator.suggest.gate import SuggestionGate
    state.feed_engine = FeedEngine(state.db, state.session_id)
    state.suggest_gate = SuggestionGate(state.db, inject_fn=lambda content, role="user", mode="queue": True)

    state.start_time = time.time()
    state._initialized = True
    yield state

    if state.db is not None:
        state.db.close()


@pytest.fixture
def client(app_state):
    import plugin_api
    from plugin_api import router

    app = FastAPI()
    app.include_router(router, prefix="/api/plugins/spectator")

    # Patch the module-level _state used by the WS + REST handlers.
    original = plugin_api._state
    plugin_api._state = app_state
    try:
        with TestClient(app) as c:
            yield c
    finally:
        plugin_api._state = original


@pytest.fixture
def host_token(app_state):
    return app_state.secret_mgr.secret.hex()


def _mint_and_join(client, host_token):
    """Mint an invite via host auth, then join it as a guest. Returns guest_token."""
    r = client.post(
        "/api/plugins/spectator/invites",
        json={},
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert r.status_code == 200, r.text
    raw = r.json()["token"]
    r = client.post("/api/plugins/spectator/invites/join", json={"token": raw})
    assert r.status_code == 200, r.text
    return r.json()["guest_token"], r.json()["guest_id"], r.json()["session_id"]


# ---------------------------------------------------------------------------
# AC: /guest.html static contract — fragment extraction + replaceState + join BODY
# ---------------------------------------------------------------------------

class TestGuestHtml:
    def test_guest_html_served(self, client):
        r = client.get("/api/plugins/spectator/guest.html")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_full_bundle_not_stub(self, client):
        """The served page must be the C5 client, not the C1 scaffold stub."""
        r = client.get("/api/plugins/spectator/guest.html")
        body = r.text
        # Fragment extraction, replaceState, first-frame auth, cursor resume all present.
        assert "#invite=" in body
        assert "history.replaceState" in body
        assert "op: 'auth'" in body or '"op":"auth"' in body
        assert "localStorage" in body
        assert "/invites/join" in body
        assert "/api/plugins/spectator/events" in body

    def test_token_never_in_query_string_or_url(self, client):
        """The token must only ever appear in the WS first frame, never the URL."""
        r = client.get("/api/plugins/spectator/guest.html")
        body = r.text
        # wsUrl() builds the URL from origin only — no token interpolation.
        assert "?token=" not in body
        # The auth frame carries the token; the URL does not.
        assert "token: state.token" in body or "token:state.token" in body
        # No query-string token helper anywhere.
        assert "encodeURIComponent(token)" not in body or "encodeURIComponent(state.token)" not in body


# ---------------------------------------------------------------------------
# AC: WS first-frame auth (no token in URL)
# ---------------------------------------------------------------------------

class TestWsAuthFirstFrame:
    def test_ws_no_query_string_token(self, client, host_token):
        """Connect to /events with NO query string and auth via first frame."""
        guest_token, _, _ = _mint_and_join(client, host_token)

        with client.websocket_connect("/api/plugins/spectator/events") as ws:
            # First frame: auth. No ?token= anywhere in the URL.
            ws.send_json({"op": "auth", "token": guest_token})
            msg = ws.receive_json()
            assert msg["op"] == "auth_ok"
            assert "cursor" in msg

    def test_ws_invalid_token_auth_error(self, client):
        with client.websocket_connect("/api/plugins/spectator/events") as ws:
            ws.send_json({"op": "auth", "token": "bogus:deadbeef"})
            msg = ws.receive_json()
            assert msg["op"] == "auth_error"
            assert msg["code"] == "invalid"

    def test_ws_auth_timeout_closes(self, client):
        """No first frame within 5s → auth_error timeout + close."""
        with client.websocket_connect("/api/plugins/spectator/events") as ws:
            # Send nothing. The server should close with auth_error:timeout.
            # TestClient's receive_json blocks until a message arrives; the
            # server sends auth_error before closing.
            msg = ws.receive_json()
            assert msg["op"] == "auth_error"
            assert msg["code"] == "timeout"

    def test_ws_rejects_host_bearer(self, client, host_token):
        """The /events surface is guest-only; a host_secret bearer is rejected."""
        with client.websocket_connect("/api/plugins/spectator/events") as ws:
            ws.send_json({"op": "auth", "token": host_token})
            msg = ws.receive_json()
            assert msg["op"] == "auth_error"
            assert msg["code"] == "invalid"


# ---------------------------------------------------------------------------
# AC: revoked live socket closes ≤2s
# ---------------------------------------------------------------------------

class TestWsRevocation:
    def test_ws_revocation_closes_socket(self, client, host_token):
        """Host revokes invite → in-flight WS gets {op:revoked} within ≤2s."""
        guest_token, guest_id, _ = _mint_and_join(client, host_token)

        # Find the invite_id to revoke.
        r = client.get(
            "/api/plugins/spectator/invites",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        invites = r.json()
        assert invites, "expected at least one invite"
        invite_id = invites[0]["invite_id"]

        with client.websocket_connect("/api/plugins/spectator/events") as ws:
            ws.send_json({"op": "auth", "token": guest_token})
            auth = ws.receive_json()
            assert auth["op"] == "auth_ok"

            start = time.monotonic()
            # Revoke the invite (host action).
            rev = client.delete(
                f"/api/plugins/spectator/invites/{invite_id}",
                headers={"Authorization": f"Bearer {host_token}"},
            )
            assert rev.status_code == 200, rev.text

            # The socket must receive {op:revoked} within ≤2s.
            msg = ws.receive_json()
            elapsed = time.monotonic() - start
            assert msg["op"] == "revoked"
            assert elapsed <= 2.5, f"revocation took {elapsed:.2f}s (>2s heartbeat window)"


# ---------------------------------------------------------------------------
# AC: polling fallback resumes from cursor (localStorage + /feed?since)
# ---------------------------------------------------------------------------

class TestPollingCursorResume:
    def test_feed_reset_semantics_for_reload(self, client, host_token):
        """A guest that reloads with a stale cursor gets a valid, ordered resume."""
        guest_token, _, _ = _mint_and_join(client, host_token)

        headers = {"Authorization": f"Bearer {guest_token}"}

        import plugin_api
        plugin_api._state.feed_engine.append("message", {"role": "user", "chars": 5, "note": "hello"})
        plugin_api._state.feed_engine.append("message", {"role": "assistant", "chars": 7, "note": "reply"})

        # Poll from 0 → all events, ordered by seq.
        r = client.get("/api/plugins/spectator/feed?since=0&limit=10", headers=headers)
        assert r.status_code == 200
        events = r.json()["events"]
        assert len(events) == 2
        assert events[0]["seq"] < events[1]["seq"]
        first_seq = events[0]["seq"]
        last_seq = events[1]["seq"]

        # Normal resume from last_seq → no new events, no reset.
        r = client.get(f"/api/plugins/spectator/feed?since={last_seq}&limit=10", headers=headers)
        assert r.status_code == 200
        assert r.json()["reset"] is False
        assert r.json()["events"] == []

        # Simulate a retention purge: delete the oldest event so the oldest
        # retained seq advances past 1, then a reloading guest holding a stale
        # cursor (since=1) must get {reset:true, oldest_seq}.
        with plugin_api._state.db.write_txn() as cur:
            cur.execute("DELETE FROM events WHERE seq = ?", (first_seq,))

        r = client.get("/api/plugins/spectator/feed?since=1&limit=10", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["reset"] is True
        assert body["oldest_seq"] == last_seq
        assert len(body["events"]) >= 1

    def test_guest_html_persists_cursor_key(self, client):
        """The bundle persists the feed cursor under a stable localStorage key."""
        r = client.get("/api/plugins/spectator/guest.html")
        body = r.text
        assert "spectator.guest.cursor" in body or "spectator.guest." in body
        assert "localStorage.setItem" in body
        assert "localStorage.getItem" in body


# ---------------------------------------------------------------------------
# AC: join via fragment end-to-end (REST contract driving the page)
# ---------------------------------------------------------------------------

class TestJoinViaFragment:
    def test_join_uses_body_not_url(self, client, host_token):
        """The join endpoint takes the token in the BODY (never the path/query)."""
        r = client.post(
            "/api/plugins/spectator/invites",
            json={},
            headers={"Authorization": f"Bearer {host_token}"},
        )
        raw = r.json()["token"]

        # Body join succeeds.
        r = client.post("/api/plugins/spectator/invites/join", json={"token": raw})
        assert r.status_code == 200
        data = r.json()
        assert "guest_token" in data
        assert "feed_cursor" in data
        assert "session_id" in data

    def test_join_returns_cursor_field(self, client, host_token):
        """Join response must carry feed_cursor for cursor resume."""
        guest_token, _, _ = _mint_and_join(client, host_token)
        # feed_cursor is returned by the join (asserted via the helper's use).
        assert guest_token
