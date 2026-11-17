"""Spectator authentication package."""

from spectator.auth.auth import (
    AuthError,
    HostSecretManager,
    SessionGenManager,
    compute_session_gen,
    derive_guest_token,
)
from spectator.auth.invite import InviteError, InviteManager

__all__ = [
    "AuthError",
    "HostSecretManager",
    "InviteError",
    "InviteManager",
    "SessionGenManager",
    "compute_session_gen",
    "derive_guest_token",
]