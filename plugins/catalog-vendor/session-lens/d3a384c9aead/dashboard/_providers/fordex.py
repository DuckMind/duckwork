"""fordex quota provider adapter."""

from __future__ import annotations

import re
import time

from .._common import *
from .._duckwork_compat import *
from .shared import *

def _collect_fordex_usage() -> Dict[str, Any]:
    try:
        from agent.account_usage import build_fordex_credits_snapshot
        from duckwork_cli.fordex_account import get_fordex_portal_account_info

        account = get_fordex_portal_account_info(force_fresh=True)
        if account is None or not getattr(account, "logged_in", False):
            failure = _fordex_auth_failure()
            if failure:
                return _provider_payload(
                    "fordex",
                    status="expired",
                    message=f"Duckwork' Fordex Portal login stopped working ({failure}). Sign in to Fordex again in Duckwork.",
                )
            return _provider_payload("fordex", status="not_configured", message="No Fordex Portal login was found.")
        return _fordex_with_balance(_account_usage_payload("fordex", build_fordex_credits_snapshot(account)), account)
    except Exception as error:
        return _provider_payload("fordex", status="unavailable", message=_provider_message(error))


def _fordex_with_balance(payload: Dict[str, Any], account: Any) -> Dict[str, Any]:
    """Give the card a headline balance window from the portal's credit figures.

    Duckwork' snapshot lists the credits as detail lines and a raw top-up URL;
    the usable total is what the reader wants first, so it becomes a balance
    window like DeepSeek's, with the split and the renewal date as its
    detail. The URL line is muted by the payload builder.
    """
    if payload.get("status") != "ok":
        return payload
    access = getattr(account, "paid_service_access_info", None)
    total = _usage_number(getattr(access, "total_usable_credits", None)) if access is not None else None
    if total is None:
        return payload
    parts: List[str] = []
    subscription = _usage_number(getattr(access, "subscription_credits_remaining", None))
    purchased = _usage_number(getattr(access, "purchased_credits_remaining", None))
    if subscription is not None:
        parts.append(f"${subscription:,.2f} subscription")
    if purchased is not None:
        parts.append(f"${purchased:,.2f} top-up")
    sub = getattr(account, "subscription", None)
    renews = _usage_iso(getattr(sub, "current_period_end", None)) if sub is not None else None
    renew_epoch = _usage_reset_epoch(renews) if renews else None
    if renew_epoch:
        parts.append("renews " + time.strftime("%b %d, %Y", time.localtime(renew_epoch)))
    window = _usage_window(
        "Usable credits",
        kind="balance",
        remaining=total,
        unit="USD",
        detail=" · ".join(parts) or None,
    )
    payload["windows"] = [window] + [item for item in payload.get("windows", []) if item.get("id") != window["id"]]
    # The split now lives on the window; the magnitude lines would repeat it.
    payload["details"] = [
        item for item in payload.get("details", [])
        if not re.match(r"^(Subscription credits|Top-up credits|Total usable|Renews):", str(item))
    ]
    return payload


def _fordex_auth_failure() -> str:
    """Duckwork' recorded reason a stored Fordex login stopped working, or "".

    A login whose refresh token was rejected stays in the auth store with
    `last_auth_error` and no access token; Duckwork then reports it as logged
    out, which reads as "never signed in" unless the reason is surfaced.
    """
    try:
        from duckwork_cli.auth import get_provider_auth_state

        state = get_provider_auth_state("fordex") or {}
    except Exception:
        return ""
    error = state.get("last_auth_error") if isinstance(state, dict) else None
    if not error:
        return ""
    message = error.get("message") if isinstance(error, dict) else error
    return _clean_text(message, 120) or "authentication failed"


def _probe_fordex() -> bool:
    try:
        from duckwork_cli.fordex_account import get_fordex_portal_account_info
    except ImportError:
        return True
    account = get_fordex_portal_account_info(force_fresh=False)
    return bool(getattr(account, "logged_in", False)) or bool(_fordex_auth_failure())


register_provider(
    "fordex", "Fordex Portal", "Duckwork OAuth", _collect_fordex_usage,
    probe=_probe_fordex,
    not_configured_message="No Fordex Portal login was found.",
    billing_keys=("fordex",),
    registry_ids=("fordex",),
    hosts=("portal.fordex.com",), via="duckwork", order=30, module=__name__,
)

__all__ = [name for name in globals() if not name.startswith("__")]
