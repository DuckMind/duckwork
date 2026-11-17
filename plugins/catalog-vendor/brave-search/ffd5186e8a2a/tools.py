"""Brave Search tool handlers for Duckwork."""

from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any

import requests


BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_TIMEOUT = 20
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def check_brave_api_key() -> bool:
    return bool(os.getenv("BRAVE_API_KEY"))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unescape(str(value))
    text = TAG_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for item in (payload.get("web") or {}).get("results") or []:
        profile = item.get("profile") or {}
        meta_url = item.get("meta_url") or {}
        results.append(
            {
                "title": _clean_text(item.get("title")),
                "url": item.get("url", ""),
                "description": _clean_text(item.get("description")),
                "age": item.get("age"),
                "language": item.get("language"),
                "source": profile.get("long_name") or profile.get("name"),
                "display_url": meta_url.get("display_url") or item.get("url", ""),
            }
        )
    return results


def brave_web_search(args: dict[str, Any], **kwargs) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "Missing required parameter: query"})

    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return json.dumps({"error": "BRAVE_API_KEY is not set"})

    count = args.get("count", 10)
    try:
        count = max(1, min(20, int(count)))
    except Exception:
        return json.dumps({"error": "count must be an integer between 1 and 20"})

    params = {
        "q": query,
        "count": count,
        "safesearch": args.get("safesearch") or "moderate",
    }
    for src_key, brave_key in (("country", "country"), ("search_lang", "search_lang"), ("freshness", "freshness")):
        value = args.get(src_key)
        if value:
            params[brave_key] = str(value).strip()

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    try:
        response = requests.get(
            BRAVE_WEB_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        return json.dumps({"error": f"Brave request failed: {exc}"})

    if response.status_code >= 400:
        body = _clean_text(response.text)
        return json.dumps(
            {
                "error": "Brave Search API returned an error",
                "status_code": response.status_code,
                "details": body[:1000],
            }
        )

    try:
        payload = response.json()
    except ValueError:
        return json.dumps(
            {
                "error": "Brave Search API returned non-JSON response",
                "status_code": response.status_code,
                "details": response.text[:1000],
            }
        )

    results = _extract_results(payload)
    return json.dumps(
        {
            "query": query,
            "count": len(results),
            "results": results,
        },
        ensure_ascii=False,
    )
