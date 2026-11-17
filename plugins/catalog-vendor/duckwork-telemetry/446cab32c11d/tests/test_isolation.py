"""Isolation contract — the test suite must never read or write the developer's
real ~/.duckwork. DUCKWORK_HOME is the single source of truth for locating Duckwork
files; no code path may fall back to Path.home()/.duckwork when DUCKWORK_HOME is set.

These tests fail-closed: they plant a POISONED file at Path.home()/.duckwork and
assert it is never consulted. They deliberately patch Path.home() directly, so
they catch escapes even though the conftest baseline also pins HOME as a safety
net (otherwise the net would mask the very bug we want to detect).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import duckwork_telemetry.budget as budget
import duckwork_telemetry.db as db


def test_path_helpers_resolve_under_duckwork_home(tmp_path, monkeypatch):
    """The path helpers must derive from DUCKWORK_HOME, not Path.home()."""
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path))
    assert budget._budget_path() == tmp_path / "telemetry" / "budget.yaml"
    assert budget._pricing_path() == tmp_path / "telemetry" / "pricing.yaml"


def test_budget_status_ignores_real_home_pricing(tmp_path, monkeypatch):
    """Regression for the Path.home() escape in _status_block: the estimated-
    price warning must read pricing.yaml from DUCKWORK_HOME, never Path.home().

    DUCKWORK_HOME gets a clean pricing.yaml (no estimated-price models); a decoy
    "real home" gets a poisoned one (with estimated-price models). If any code
    reads Path.home(), the warning surfaces and this test fails.
    """
    # DUCKWORK_HOME → clean pricing.yaml
    hh = tmp_path / "duckwork_home" / "telemetry"
    hh.mkdir(parents=True)
    (hh / "pricing.yaml").write_text("models: {}\n")
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "duckwork_home"))

    # Decoy "real home" → poisoned pricing.yaml (has estimated-price models)
    decoy_home = tmp_path / "decoy_home"
    decoy_tele = decoy_home / ".duckwork" / "telemetry"
    decoy_tele.mkdir(parents=True)
    (decoy_tele / "pricing.yaml").write_text(
        textwrap.dedent(
            """
            models: {}
            _meta:
              estimated_price_models:
              - poison/should-never-be-read
            """
        )
    )
    monkeypatch.setattr(Path, "home", lambda: decoy_home)

    db._local.conn = None
    budget.reload_config()
    out = budget._status_block()

    # If _status_block read Path.home() (the decoy), the estimated-price warning
    # would appear. With DUCKWORK_HOME clean, it must not.
    assert "estimated pricing" not in out, (
        "budget._status_block() read pricing.yaml from Path.home() instead of "
        "DUCKWORK_HOME — real-home isolation is broken"
    )


def test_conftest_neutralizes_ambient_telemetry_home():
    """The autouse isolation fixture must clear DUCKWORK_TELEMETRY_HOME so a
    developer's ambient value cannot override the tmp DUCKWORK_HOME and leak the
    suite into the real telemetry dir."""
    import os

    assert "DUCKWORK_TELEMETRY_HOME" not in os.environ


def test_telemetry_home_precedence_stays_in_tmp():
    """With the fixture active and no ambient var, telemetry resolves under the
    tmp DUCKWORK_HOME — never the developer's real ~/.duckwork."""
    import os

    import duckwork_telemetry.paths as paths

    assert paths.get_telemetry_home() == Path(os.environ["DUCKWORK_HOME"]) / "telemetry"


def test_budget_paths_honor_telemetry_home(tmp_path, monkeypatch):
    """budget._budget_path / _pricing_path route through the canonical home."""
    import duckwork_telemetry.budget as budget

    monkeypatch.setenv("DUCKWORK_TELEMETRY_HOME", str(tmp_path / "shared"))
    monkeypatch.setenv("DUCKWORK_HOME", str(tmp_path / "profile"))
    tele = tmp_path / "shared" / "telemetry"
    assert budget._budget_path() == tele / "budget.yaml"
    assert budget._pricing_path() == tele / "pricing.yaml"
