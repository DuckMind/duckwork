"""Translate Octen's OpenAPI search/extract contract into Duckwork web results."""

from __future__ import annotations

from typing import Any

import httpx

from agent.web_search_provider import WebSearchProvider, get_provider_env

API_URL = "https://api.octen.ai"
MISSING_KEY = "Octen requires OCTEN_API_KEY. Run `duckwork tools` and configure Octen."


def _results(response: httpx.Response) -> list[dict]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid Octen response")
    if payload.get("code") not in (None, 0):
        raise ValueError("Octen API reported an error. Check your API key, balance, and quota.")
    data = payload.get("data")
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid Octen response")
    return rows


def _error(exc: Exception) -> str:
    # Do not echo response bodies or request headers: these may contain credentials.
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        hint = {
            401: "Check OCTEN_API_KEY.",
            403: "Check your account access and balance.",
            429: "Rate limit reached; try again later.",
        }.get(code, "Try again later or check the Octen service status.")
        return f"Octen returned HTTP {code}. {hint}"
    if isinstance(exc, httpx.TimeoutException):
        return "Octen request timed out. Try again later."
    if isinstance(exc, httpx.RequestError):
        return "Could not reach Octen. Check your network connection."
    return "Octen returned an invalid response or an API error. Check your API key, balance, and quota."


def _page_error(url: str, message: str) -> dict:
    return {"url": url, "title": "", "content": "", "raw_content": "", "error": message}


class OctenWebSearchProvider(WebSearchProvider):
    @property
    def name(self) -> str:
        return "octen"

    @property
    def display_name(self) -> str:
        return "Octen"

    def is_available(self) -> bool:
        return bool(get_provider_env("OCTEN_API_KEY"))

    def supports_extract(self) -> bool:
        return True

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "Octen",
            "badge": "API key",
            "tag": "Web search with query-focused highlights and page extraction.",
            "env_vars": [{
                "key": "OCTEN_API_KEY",
                "prompt": "Octen API key",
                "url": "https://octen.ai",
            }],
        }

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        api_key = get_provider_env("OCTEN_API_KEY")
        if not api_key:
            return {"success": False, "error": MISSING_KEY}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{API_URL}/search",
                    headers={"x-api-key": api_key},
                    json={
                        "query": query,
                        "count": max(1, min(int(limit), 100)),
                        "highlight": {"enable": True},
                        "full_content": {"enable": False},
                    },
                )
            results = []
            for position, row in enumerate(_results(response), 1):
                if not isinstance(row.get("url"), str) or not row["url"]:
                    raise ValueError("Invalid Octen search result URL")
                results.append({
                    "title": row.get("title") or "",
                    "url": row["url"],
                    "description": row.get("highlight") or "",
                    "position": position,
                })
            return {"success": True, "data": {"web": results}}
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return {"success": False, "error": _error(exc)}

    async def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        api_key = get_provider_env("OCTEN_API_KEY")
        if not api_key:
            return [_page_error(url, MISSING_KEY) for url in urls]
        output = []
        # Octen accepts at most 20 URLs per request. Keep batch failures local.
        async with httpx.AsyncClient(timeout=45) as client:
            for start in range(0, len(urls), 20):
                batch = urls[start:start + 20]
                try:
                    response = await client.post(
                        f"{API_URL}/extract",
                        headers={"x-api-key": api_key},
                        json={"urls": batch, "format": kwargs.get("format") or "markdown"},
                    )
                    rows = _results(response)
                except (httpx.HTTPError, ValueError) as exc:
                    output.extend(_page_error(url, _error(exc)) for url in batch)
                    continue
                for index, url in enumerate(batch):
                    row = rows[index] if index < len(rows) else {}
                    if row.get("url") != url or row.get("status") != "success":
                        output.append(_page_error(url, "Octen could not extract this URL."))
                        continue
                    content = row.get("full_content")
                    if not isinstance(content, str):
                        output.append(_page_error(url, "Octen returned no page content."))
                        continue
                    title = row.get("title") or ""
                    output.append({
                        "url": url, "title": title, "content": content, "raw_content": content,
                        "metadata": {"sourceURL": url, "title": title},
                    })
        return output
