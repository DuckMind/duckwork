#!/usr/bin/env python3
"""Google API helpers for Duckwork SEO's injected runtime credentials.

Only static Google API-key services run directly. Authenticated Google
services require a Duckwork-managed route and intentionally fail closed here.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

SERVICE_AUTH = {
    "psi": "api_key",
    "crux": "api_key",
    "crux_history": "api_key",
    "gsc": "duckwork_route",
    "indexing": "duckwork_route",
    "ga4": "duckwork_route",
}
SERVICE_NAMES = {
    "psi": "PageSpeed Insights v5",
    "crux": "Chrome UX Report (CrUX) API",
    "crux_history": "CrUX History API",
    "gsc": "Google Search Console API",
    "indexing": "Google Indexing API v3",
    "ga4": "GA4 Data API v1beta",
}
_GOOGLE_API_KEY_PREFIX = "AI" + "za"
_GOOGLE_API_KEY_RE = re.compile(_GOOGLE_API_KEY_PREFIX + r"[0-9A-Za-z_-]+")
_GOOGLE_KEY_QUERY_RE = re.compile(r"([?&])key=[^&\s'\"<>)]*(&?)")
_GOOGLE_KEY_BARE_RE = re.compile(r"\bkey=[^&\s'\"<>)]*")
_ROUTE_UNAVAILABLE = "This authenticated Google service requires a Duckwork route and is unavailable in the bundled runtime."


def google_api_key_headers(api_key: str) -> dict[str, str]:
    return {"X-Goog-Api-Key": api_key}


def redact_google_api_key(value: object) -> str:
    text = str(value)

    def drop_query_key(match: re.Match[str]) -> str:
        separator, trailing_amp = match.groups()
        if separator == "?" and trailing_amp:
            return "?"
        if separator == "&" and trailing_amp:
            return "&"
        return ""

    text = _GOOGLE_KEY_QUERY_RE.sub(drop_query_key, text).replace("?&", "?")
    return _GOOGLE_API_KEY_RE.sub("GOOGLE_API_KEY_REDACTED", _GOOGLE_KEY_BARE_RE.sub("google_api_key_redacted", text))


def load_config() -> dict[str, Optional[str]]:
    """Return only values injected into this child process.

    Property identifiers are nonsecret runtime configuration. The API key must
    be supplied by the Duckwork child-environment bridge.
    """
    return {
        "api_key": os.environ.get("GOOGLE_API_KEY"),
        "default_property": os.environ.get("GSC_PROPERTY"),
        "ga4_property_id": os.environ.get("GA4_PROPERTY_ID"),
    }


def get_api_key() -> Optional[str]:
    return load_config()["api_key"]


def get_oauth_credentials(_scopes: list[str]):
    """Compatibility seam for callers of authenticated Google APIs.

    Local authenticated credential mechanisms are unavailable until Duckwork
    exposes a managed route.
    """
    print(_ROUTE_UNAVAILABLE, file=sys.stderr)
    return None


def build_service(_api_name: str, _version: str, scopes: list[str]):
    return get_oauth_credentials(scopes)


def validate_url(url: str) -> bool:
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from url_safety import validate_url as validate

    return validate(url)


def check_credentials(service: str) -> dict:
    method = SERVICE_AUTH.get(service, "unknown")
    result = {
        "available": False,
        "method": method,
        "service": SERVICE_NAMES.get(service, service),
        "error": None,
    }
    if method == "api_key":
        result["available"] = bool(get_api_key())
        if not result["available"]:
            result["error"] = "No API key was injected. Configure GOOGLE_API_KEY through Duckwork."
    elif method == "duckwork_route":
        result["error"] = _ROUTE_UNAVAILABLE
    else:
        result["error"] = f"Unknown service: {service}"
    return result


def detect_tier() -> dict:
    if get_api_key():
        return {
            "tier": 1,
            "description": "Static Google API-key services",
            "capabilities": ["PageSpeed Insights", "CrUX", "CrUX History"],
            "missing": _ROUTE_UNAVAILABLE,
        }
    return {
        "tier": 0,
        "description": "No injected Google API key",
        "capabilities": [],
        "missing": "Configure GOOGLE_API_KEY through Duckwork for static Google API-key services.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Duckwork SEO Google API-key readiness")
    parser.add_argument("--check", nargs="?", const="all", metavar="SERVICE")
    parser.add_argument("--tier", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    services = list(SERVICE_AUTH) if args.check in (None, "all") else [args.check]
    payload = {service: check_credentials(service) for service in services}
    if args.json:
        import json
        print(json.dumps({"tier": detect_tier(), "services": payload}, indent=2))
    else:
        for service, status in payload.items():
            print(f"{service}: {'ready' if status['available'] else status['error']}")
    return 0 if all(status["available"] for status in payload.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
