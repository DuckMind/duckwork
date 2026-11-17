"""Bind Duckwork configuration and credentials to this plugin's installed profile.

The dashboard can serve several profiles from one process. Plugin routes do not
receive the profile context that Duckwork' built-in routes establish, so every
provider/configuration read must enter that context explicitly. Never read a
provider secret from the process environment as a fallback.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path


def installed_profile_name() -> str | None:
    package_dir = Path(__file__).resolve().parents[2]
    plugins_dir = package_dir.parent
    profile_dir = plugins_dir.parent
    if plugins_dir.name == "plugins" and profile_dir.parent.name == "profiles":
        return profile_dir.name
    return None


@contextmanager
def duckwork_profile_scope(profile_name: str | None = None):
    profile = profile_name or installed_profile_name()
    if profile is None:
        # Source-tree tests use a scratch DUCKWORK_HOME and no multiplexed host.
        yield
        return
    from duckwork_cli.web_server_profiles import _config_profile_scope

    with _config_profile_scope(profile):
        yield
