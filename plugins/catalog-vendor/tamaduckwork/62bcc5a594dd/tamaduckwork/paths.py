from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def repo_root(value: str | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def codex_home(value: str | None = None) -> Path:
    raw = value or os.environ.get("CODEX_HOME") or "~/.codex"
    return Path(raw).expanduser().resolve()


def duckwork_home(value: str | None = None) -> Path:
    """Resolve the Duckwork Agent home (``DUCKWORK_HOME`` or ``~/.duckwork``).

    Duckwork is profile-aware: a hosted profile sets ``DUCKWORK_HOME`` to
    ``~/.duckwork/profiles/<name>``, so the env var wins over the default exactly
    as Duckwork' own ``get_duckwork_home()`` does.
    """
    raw = value or os.environ.get("DUCKWORK_HOME") or "~/.duckwork"
    return Path(raw).expanduser().resolve()


def petdex_home(value: str | None = None) -> Path | None:
    """The Petdex *desktop* home to mirror the pet into, if one is configured.

    Returns ``None`` when nothing is configured. Deliberately does not guess
    ``~/.petdex``: mirroring is an explicit opt-in, so a plain run never writes
    outside the Duckwork home it was pointed at.
    """
    raw = value or os.environ.get("TAMADUCKWORK_PETDEX_HOME")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def default_state_path(home: Path) -> Path:
    return home / "tamaduckwork" / "state.json"


def default_catalog_dir(root: Path) -> Path:
    packaged_catalog = Path(__file__).resolve().parent / "catalog_assets"
    if (packaged_catalog / "manifest.json").exists():
        return packaged_catalog
    release_catalog = root / "assets" / "catalog"
    if (release_catalog / "manifest.json").exists():
        return release_catalog
    return packaged_catalog


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
