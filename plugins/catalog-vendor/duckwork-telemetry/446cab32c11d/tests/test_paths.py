"""paths.py — single source of truth for telemetry file locations."""

from pathlib import Path

import duckwork_telemetry.paths as paths


def test_prefers_telemetry_home_over_duckwork_home(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKWORK_TELEMETRY_HOME", str(tmp_path / "shared"))
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "profile"))
    assert paths.get_telemetry_home() == tmp_path / "shared" / "telemetry"


def test_falls_back_to_duckwork_home_when_telemetry_home_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("DUCKWORK_TELEMETRY_HOME", raising=False)
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "profile"))
    assert paths.get_telemetry_home() == tmp_path / "profile" / "telemetry"


def test_defaults_to_dot_duckwork_when_both_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("DUCKWORK_TELEMETRY_HOME", raising=False)
    monkeypatch.delenv("DUCKWORK_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert paths.get_telemetry_home() == tmp_path / ".duckwork" / "telemetry"


def test_get_db_path_creates_telemetry_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("DUCKWORK_TELEMETRY_HOME", raising=False)
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "profile"))
    db_path = paths.get_db_path()
    assert db_path == tmp_path / "profile" / "telemetry" / "telemetry.db"
    assert db_path.parent.is_dir()


def test_budget_and_pricing_paths_do_not_create_dir(tmp_path, monkeypatch):
    """Resolving budget/pricing paths must be pure (no mkdir) so an unwritable
    canonical home never turns a read into a crash."""
    monkeypatch.delenv("DUCKWORK_TELEMETRY_HOME", raising=False)
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "profile"))
    paths.get_budget_path()
    paths.get_pricing_path()
    assert not (tmp_path / "profile" / "telemetry").exists()


def test_db_budget_pricing_share_one_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKWORK_TELEMETRY_HOME", str(tmp_path / "shared"))
    tele = tmp_path / "shared" / "telemetry"
    assert paths.get_db_path() == tele / "telemetry.db"
    assert paths.get_budget_path() == tele / "budget.yaml"
    assert paths.get_pricing_path() == tele / "pricing.yaml"
