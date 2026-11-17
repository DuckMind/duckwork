"""HTTP client for the Financial Datasets API (https://api.financialdatasets.ai).

Standard library only, so the plugin installs with no dependencies. The API
key is read from the environment on every request and is sent to the
Financial Datasets API host only.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.financialdatasets.ai/"
API_KEY_ENV = "FINANCIAL_DATASETS_API_KEY"
API_KEY_URL = "https://financialdatasets.ai"
USER_AGENT = "duckwork-plugin-financial-datasets/1.0.0"
TIMEOUT_SECONDS = 30

# The API caps every list response at a fixed page size and links the rest via
# `next_page_url`. LLMs cannot be trusted to loop over cursors, so `get`
# follows the links itself. MAX_PAGES bounds a pathological request (months of
# minute bars); hitting it returns the rows accumulated so far.
MAX_PAGES = 100


class ApiError(Exception):
    """A request the API rejected, or that never reached it."""


def get(path: str, params: dict | None = None, paginated: bool = False) -> dict:
    """GET one API route. With `paginated`, follow `next_page_url` and merge the pages."""
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)

    merged = _request(url)
    if not paginated:
        return merged

    next_page_url = merged.get("next_page_url")
    pages = 1
    while _is_api_url(next_page_url) and pages < MAX_PAGES:
        page = _request(next_page_url)
        _merge_page(merged, page)
        next_page_url = page.get("next_page_url")
        pages += 1

    merged.pop("next_page_url", None)
    return merged


def post(path: str, body: dict) -> dict:
    return _request(API_BASE + path, body=body)


def _is_api_url(url) -> bool:
    """True for a follow-up page on the API host. The key never goes anywhere else."""
    return isinstance(url, str) and url.startswith(API_BASE)


def _request(url: str, body: dict | None = None) -> dict:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise ApiError(f"{API_KEY_ENV} is not set. Get an API key at {API_KEY_URL} and add it to ~/.duckwork/.env.")

    headers = {"X-API-KEY": api_key, "User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()

    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise ApiError(_error_message(error)) from error
    except urllib.error.URLError as error:
        raise ApiError(f"Could not reach the Financial Datasets API: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise ApiError("The Financial Datasets API returned a response that is not JSON.") from error


def _error_message(error: urllib.error.HTTPError) -> str:
    """The API's own `message` (or `error`) when the body has one, else the HTTP status."""
    try:
        payload = json.loads(error.read())
    except (ValueError, OSError):
        payload = {}
    detail = payload.get("message") or payload.get("error") if isinstance(payload, dict) else None
    return f"HTTP {error.code}: {detail or error.reason}"


def _merge_page(accumulated: dict, page: dict) -> None:
    """Merge a follow-up page: record lists are concatenated (recursively, in case an
    envelope nests them one level down) and scalars keep the first page's value."""
    for key, value in page.items():
        if key == "next_page_url":
            continue
        existing = accumulated.get(key)
        if isinstance(existing, list) and isinstance(value, list):
            existing.extend(value)
        elif isinstance(existing, dict) and isinstance(value, dict):
            _merge_page(existing, value)
