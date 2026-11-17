#!/usr/bin/env python3
"""Backlink provider helpers using Duckwork-injected static API keys only."""

from __future__ import annotations

import argparse
import json
import os
from typing import Optional

CACHE_DIR = os.path.join(
    os.environ.get("DUCKWORK_SEO_CACHE_DIR", os.path.expanduser("~/.cache/duckwork-seo")),
    "commoncrawl",
)
SERVICE_AUTH = {
    "moz": "api_key",
    "bing": "api_key",
    "keywordseverywhere": "api_key",
    "commoncrawl": "none",
    "verify": "none",
}
SERVICE_NAMES = {
    "moz": "Moz Link Explorer API",
    "bing": "Bing Webmaster Tools API",
    "keywordseverywhere": "Keywords Everywhere",
    "commoncrawl": "Common Crawl Web Graph",
    "verify": "Backlink Verification Crawler",
}


def load_config() -> dict:
    """Return static keys injected into this process, never a credential file."""
    return {
        "moz_api_key": os.environ.get("MOZ_API_KEY"),
        "bing_api_key": os.environ.get("BING_WEBMASTER_API_KEY"),
        "keywordseverywhere_api_key": os.environ.get("KEYWORDSEVERYWHERE_API_KEY"),
        "bing_verified_sites": [],
        "commoncrawl_cache_dir": CACHE_DIR,
    }


def get_moz_api_key() -> Optional[str]:
    return load_config()["moz_api_key"]


def get_bing_api_key() -> Optional[str]:
    return load_config().get("bing_api_key")


def get_keywordseverywhere_api_key() -> Optional[str]:
    return load_config().get("keywordseverywhere_api_key")


def get_bing_verified_sites() -> list:
    return []


def get_cache_dir() -> str:
    cache_dir = load_config()["commoncrawl_cache_dir"]
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def check_credentials(service: str) -> dict:
    result = {
        "available": False,
        "method": SERVICE_AUTH.get(service, "unknown"),
        "service": SERVICE_NAMES.get(service, service),
        "error": None,
    }
    keys = {
        "moz": get_moz_api_key(),
        "bing": get_bing_api_key(),
        "keywordseverywhere": get_keywordseverywhere_api_key(),
    }
    if service in keys:
        result["available"] = bool(keys[service])
        if not result["available"]:
            result["error"] = f"No {result['service']} key was injected through Duckwork."
    elif service == "commoncrawl":
        result.update(available=True, method="none (public data)", cache_dir=get_cache_dir())
    elif service == "verify":
        result.update(available=True, method="none (local crawler)")
    else:
        result["error"] = f"Unknown service: {service}"
    return result


def detect_tier() -> dict:
    config = load_config()
    keys = [config["moz_api_key"], config["bing_api_key"], config["keywordseverywhere_api_key"]]
    return {
        "tier": sum(bool(key) for key in keys),
        "description": "Duckwork-injected static provider keys",
        "capabilities": [name for name, key in zip(("Moz", "Bing", "Keywords Everywhere"), keys) if key],
        "missing": None if all(keys) else "Inject the required provider key through Duckwork.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Duckwork SEO backlink provider readiness")
    parser.add_argument("--check", nargs="?", const="all", metavar="SERVICE")
    parser.add_argument("--tier", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    services = list(SERVICE_AUTH) if args.check in (None, "all") else [args.check]
    results = {service: check_credentials(service) for service in services}
    if args.json:
        print(json.dumps({"tier": detect_tier(), "services": results}, indent=2))
    else:
        for service, status in results.items():
            print(f"{service}: {'ready' if status['available'] else status['error']}")
    return 0 if all(status["available"] for status in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
