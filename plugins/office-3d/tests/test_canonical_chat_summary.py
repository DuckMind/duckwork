"""Office canonical-chat projection: exact owner/title, recent not live, no content."""

import contextlib
import importlib.util
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace

import pytest

from duckwork_state import SessionDB


API = Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
EMPTY = {
    "latest_session_id": None,
    "current_task": None,
    "current_model": None,
    "recent_task": None,
    "recent_model": None,
}


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    spec = importlib.util.spec_from_file_location("office_canonical_summary", API)
    assert spec is not None and spec.loader is not None
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    monkeypatch.setattr(api, "DUCKWORK_HOME", str(tmp_path))
    with contextlib.ExitStack() as stack:
        stores = {}
        for profile in ("default", "accounting"):
            home = tmp_path if profile == "default" else tmp_path / "profiles" / profile
            home.mkdir(parents=True, exist_ok=True)
            stores[profile] = stack.enter_context(contextlib.closing(SessionDB(home / "state.db")))
        try:
            yield api, stores
        finally:
            api._close_all_ro_conns()


def record(db, sid, title, model, *, age=0, hidden=True, archived=False):
    db.create_session(sid, "cli", model=model)
    assert db.set_session_title(sid, title)
    assert db.set_session_hidden(sid, hidden)
    if archived:
        assert db.set_session_archived(sid, True, notify=False)
    # Seed recorded recency, NOT a live gateway execution. The production schema
    # and unique title registry are created by SessionDB, not a copied schema.
    with contextlib.closing(sqlite3.connect(db.db_path)) as conn:
        conn.execute(
            "UPDATE sessions SET started_at=?, last_activity_at=? WHERE id=?",
            (time.time() - age - 20, time.time() - age, sid),
        )
        conn.commit()


@pytest.mark.parametrize("profile", ["default", "accounting"])
@pytest.mark.parametrize("older_side_chat", [False, True])
def test_canonical_chat_recent_metadata_is_owned_and_not_current(office, profile, older_side_chat):
    api, stores = office
    other = "accounting" if profile == "default" else "default"
    record(stores[other], "other-chat", "Bot Chat", "other-private-model")
    owner = stores[profile]
    if older_side_chat:
        record(owner, "side-chat", "Old task", "old-model", age=300, hidden=False)
    record(owner, "owner-chat", "Bot Chat", "owner-recorded-model")
    # The registry itself confirms exact identity in the owning real DB.
    assert owner.get_session_by_title(SessionDB.CANONICAL_BOT_CHAT_TITLE)["id"] == "owner-chat"
    result = api._read_session_metadata(profile)
    assert result == {
        "latest_session_id": "owner-chat",
        "current_task": None,
        "current_model": None,
        "recent_task": "Bot Chat",
        "recent_model": "owner-recorded-model",
    }
    assert "other-private-model" not in str(result)


@pytest.mark.parametrize("title", ["Internal automation", "Bot Chat #2", "bot chat", "Bot Chat (API other)"])
def test_arbitrary_hidden_sessions_are_not_canonical(office, title):
    api, stores = office
    record(stores["accounting"], "hidden-other", title, "hidden-private-model")
    assert api._read_session_metadata("accounting") == EMPTY


def test_archived_canonical_chat_stays_private(office):
    api, stores = office
    record(stores["accounting"], "retired-chat", "Bot Chat", "retired-private-model", archived=True)
    assert api._read_session_metadata("accounting") == EMPTY


def test_other_profiles_canonical_chat_is_not_a_fallback(office):
    api, stores = office
    record(stores["default"], "root-chat", "Bot Chat", "root-private-model")
    assert api._read_session_metadata("accounting") == EMPTY
    with pytest.raises(ValueError):
        api._read_session_metadata("../default")


@pytest.mark.parametrize("gateway_running", [False, True])
@pytest.mark.parametrize("hidden", [False, True])
def test_recorded_recency_without_running_evidence_is_not_current_work(
    office, monkeypatch, gateway_running, hidden
):
    api, stores = office
    title = "Bot Chat" if hidden else "Recorded task"
    record(stores["accounting"], "recent-only", title, "recorded-model", hidden=hidden)
    monkeypatch.setattr(
        api, "resolve_gateway_liveness",
        lambda **kwargs: SimpleNamespace(running=gateway_running, source="multiplexer"),
    )
    result = api._read_profile("accounting")
    assert result["recent_task"] == title
    assert result["recent_model"] == "recorded-model"
    assert (result["current_task"], result["current_model"]) == (None, None)


def test_newer_visible_chat_is_still_the_most_recent_record(office):
    api, stores = office
    record(stores["accounting"], "canonical", "Bot Chat", "older-model", age=300)
    record(stores["accounting"], "visible", "Newer work", "newer-model", hidden=False)
    result = api._read_session_metadata("accounting")
    assert result["latest_session_id"] == "visible"
    assert result["recent_task"] == "Newer work"
    assert result["recent_model"] == "newer-model"
    assert (result["current_task"], result["current_model"]) == (None, None)


def test_canonical_projection_never_reads_messages_or_prompts(office):
    api, stores = office
    record(stores["accounting"], "canonical", "Bot Chat", "recorded-model")
    allowed = {"id", "title", "model", "hidden", "archived", "last_activity_at", "started_at"}
    forbidden_reads = []

    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and (table != "sessions" or column not in allowed):
            forbidden_reads.append((table, column))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    with api._db_lock:
        conn = api._get_ro_conn_unlocked(api._db_path("accounting"))
        assert conn is not None
        conn.set_authorizer(authorize)
    try:
        result = api._read_session_metadata("accounting")
    finally:
        conn.set_authorizer(None)
    assert forbidden_reads == []
    assert result == {
        "latest_session_id": "canonical",
        "current_task": None,
        "current_model": None,
        "recent_task": "Bot Chat",
        "recent_model": "recorded-model",
    }
