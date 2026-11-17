"""Venice AI — privacy-first web search + extract provider.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`.
Backs the standard ``web_search`` and ``web_extract`` tools via Venice's
``/augment/search`` and ``/augment/scrape`` endpoints.

Config keys this provider responds to::

    web:
      backend: "venice"            # shared
      search_backend: "venice"     # per-capability
      extract_backend: "venice"    # per-capability

Auth env var::

    VENICE_API_KEY=vk-...   # https://venice.ai
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.venice.ai/api/v1/augment"


class VeniceWebSearchProvider(WebSearchProvider):
    """Privacy-focused search + extract via Venice AI /augment endpoints.

    Venice routes search through Brave (zero data retention) or Google
    (anonymized). Extract uses headless scraping with Cloudflare Markdown
    for Agents fallback.

    $0.01 per search request, $0.01 per scrape URL.
    """

    @property
    def name(self) -> str:
        return "venice"

    @property
    def display_name(self) -> str:
        return "Venice AI"

    def is_available(self) -> bool:
        return bool(os.getenv("VENICE_API_KEY", "").strip())

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        import httpx

        api_key = os.environ.get("VENICE_API_KEY", "")
        if not api_key:
            return {"success": False, "error": "VENICE_API_KEY is not set"}

        count = max(1, min(int(limit), 20))
        search_provider = os.getenv("VENICE_SEARCH_PROVIDER", "brave").lower()
        if search_provider not in ("brave", "google"):
            search_provider = "brave"

        try:
            resp = httpx.post(
                f"{_BASE_URL}/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "limit": count,
                    "search_provider": search_provider,
                },
                timeout=20,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Venice Search HTTP error: %s", exc)
            return {
                "success": False,
                "error": f"Venice Search returned HTTP {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("Venice Search request error: %s", exc)
            return {"success": False, "error": f"Could not reach Venice Search: {exc}"}

        try:
            data = resp.json()
        except Exception as exc:
            logger.warning("Venice Search response parse error: %s", exc)
            return {"success": False, "error": "Could not parse Venice Search response as JSON"}

        raw_results = data.get("results") or []
        web_results = [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "description": str(r.get("content", r.get("snippet", ""))),
                "position": idx + 1,
            }
            for idx, r in enumerate(raw_results[:count])
        ]

        logger.info(
            "Venice Search '%s': %d results (limit %d, provider %s)",
            query,
            len(web_results),
            count,
            search_provider,
        )

        return {"success": True, "data": {"web": web_results}}

    def extract(self, urls: List[str], **kwargs: Any) -> Dict[str, Any]:
        import httpx

        api_key = os.environ.get("VENICE_API_KEY", "")
        if not api_key:
            return {"success": False, "error": "VENICE_API_KEY is not set"}

        results = []
        for url in urls:
            result = self._scrape_single(httpx, api_key, url)
            results.append(result)

        return {"success": True, "data": results}

    def _scrape_single(self, httpx: Any, api_key: str, url: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(
                f"{_BASE_URL}/scrape",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url},
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Venice Scrape HTTP error for %s: %s", url, exc)
            return {
                "url": url,
                "title": "",
                "content": "",
                "raw_content": "",
                "error": f"HTTP {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("Venice Scrape request error for %s: %s", url, exc)
            return {
                "url": url,
                "title": "",
                "content": "",
                "raw_content": "",
                "error": str(exc),
            }

        try:
            data = resp.json()
        except Exception:
            return {
                "url": url,
                "title": "",
                "content": "",
                "raw_content": "",
                "error": "Could not parse Venice scrape response",
            }

        # Venice wraps under "data" key in some responses
        payload = data.get("data", data)
        content = payload.get("content", "")

        return {
            "url": payload.get("url", url),
            "title": "",
            "content": content,
            "raw_content": content,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Venice AI",
            "badge": "paid",
            "tag": "Privacy-first search + extract — $0.01/request, zero data retention.",
            "env_vars": [
                {
                    "key": "VENICE_API_KEY",
                    "prompt": "Venice API key",
                    "url": "https://venice.ai",
                },
            ],
        }
