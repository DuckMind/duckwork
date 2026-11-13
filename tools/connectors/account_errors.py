"""Safe preparation failures shared by account-operation consumers.

Messages, URLs, request IDs and arbitrary backend codes are deliberately not copied:
HTTP error envelopes and transport exceptions can contain credentials.
"""
from __future__ import annotations

from dataclasses import dataclass

from tools.connectors.gateway.errors import GatewayAuthError, GatewayUnavailable, ToolGatewayError


@dataclass(frozen=True)
class AccountOperationFailure:
    reason: str
    message: str
    retryable: bool = False
    status: int | None = None


_UNAVAILABLE = (
    "Hosted connector service is unavailable. Try again later, or use a directly configured MCP server."
)


def account_operation_failure(exc: Exception) -> AccountOperationFailure:
    """Classify typed fields only, in the worker's owning profile context; never stringify *exc*."""
    status = exc.status if isinstance(exc, ToolGatewayError) else None
    if isinstance(exc, ToolGatewayError) and exc.code == "GUEST_SETUP_FAILED":
        # Guest setup currently returns copy rather than an exception. Its typed failure memo is
        # profile-scoped and recorded before that return; do not parse the copy to recover meaning.
        from duckwork_cli.anon_auth import last_mint_failure

        failure = last_mint_failure() or {}
        code = failure.get("error_code")
        if code == "anon_account_locked":
            return AccountOperationFailure("PERMISSION_DENIED", "This account is not permitted to use hosted connectors.")
        if code in {"anon_signin_required", "anon_gate_closed", "anon_pow_required", "anon_credential_dead"}:
            return AccountOperationFailure("AUTH_REQUIRED", "Hosted connectors require an account. Sign in to continue.")
        if code == "anon_challenge_required":
            return AccountOperationFailure("AUTH_REQUIRED", "Finish the account check in your browser, then try again.")
        if code == "anon_rate_limited":
            return AccountOperationFailure("RATE_LIMITED", "Hosted connector requests are rate limited. Try again later.", True)
        return AccountOperationFailure("SERVICE_UNAVAILABLE", _UNAVAILABLE, True)
    if status == 403:
        return AccountOperationFailure("PERMISSION_DENIED", "Your account does not have permission to use this connector.", status=status)
    if status == 401 or isinstance(exc, GatewayAuthError):
        return AccountOperationFailure("AUTH_REQUIRED", "Hosted connector authentication is required. Sign in to continue.", status=status)
    if status == 429:
        return AccountOperationFailure("RATE_LIMITED", "Hosted connector requests are rate limited. Try again later.", True, status)
    if (isinstance(exc, GatewayUnavailable) or (status is not None and status >= 500)
            or (isinstance(exc, ToolGatewayError) and exc.code == "TRANSPORT_ERROR")
            or isinstance(exc, (ConnectionError, TimeoutError, OSError))):
        return AccountOperationFailure("SERVICE_UNAVAILABLE", _UNAVAILABLE, True, status)
    if isinstance(exc, ValueError):
        return AccountOperationFailure("INVALID_CONFIGURATION", "Check this connector's local configuration before retrying.")
    return AccountOperationFailure("REQUEST_FAILED", "Could not prepare the hosted connector. Try again later.", status=status)
