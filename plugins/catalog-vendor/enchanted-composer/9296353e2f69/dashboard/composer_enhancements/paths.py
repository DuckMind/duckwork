"""Profile and connection scoped filesystem boundaries with hashed safe components."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .contracts import OwnerBinding


def duckwork_home() -> Path:
    try:
        from duckwork_constants import get_duckwork_home
    except ModuleNotFoundError:  # Standalone package tests do not install Duckwork.
        configured=os.environ.get("DUCKWORK_HOME", "").strip()
        return Path(configured).expanduser() if configured else Path.home()/"DuckworkHome"
    return Path(get_duckwork_home())


def _component(value: str) -> str:
    # The name never enters a path; fixed lowercase digest prevents traversal/collisions.
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def owner_state_dir(owner: object) -> Path:
    binding=owner if isinstance(owner,OwnerBinding) else OwnerBinding.from_dict(owner)
    connection=_component(binding.connection_id)
    profile=_component(binding.profile)
    path=plugin_state_dir()/"owners"/connection/profile
    path.mkdir(parents=True,exist_ok=True)
    legacy=duckwork_home()/"composer-enhancements"/"owners"/connection/profile
    for name in ("settings.json","usage.json"):
        source,target=legacy/name,path/name
        if source.is_file() and not target.exists():
            shutil.copy2(source,target)
    return path


def profile_state_dir(profile: str) -> Path:
    # Retained only for read-only legacy callers; new state must use owner_state_dir.
    return owner_state_dir({"connectionId":"legacy","profile":profile,"runtimeSessionId":"legacy","storedSessionId":"legacy"})


def plugin_state_dir() -> Path:
    path=duckwork_home()/"plugin-data"/"enchanted-composer"
    path.mkdir(parents=True,exist_ok=True)
    return path
