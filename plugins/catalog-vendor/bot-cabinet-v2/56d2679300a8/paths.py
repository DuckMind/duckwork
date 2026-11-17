"""Where Cabinet keeps its own files, and where Duckwork keeps profiles.

Cabinet's data folder holds the cached catalog and the record of what Cabinet installed. It lives under
Duckwork's main home, not under a profile, so every profile sees the same record.

Tests point both folders at a temporary place with two environment variables, so a test can never
reach the user's real ~/.duckwork:

- ``CABINET_DATA_DIR``: Cabinet's own folder.
- ``DUCKWORK_HOME``: Duckwork's home (Duckwork itself reads this one).
"""

from __future__ import annotations

import os
from pathlib import Path

PLUGIN_ID = "bot-cabinet-v2"


def duckwork_home() -> Path:
    """Duckwork's main home: the folder that holds ``profiles/``."""
    try:
        from duckwork_constants import get_default_duckwork_root  # inside Duckwork
        return Path(get_default_duckwork_root())
    except Exception:
        return Path(os.environ.get("DUCKWORK_HOME") or (Path.home() / ".duckwork"))


def data_dir(create: bool = True) -> Path:
    override = os.environ.get("CABINET_DATA_DIR")
    path = Path(override) if override else duckwork_home() / "state" / PLUGIN_ID
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def display(path: Path | str) -> str:
    """A path as the page shows it: under your home folder it reads ~/..., so a screenshot never shows your user name.

    On Windows the home folder is matched without regard to case or slash direction (C:\\Users\\Ada and c:/users/ada
    are the same folder), and the part after ~ is shown with forward slashes, as on every other platform.
    """
    text = str(path)
    try:
        home = str(Path.home())
    except Exception:
        return text
    base = home.rstrip("/\\")
    if not base:
        return text
    folded, folded_base = os.path.normcase(text), os.path.normcase(base)
    if folded == folded_base:
        return "~"
    for sep in {"/", os.sep}:
        if folded.startswith(folded_base + os.path.normcase(sep)):
            return "~/" + text[len(base) + 1:].replace(os.sep, "/")
    return text
