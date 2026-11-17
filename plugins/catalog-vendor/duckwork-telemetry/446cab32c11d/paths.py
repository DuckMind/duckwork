"""Single source of truth for duckwork-telemetry state-file locations.

Resolves the telemetry directory with an opt-in canonical home:
  1. DUCKWORK_TELEMETRY_HOME  — shared cost-center dir, if set
  2. DUCKWORK_HOME            — this profile's Duckwork home
  3. ~/.duckwork              — default

get_telemetry_home() is a PURE resolver — it never creates the directory.
Only get_db_path() creates it, because the DB writes there. The budget/pricing
path getters stay pure so an unwritable canonical home never turns a read into
a crash — absence of budget.yaml is the "budgets disabled" signal, not an error.

Governs telemetry files ONLY (telemetry.db, budget.yaml, pricing.yaml).
state.db and cron/ belong to the Duckwork core home and are NOT relocated here.

The dashboard surfaces (dashboard/plugin_api.py, dashboard/serve.py) do NOT
import this module: the Duckwork web server loads plugin_api.py standalone (no
package context, repo root not on sys.path) and
tests/test_dashboard_plugin_isolation.py enforces that the two dashboard
surfaces share zero code. They replicate the precedence inline by design.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_telemetry_home() -> Path:
    """Resolve the telemetry directory (pure — does NOT create it)."""
    override = os.environ.get("DUCKWORK_TELEMETRY_HOME") or os.environ.get("DUCKWORK_HOME")
    root = Path(override) if override else Path.home() / ".duckwork"
    return root / "telemetry"


def get_db_path() -> Path:
    """Path to telemetry.db. Ensures the telemetry dir exists (the DB writes there)."""
    home = get_telemetry_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "telemetry.db"


def get_budget_path() -> Path:
    return get_telemetry_home() / "budget.yaml"


def get_pricing_path() -> Path:
    return get_telemetry_home() / "pricing.yaml"
