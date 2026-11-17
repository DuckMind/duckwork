"""Behavioural rebuild gates for the harness-neutral Spectator surface."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_repo(root: Path) -> tuple[str, str]:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "spectator-tests@example.invalid")
    _git(root, "config", "user.name", "Spectator Tests")
    (root / "service.py").write_text(
        "def calculate_total(items):\n"
        "    return sum(item.price for item in items)\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Portable branch fixture\n", encoding="utf-8")
    _git(root, "add", "service.py", "README.md")
    _git(root, "commit", "-qm", "fixture")
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    return branch, head


def _client(tmp_path: Path, session_id: str = "portable-session"):
    from dashboard import plugin_api

    old_state = plugin_api._state
    if old_state.poller is not None:
        old_state.poller.stop()
    if old_state.db is not None:
        old_state.db.close()

    plugin_api._state = plugin_api._AppState()
    plugin_api.init_plugin(
        config_path=tmp_path / "missing-config.yaml",
        data_dir=tmp_path / "spectator-data",
        session_id=session_id,
    )
    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/spectator")
    client = TestClient(app)
    host_token = plugin_api._state.secret_mgr.secret.hex()
    return client, host_token, plugin_api


def _guest_token(client: TestClient, host_token: str) -> str:
    host_headers = {"Authorization": f"Bearer {host_token}"}
    mint = client.post(
        "/api/plugins/spectator/invites",
        headers=host_headers,
        json={"session_label": "Portable session"},
    )
    assert mint.status_code == 200, mint.text
    joined = client.post(
        "/api/plugins/spectator/invites/join",
        json={"token": mint.json()["token"]},
    )
    assert joined.status_code == 200, joined.text
    return joined.json()["guest_token"]


def test_portable_harness_workflow_exposes_stream_summary_and_branch_query(tmp_path):
    repo = tmp_path / "branch"
    branch, head = _make_repo(repo)
    client, host_token, plugin_api = _client(tmp_path)
    host_headers = {"Authorization": f"Bearer {host_token}"}

    registered = client.put(
        "/api/plugins/spectator/bridge/session",
        headers=host_headers,
        json={
            "session_id": "portable-session",
            "owner_label": "Remote builder",
            "harness": "codex",
            "repository_root": str(repo),
            "branch": branch,
            "head_sha": head,
        },
    )
    assert registered.status_code == 200, registered.text
    assert registered.json()["capabilities"] == [
        "live_stream",
        "summary_entries",
        "branch_query",
    ]
    from spectator.core.contracts import SessionAdapter

    adapter = plugin_api._state.adapter_registry.get("portable-session")
    assert isinstance(adapter, SessionAdapter)

    first_ingest = client.post(
        "/api/plugins/spectator/bridge/events",
        headers=host_headers,
        json={
            "session_id": "portable-session",
            "events": [
                {
                    "source_id": "codex-1",
                    "type": "message",
                    "summary": {
                        "role": "assistant",
                        "chars": 42,
                        "note": "implemented total calculation",
                    },
                },
                {
                    "source_id": "codex-2",
                    "type": "tool_call",
                    "summary": {
                        "tool": "pytest",
                        "args": 1,
                        "note": "ran focused tests",
                    },
                },
            ],
        },
    )
    assert first_ingest.status_code == 200, first_ingest.text
    assert first_ingest.json() == {"accepted": 2, "duplicates": 0, "cursor": 2}

    duplicate_ingest = client.post(
        "/api/plugins/spectator/bridge/events",
        headers=host_headers,
        json={
            "session_id": "portable-session",
            "events": [
                {
                    "source_id": "codex-2",
                    "type": "tool_call",
                    "summary": {
                        "tool": "pytest",
                        "args": 1,
                        "note": "ran focused tests",
                    },
                }
            ],
        },
    )
    assert duplicate_ingest.status_code == 200, duplicate_ingest.text
    assert duplicate_ingest.json()["duplicates"] == 1

    guest_token = _guest_token(client, host_token)
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    stream = client.get(
        "/api/plugins/spectator/stream?after=0",
        headers=guest_headers,
    )
    assert stream.status_code == 200, stream.text
    assert [event["type"] for event in stream.json()["events"]] == [
        "message",
        "tool_call",
    ]
    assert stream.json()["cursor"] == 2

    summaries = client.get(
        "/api/plugins/spectator/summary-entries?after=0",
        headers=guest_headers,
    )
    assert summaries.status_code == 200, summaries.text
    data = summaries.json()
    assert data["cursor"] == 2
    assert [entry["title"] for entry in data["entries"]] == [
        "Assistant update",
        "Tool call: pytest",
    ]
    assert data["entries"][0]["body"] == "implemented total calculation · 42 characters"

    query = client.post(
        "/api/plugins/spectator/code/query",
        headers=guest_headers,
        json={"query": "calculate_total", "limit": 10},
    )
    assert query.status_code == 200, query.text
    result = query.json()
    assert result["branch"] == branch
    assert result["head_sha"] == head
    assert result["matches"][0]["path"] == "service.py"
    assert result["matches"][0]["line"] == 1
    assert "calculate_total" in result["matches"][0]["snippet"]

    plugin_api._state.poller.stop()


def test_branch_query_excludes_secret_files_untracked_files_and_redacts_inline_values(tmp_path):
    from spectator.code.query import GitBranchQuery

    repo = tmp_path / "branch"
    _make_repo(repo)
    (repo / "settings.py").write_text('password="hunter2"\n', encoding="utf-8")
    (repo / ".env").write_text("ENV_ONLY_TOKEN=never-show-this\n", encoding="utf-8")
    _git(repo, "add", "settings.py", ".env")
    _git(repo, "commit", "-qm", "add privacy fixtures")
    (repo / "untracked.py").write_text("UNTRACKED_PRIVATE_VALUE = 1\n", encoding="utf-8")
    branch = _git(repo, "branch", "--show-current")
    head = _git(repo, "rev-parse", "HEAD")

    query = GitBranchQuery(repo, branch, head)
    inline = query.query("password")
    assert len(inline.matches) == 1
    assert "hunter2" not in inline.matches[0].snippet
    assert "password=***" in inline.matches[0].snippet
    assert query.query("ENV_ONLY_TOKEN").matches == ()
    assert query.query("UNTRACKED_PRIVATE_VALUE").matches == ()


def test_neutral_bridge_accepts_every_supported_harness_name(tmp_path):
    repo = tmp_path / "branch"
    branch, head = _make_repo(repo)
    supported = [
        "claude-code",
        "codex",
        "duckwork",
        "pi",
        "opencode",
        "commandcode",
        "generic",
    ]

    for harness in supported:
        client, host_token, plugin_api = _client(tmp_path / harness, session_id=harness)
        response = client.put(
            "/api/plugins/spectator/bridge/session",
            headers={"Authorization": f"Bearer {host_token}"},
            json={
                "session_id": harness,
                "owner_label": "Builder",
                "harness": harness,
                "repository_root": str(repo),
                "branch": branch,
                "head_sha": head,
            },
        )
        assert response.status_code == 200, (harness, response.text)
        assert response.json()["harness"] == harness

        headers = {"Authorization": f"Bearer {host_token}"}
        ingested = client.post(
            "/api/plugins/spectator/bridge/events",
            headers=headers,
            json={
                "session_id": harness,
                "events": [
                    {
                        "source_id": f"{harness}-1",
                        "type": "status_change",
                        "summary": {"from": "starting", "to": "active"},
                    }
                ],
            },
        )
        assert ingested.status_code == 200, (harness, ingested.text)
        stream = client.get("/api/plugins/spectator/stream?after=0", headers=headers)
        assert stream.status_code == 200, (harness, stream.text)
        assert stream.json()["events"][0]["type"] == "status_change"
        code = client.post(
            "/api/plugins/spectator/code/query",
            headers=headers,
            json={"query": "calculate_total"},
        )
        assert code.status_code == 200, (harness, code.text)
        assert code.json()["matches"][0]["path"] == "service.py"
        plugin_api._state.poller.stop()


def test_duckwork_native_adapter_discovers_session_without_bridge_registration(tmp_path, monkeypatch):
    repo = tmp_path / "branch"
    branch, head = _make_repo(repo)
    state_db = tmp_path / "state.db"
    conn = sqlite3.connect(state_db)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            cwd TEXT,
            git_branch TEXT,
            git_repo_root TEXT,
            display_name TEXT,
            profile_name TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            tool_name TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
        ("duckwork-native", str(repo), branch, str(repo), "Live builder", "default"),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        ("duckwork-native", "assistant", "finished implementation"),
    )
    conn.commit()
    conn.close()

    from dashboard import plugin_api

    monkeypatch.setattr(plugin_api, "DEFAULT_STATE_DB_PATH", state_db)
    client, host_token, plugin_api = _client(tmp_path, session_id="duckwork-native")
    headers = {"Authorization": f"Bearer {host_token}"}

    session = client.get("/api/plugins/spectator/session", headers=headers)
    assert session.status_code == 200, session.text
    assert session.json()["harness"] == "duckwork"
    assert session.json()["branch"] == branch
    assert session.json()["head_sha"] == head

    plugin_api._state.poller.poll_once()
    stream = client.get("/api/plugins/spectator/stream?after=0", headers=headers)
    assert stream.status_code == 200, stream.text
    assert stream.json()["events"][0]["type"] == "message"
    plugin_api._state.poller.stop()


def test_portable_sidecar_can_own_a_non_duckwork_session(tmp_path):
    repo = tmp_path / "branch"
    branch, head = _make_repo(repo)
    client, host_token, plugin_api = _client(tmp_path, session_id="")
    host_headers = {"Authorization": f"Bearer {host_token}"}

    registered = client.put(
        "/api/plugins/spectator/bridge/session",
        headers=host_headers,
        json={
            "session_id": "external-session",
            "owner_label": "External builder",
            "harness": "generic",
            "repository_root": str(repo),
            "branch": branch,
            "head_sha": head,
        },
    )
    assert registered.status_code == 200, registered.text
    sessions = client.get("/api/plugins/spectator/bridge/sessions", headers=host_headers)
    assert sessions.status_code == 200, sessions.text
    assert [item["session_id"] for item in sessions.json()] == ["external-session"]

    ingested = client.post(
        "/api/plugins/spectator/bridge/events",
        headers=host_headers,
        json={
            "session_id": "external-session",
            "events": [
                {
                    "source_id": "external-1",
                    "type": "message",
                    "summary": {"role": "assistant", "chars": 12, "note": "assistant reply"},
                }
            ],
        },
    )
    assert ingested.status_code == 200, ingested.text

    minted = client.post(
        "/api/plugins/spectator/invites",
        headers=host_headers,
        json={"session_id": "external-session", "session_label": "External session"},
    )
    assert minted.status_code == 200, minted.text
    joined = client.post(
        "/api/plugins/spectator/invites/join",
        json={"token": minted.json()["token"]},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["session_id"] == "external-session"

    guest_headers = {"Authorization": f"Bearer {joined.json()['guest_token']}"}
    stream = client.get("/api/plugins/spectator/stream?after=0", headers=guest_headers)
    assert stream.status_code == 200, stream.text
    assert stream.json()["events"][0]["summary"]["note"] == "assistant reply"

    removed = client.delete(
        "/api/plugins/spectator/bridge/session/external-session",
        headers=host_headers,
    )
    assert removed.status_code == 204, removed.text
    sessions = client.get("/api/plugins/spectator/bridge/sessions", headers=host_headers)
    assert sessions.json() == []
    plugin_api._state.poller.stop()


def test_portable_websocket_uses_the_guest_session_adapter(tmp_path):
    repo = tmp_path / "branch"
    branch, head = _make_repo(repo)
    client, host_token, plugin_api = _client(tmp_path, session_id="")
    host_headers = {"Authorization": f"Bearer {host_token}"}
    session_id = "external-websocket"
    registered = client.put(
        "/api/plugins/spectator/bridge/session",
        headers=host_headers,
        json={
            "session_id": session_id,
            "owner_label": "External builder",
            "harness": "generic",
            "repository_root": str(repo),
            "branch": branch,
            "head_sha": head,
        },
    )
    assert registered.status_code == 200, registered.text
    ingested = client.post(
        "/api/plugins/spectator/bridge/events",
        headers=host_headers,
        json={
            "session_id": session_id,
            "events": [
                {
                    "source_id": "ws-1",
                    "type": "status_change",
                    "summary": {"from": "starting", "to": "active"},
                }
            ],
        },
    )
    assert ingested.status_code == 200, ingested.text
    minted = client.post(
        "/api/plugins/spectator/invites",
        headers=host_headers,
        json={"session_id": session_id},
    )
    joined = client.post(
        "/api/plugins/spectator/invites/join",
        json={"token": minted.json()["token"]},
    )
    guest_token = joined.json()["guest_token"]

    with client.websocket_connect("/api/plugins/spectator/events") as ws:
        ws.send_json({"op": "auth", "token": guest_token})
        auth = ws.receive_json()
        assert auth["op"] == "auth_ok"
        assert auth["cursor"] == 1
        pushed = client.post(
            "/api/plugins/spectator/bridge/events",
            headers=host_headers,
            json={
                "session_id": session_id,
                "events": [
                    {
                        "source_id": "ws-2",
                        "type": "message",
                        "summary": {"role": "assistant", "chars": 5, "note": "assistant reply"},
                    }
                ],
            },
        )
        assert pushed.status_code == 200, pushed.text
        frame = ws.receive_json()
        assert frame["op"] == "feed_event"
        assert frame["seq"] == 2
        assert json.loads(frame["summary"])["note"] == "assistant reply"
    plugin_api._state.poller.stop()


def test_guest_frontend_contains_the_three_functional_views(tmp_path):
    client, _, plugin_api = _client(tmp_path)
    response = client.get("/api/plugins/spectator/guest.html")
    assert response.status_code == 200
    html = response.text
    assert 'id="live-stream"' in html
    assert 'id="summary-entries"' in html
    assert 'id="branch-query"' in html
    assert "/stream?after=" in html
    assert "/summary-entries?after=" in html
    assert "/code/query" in html
    assert "DUCKWORK_SESSION_ID" not in html
    assert "claude-code" not in html.lower()
    plugin_api._state.poller.stop()
