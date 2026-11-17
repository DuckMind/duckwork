"""Configuration schema for duckwork-spectator.

Precedence: defaults < config.yaml < SPECTATOR_* environment variables.
Out-of-range values fail closed to the default; invalid types are refused at
plugin load time.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class SpectatorConfig(BaseModel):
    """Canonical configuration for the spectator plugin."""

    pending_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    invite_ttl_seconds: int = Field(default=86400, ge=60, le=604800)
    allow_remote: bool = Field(default=False)
    require_tls: bool = Field(default=True)
    feed_source: str = Field(default="auto")  # auto | onEvent | transcript
    poll_interval_seconds: int = Field(default=2, ge=1)
    max_pending_suggestions: int = Field(default=100, ge=1)
    event_retention_days: int = Field(default=7, ge=1)
    mask_overrides: dict[str, Any] = Field(default_factory=dict)
    allow_gateway_injection: bool = Field(default=False)
    inject_timeout_seconds: float = Field(default=2.0, ge=1.0, le=10.0)

    @field_validator("feed_source")
    @classmethod
    def _validate_feed_source(cls, v: str) -> str:
        allowed = {"auto", "onEvent", "transcript"}
        if v not in allowed:
            raise ValueError(f"feed_source must be one of {allowed}, got {v!r}")
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Default profile-local paths
# ---------------------------------------------------------------------------

DEFAULT_DUCKWORK_HOME = Path(
    os.environ.get("DUCKWORK_HOME", str(Path.home() / ".duckwork"))
).expanduser()

DEFAULT_DATA_DIR = Path(
    os.environ.get(
        "SPECTATOR_DATA_DIR",
        str(DEFAULT_DUCKWORK_HOME / "data" / "spectator"),
    )
).expanduser()

# Host transcript source (P7: read-only, stdlib sqlite3 only). Configurable so
# tests can point at a seeded fixture; defaults to this Duckwork profile's state DB.
DEFAULT_STATE_DB_PATH = Path(
    os.environ.get(
        "SPECTATOR_STATE_DB",
        str(DEFAULT_DUCKWORK_HOME / "state.db"),
    )
).expanduser()

DEFAULT_CONFIG_PATH = DEFAULT_DATA_DIR / "config.yaml"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "spectator.db"
DEFAULT_SECRET_PATH = DEFAULT_DATA_DIR / "host_secret"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_ENV_MAP = {
    "SPECTATOR_PENDING_TTL_SECONDS": ("pending_ttl_seconds", int),
    "SPECTATOR_INVITE_TTL_SECONDS": ("invite_ttl_seconds", int),
    "SPECTATOR_ALLOW_REMOTE": ("allow_remote", lambda v: v.lower() in ("1", "true", "yes", "on")),
    "SPECTATOR_REQUIRE_TLS": ("require_tls", lambda v: v.lower() in ("1", "true", "yes", "on")),
    "SPECTATOR_FEED_SOURCE": ("feed_source", str),
    "SPECTATOR_POLL_INTERVAL_SECONDS": ("poll_interval_seconds", int),
    "SPECTATOR_MAX_PENDING_SUGGESTIONS": ("max_pending_suggestions", int),
    "SPECTATOR_EVENT_RETENTION_DAYS": ("event_retention_days", int),
    "SPECTATOR_ALLOW_GATEWAY_INJECTION": ("allow_gateway_injection", lambda v: v.lower() in ("1", "true", "yes", "on")),
    "SPECTATOR_INJECT_TIMEOUT_SECONDS": ("inject_timeout_seconds", float),
}


def load_config(config_path: Path | None = None) -> SpectatorConfig:
    """Load configuration with precedence: defaults < YAML file < env vars.

    Out-of-range values fail closed: env overrides that are invalid revert to
    the default with a warning logged. Invalid types raise at plugin init.
    """
    import logging
    log = logging.getLogger("spectator.config")

    # 1. Start with defaults
    overrides: dict[str, Any] = {}

    # 2. Load YAML (lower precedence than env)
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}
            spectator_section = yaml_data.get("spectator", yaml_data)
            if isinstance(spectator_section, dict):
                overrides.update(spectator_section)
        except Exception as exc:
            log.warning("Failed to load config from %s: %s", path, exc)

    # 3. Env overrides (highest precedence)
    for env_key, (field_name, coerce) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            try:
                overrides[field_name] = coerce(val)  # type: ignore[operator]
            except (ValueError, TypeError) as exc:
                log.warning(
                    "Invalid env %s=%r, ignoring: %s", env_key, val, exc
                )

    # 4. Build and validate — fail-closed on invalid types
    try:
        cfg = SpectatorConfig(**overrides)
    except Exception as exc:
        log.error("Invalid spectator config, using defaults: %s", exc)
        cfg = SpectatorConfig()

    return cfg