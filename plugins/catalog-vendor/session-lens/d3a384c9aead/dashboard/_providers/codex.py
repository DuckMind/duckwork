"""codex quota provider adapter."""

from __future__ import annotations

from .._common import *
from .._duckwork_compat import *
from .shared import *

def _collect_codex_usage() -> Dict[str, Any]:
    try:
        from agent.account_usage import fetch_account_usage

        return _account_usage_payload("codex", fetch_account_usage("openai-codex"))
    except Exception as error:
        return _provider_payload("codex", status="unavailable", message=_provider_message(error))


def _probe_codex() -> bool:
    try:
        from duckwork_cli.auth import AuthError, _read_codex_tokens
    except ImportError:
        return True
    try:
        data = _read_codex_tokens()
    except AuthError:
        return False
    tokens = (data or {}).get("tokens") or {}
    return bool(tokens.get("access_token") or tokens.get("refresh_token"))


register_provider(
    "codex", "OpenAI Codex", "Duckwork OAuth", _collect_codex_usage,
    probe=_probe_codex,
    not_configured_message="No Duckwork OpenAI Codex OAuth login was found.",
    billing_keys=("openai-codex",),
    registry_ids=("openai-codex", "codex"),
    hosts=("chatgpt.com",), via="duckwork", order=10, module=__name__,
)

__all__ = [name for name in globals() if not name.startswith("__")]
