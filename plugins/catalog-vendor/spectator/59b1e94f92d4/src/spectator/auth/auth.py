"""Authentication module — host and guest identity for spectator plugin.

Auth model v3 (canonical):
- Host: gateway session credentials (ctx.rest) or CLI bearer host_secret
- Guest: self-identifying HMAC token = guest_id + ":" + HMAC-SHA256(host_secret, guest_id || ":" || token_hash)
- Invite tokens: 256-bit random, single-use, appear only in URL fragment
- Session generation identity: prevents stale invite rebinding on restart
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from pathlib import Path

log = logging.getLogger("spectator.auth")

# Host secret is 256 bits (32 bytes), stored 0600 in the plugin data dir.
_HOST_SECRET_SIZE = 32


class AuthError(Exception):
    """Raised on authentication failures."""
    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class HostSecretManager:
    """Manages the host_secret — created once, stored 0600, never returned by any endpoint.

    Fail-closed: if the secret cannot be created (unwritable dir) or read
    (corrupt data), the plugin enters DEGRADED state (all endpoints 503).
    """

    def __init__(self, secret_path: Path) -> None:
        self.secret_path = secret_path
        self._secret: bytes | None = None
        self.degraded = False
        self.degraded_reason = ""

    def load_or_create(self) -> bool:
        """Load or create the host secret. Returns True on success.

        On failure, sets self.degraded=True and self.degraded_reason.
        """
        self.secret_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            exists = self.secret_path.exists()
        except PermissionError:
            self.degraded = True
            self.degraded_reason = (
                f"Cannot access host_secret path {self.secret_path}: permission denied. "
                f"Recovery: fix directory permissions or remove the file."
            )
            log.critical(self.degraded_reason)
            return False

        if exists:
            try:
                data = self.secret_path.read_bytes()
                if len(data) != _HOST_SECRET_SIZE:
                    self.degraded = True
                    self.degraded_reason = (
                        f"Corrupt host_secret: expected {_HOST_SECRET_SIZE} bytes, "
                        f"got {len(data)} — remove {self.secret_path} to regenerate"
                    )
                    log.critical(self.degraded_reason)
                    return False
                self._secret = data
                return True
            except OSError as exc:
                self.degraded = True
                self.degraded_reason = f"Cannot read host_secret: {exc}"
                log.critical(self.degraded_reason)
                return False
        else:
            # Create new
            try:
                secret = secrets.token_bytes(_HOST_SECRET_SIZE)
                self.secret_path.write_bytes(secret)
                self.secret_path.chmod(0o600)
                self._secret = secret
                log.info("Created new host_secret at %s", self.secret_path)
                return True
            except OSError as exc:
                self.degraded = True
                self.degraded_reason = (
                    f"Cannot create host_secret at {self.secret_path}: {exc}. "
                    f"Recovery: ensure the directory is writable."
                )
                log.critical(self.degraded_reason)
                return False

    @property
    def secret(self) -> bytes | None:
        """The raw host secret. None if degraded."""
        return self._secret

    def verify_host_bearer(self, token: str) -> bool:
        """Verify a CLI host_secret bearer token (hex-encoded)."""
        if self._secret is None:
            return False
        try:
            provided = bytes.fromhex(token)
            return hmac.compare_digest(provided, self._secret)
        except (ValueError, TypeError):
            return False


def derive_guest_token(host_secret: bytes, guest_id: str, token_hash: str) -> str:
    """Derive the canonical self-identifying guest token.

    guest_token = guest_id + ":" + HMAC-SHA256(host_secret, guest_id || ":" || token_hash)
    """
    msg = f"{guest_id}:{token_hash}".encode()
    mac = hmac.new(host_secret, msg, hashlib.sha256).hexdigest()
    return f"{guest_id}:{mac}"


# ---------------------------------------------------------------------------
# Session-generation identity
# ---------------------------------------------------------------------------

def compute_session_gen(session_id: str, process_start_epoch: float, nonce: bytes | None = None) -> str:
    """Compute the session-generation token.

    session_gen = SHA-256(session_id + ":" + process_start_epoch + ":" + 128-bit random nonce)
    """
    if nonce is None:
        nonce = secrets.token_bytes(16)
    raw = f"{session_id}:{process_start_epoch}".encode() + b":" + nonce
    return hashlib.sha256(raw).hexdigest()


class SessionGenManager:
    """Manages the session-generation token persisted in the plugin data dir.

    On init, if the persisted session_gen differs from the current one,
    ALL invites with the old session_gen are invalidated (host_gone semantics).
    """

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "session_gen"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._current: str | None = None
        self._previous: str | None = None

    def initialise(self, session_id: str, process_start_epoch: float) -> str:
        """Load or create session_gen. Returns the current session_gen.

        If the persisted gen differs from the newly computed one, stores the
        new gen and records the previous one (for invite invalidation).

        Fail-closed: if the persisted session_gen file is missing, corrupt,
        or unreadable, we treat the generation as CHANGED by setting
        _previous to an empty-string sentinel.  This ensures
        _invalidate_stale_invites() runs against ALL rows, preventing stale
        invites from a previous session from surviving a restart where the
        gen file was lost.  (AC#3: session-gen invalidation must work even
        when the gen file is absent.)
        """
        new_gen = compute_session_gen(session_id, process_start_epoch)

        if self.path.exists():
            try:
                content = self.path.read_text(encoding="utf-8").strip()
                if content:
                    self._previous = content
                else:
                    # Corrupt: empty file treated as generation change
                    self._previous = ""
            except Exception:
                # Unreadable: treat as generation change (fail-closed)
                self._previous = ""
        else:
            # Missing file: cannot know previous gen → invalidate all stale
            # invites.  This is the fail-closed path for AC#3.
            self._previous = ""

        self._current = new_gen
        try:
            self.path.write_text(new_gen, encoding="utf-8")
            self.path.chmod(0o600)
        except OSError as exc:
            log.warning("Failed to persist session_gen: %s", exc)

        return new_gen

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def previous(self) -> str | None:
        return self._previous