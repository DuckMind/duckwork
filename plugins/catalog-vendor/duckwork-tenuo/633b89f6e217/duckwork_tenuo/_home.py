# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Where Duckwork lives, and how to read its config, from inside or outside Duckwork.

Inside a Duckwork process ``duckwork_constants`` and ``duckwork_cli`` are importable
and authoritative (profile overrides, managed scope, env expansion). From a
plain shell, for example ``duckwork-tenuo status`` in a different venv, the same
answers come from ``DUCKWORK_HOME`` (default ``~/.duckwork``) and a plain read of
``config.yaml``. Every path the plugin derives from the Duckwork home goes
through :func:`duckwork_home` so the two modes agree.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("duckwork_tenuo")


def duckwork_home() -> Path:
    """Duckwork home: ``duckwork_constants.get_duckwork_home()`` → ``$DUCKWORK_HOME`` → ``~/.duckwork``."""
    try:
        from duckwork_constants import get_duckwork_home
        return Path(get_duckwork_home())
    except Exception:
        pass
    env = os.environ.get("DUCKWORK_HOME")
    if env:
        return Path(env).expanduser()
    return Path("~/.duckwork").expanduser()


def config_path() -> Path:
    return duckwork_home() / "config.yaml"


def duckwork_cli_available() -> bool:
    try:
        import duckwork_cli.config  # noqa: F401
        return True
    except ImportError:
        return False


def load_duckwork_config() -> Dict[str, Any]:
    """Duckwork's merged config when ``duckwork_cli`` is importable, else a plain
    YAML read of ``$DUCKWORK_HOME/config.yaml``. ``{}`` when neither exists."""
    try:
        from duckwork_cli.config import load_config
    except ImportError:
        load_config = None
    if load_config is not None:
        try:
            data = load_config() or {}
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.debug("duckwork-tenuo: duckwork_cli.load_config failed (%s); reading config.yaml directly", exc)
    path = config_path()
    if not path.is_file():
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("duckwork-tenuo: could not read %s: %s", path, exc)
        return {}
