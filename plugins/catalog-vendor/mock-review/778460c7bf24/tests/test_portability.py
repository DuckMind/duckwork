"""Windows defaults, simulated on any OS (monkeypatched sys.platform / env)."""

import sys
from pathlib import Path

from mockreview import owner, settings


def test_duckwork_home_windows_default_is_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("DUCKWORK_HOME", raising=False)
    monkeypatch.delenv("DUCKWORK_DATA_DIR_SUFFIX", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert settings.duckwork_home() == tmp_path / "Local" / "duckwork"
    assert owner.default_owner_root() == tmp_path / "Local" / "duckwork" / "workspace" / "mock-reviews"
    monkeypatch.setenv("LOCALAPPDATA", "  ")                     # unset/blank: the usual place under the profile
    assert settings.duckwork_home() == Path.home() / "AppData" / "Local" / "duckwork"
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "explicit"))  # DUCKWORK_HOME still wins
    assert settings.duckwork_home() == tmp_path / "explicit"
    assert owner.default_owner_root() == tmp_path / "explicit" / "workspace" / "mock-reviews"


def test_duckwork_home_posix_default(monkeypatch):
    monkeypatch.delenv("DUCKWORK_HOME", raising=False)
    monkeypatch.delenv("DUCKWORK_DATA_DIR_SUFFIX", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert settings.duckwork_home() == Path.home() / ".duckwork"
    monkeypatch.setenv("DUCKWORK_DATA_DIR_SUFFIX", "-dev")          # same suffix rule as Duckwork
    assert settings.duckwork_home() == Path.home() / ".duckwork-dev"


def test_owner_error_names_no_service_manager(monkeypatch, tmp_path):
    """The 'no server' refusal tells the user what to run, on any OS (no launchd label)."""
    monkeypatch.setenv("MOCKREVIEW_OWNER", "auto")
    monkeypatch.setenv("MOCKREVIEW_HOME", str(tmp_path / "private"))
    monkeypatch.setenv("MOCKREVIEW_LOCAL_BASE", "http://127.0.0.1:9")    # nothing listens on the discard port
    try:
        owner.resolve()
    except owner.OwnerError as e:
        assert "duckwork mockreview serve" in e.message and "autostart" in e.message
        assert "launchd" not in e.message and "com." not in e.message
    else:
        raise AssertionError("resolve() should refuse a private store with no server")
