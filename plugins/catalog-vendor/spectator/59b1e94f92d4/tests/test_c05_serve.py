"""C5 serve.py — standalone guest-facing namespace (host-auth bypass).

Verifies the plain-browser guest flow end-to-end: the standalone app mounts the
SAME router with NO host session-token auth in front, so a guest browser's
bearer token reaches the plugin routes. The plugin's own auth layers (WS
first-frame HMAC, bearer guest_token, public /guest.html + /invites/join)
remain the only boundary — exactly as the host-mounted path would be for WS,
but now also for HTTP.

This closes the integration gap that would otherwise orphan the guest client:
the host dashboard's auth_middleware gates every /api/ route, so a browser
guest could only ever reach /events (WS is exempt) — never /guest.html, join,
feed, or suggestions.

The test builds an ISOLATED _AppState (temp data dir) and patches
plugin_api._state — it never touches the real profile-local Spectator data.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "src"))
    sys.path.insert(0, str(repo_root / "dashboard"))

    import plugin_api

    from spectator.auth.auth import HostSecretManager, SessionGenManager
    from spectator.auth.invite import InviteManager
    from spectator.db.db import SpectatorDB
    from spectator.feed.engine import FeedEngine
    from spectator.suggest.gate import SuggestionGate

    state = plugin_api._AppState()
    data_dir = tmp_path / "spectator"
    data_dir.mkdir()

    state.db = SpectatorDB(data_dir / "spectator.db")
    state.db.init_schema()

    state.secret_mgr = HostSecretManager(data_dir / "host_secret")
    assert state.secret_mgr.load_or_create() is True
    state.degraded = False

    state.session_gen_mgr = SessionGenManager(data_dir)
    state.session_id = "serve-test-session"
    state.session_gen = state.session_gen_mgr.initialise(state.session_id, time.time())
    state.invite_mgr = InviteManager(state.db, state.secret_mgr, current_session_gen=state.session_gen)

    state.feed_engine = FeedEngine(state.db, state.session_id)
    state.suggest_gate = SuggestionGate(state.db, inject_fn=lambda content, role="user", mode="queue": True)

    state.start_time = time.time()
    state._initialized = True

    # Import the standalone app (mounts the SAME router, no host auth) and
    # patch its plugin_api._state to our isolated one.
    from spectator.serve import app as serve_app
    original = plugin_api._state
    plugin_api._state = state
    try:
        with TestClient(serve_app) as client:
            yield client
    finally:
        plugin_api._state = original
        state.db.close()


def _mint_and_join(app, host):
    mint = app.post(
        "/api/plugins/spectator/invites",
        json={},
        headers={"Authorization": f"Bearer {host}"},
    )
    raw = mint.json()["token"]
    join = app.post("/api/plugins/spectator/invites/join", json={"token": raw})
    return join.json()["guest_token"]


class TestStandaloneNamespace:
    def _host_token(self, app):
        import plugin_api
        return plugin_api._state.secret_mgr.secret.hex()

    def test_guest_html_served_without_host_auth(self, app):
        """/guest.html must be reachable with NO host session token."""
        r = app.get("/api/plugins/spectator/guest.html")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_invite_join_full_guest_flow(self, app):
        """Host mints via bearer, guest joins via fragment-body token, feeds."""
        host = self._host_token(app)

        mint = app.post(
            "/api/plugins/spectator/invites",
            json={},
            headers={"Authorization": f"Bearer {host}"},
        )
        assert mint.status_code == 200, mint.text
        raw = mint.json()["token"]

        join = app.post("/api/plugins/spectator/invites/join", json={"token": raw})
        assert join.status_code == 200, join.text
        guest_token = join.json()["guest_token"]

        feed = app.get(
            "/api/plugins/spectator/feed?since=0&limit=10",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert feed.status_code == 200, feed.text
        assert "events" in feed.json()

    def test_ws_first_frame_auth_standalone(self, app):
        """WS /events works standalone with first-frame auth, no query token."""
        host = self._host_token(app)

        mint = app.post(
            "/api/plugins/spectator/invites",
            json={},
            headers={"Authorization": f"Bearer {host}"},
        )
        raw = mint.json()["token"]
        join = app.post("/api/plugins/spectator/invites/join", json={"token": raw})
        guest_token = join.json()["guest_token"]

        with app.websocket_connect("/api/plugins/spectator/events") as ws:
            ws.send_json({"op": "auth", "token": guest_token})
            msg = ws.receive_json()
            assert msg["op"] == "auth_ok"
            assert "cursor" in msg
