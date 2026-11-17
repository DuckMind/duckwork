"""HTTP, catalog, job and config helpers shared by the EmpirioLabs AI media backends.

Every request goes to the EmpirioLabs AI API (``https://api.empiriolabs.ai/v1``, or
``EMPIRIOLABS_BASE_URL``). Generated files are downloaded from the URLs the API returns.
The API key is read through Duckwork' profile-scoped secret lookup on each call and is
sent only to the API, never to a download URL.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Any, Callable, Optional

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

PROVIDER_NAME = "empiriolabs"
DISPLAY_NAME = "EmpirioLabs AI"
DEFAULT_BASE_URL = "https://api.empiriolabs.ai/v1"
API_KEYS_URL = "https://platform.empiriolabs.ai/dashboard/api-keys"
KEY_ENV = "EMPIRIOLABS_API_KEY"
BASE_URL_ENV = "EMPIRIOLABS_BASE_URL"
USER_AGENT = f"duckwork-empiriolabs-media/{__version__}"

CATALOG_TTL_SECONDS = 3600.0
FAILURE_BACKOFF_SECONDS = 60.0
CATALOG_TIMEOUT_SECONDS = 8.0
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024

JOB_IN_PROGRESS = frozenset({"processing", "queued", "pending", "running", "in_progress", "submitted", "starting"})
JOB_SUCCEEDED = frozenset({"completed", "succeeded"})
JOB_FAILED = frozenset({"failed", "error", "cancelled", "canceled", "expired"})
RETRYABLE_POLL_STATUSES = frozenset({0, 408, 425, 429, 500, 502, 503, 504})
MAX_POLL_RETRIES = 5

# Indirection points so tests can replace the network, the clock and the URL check.
_sleep = time.sleep
_now = time.monotonic


class ApiError(Exception):
    """A failed request. ``status`` is the HTTP status (0 when no response arrived)."""

    def __init__(self, message: str, *, status: int = 0, code: str = "", job_id: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.job_id = job_id


class JobFailed(ApiError):
    """The job reached a failed or cancelled state."""


class JobTimeout(ApiError):
    """The job was still running when the wait deadline passed (it keeps running)."""


# ---------------------------------------------------------------------------
# Credentials and settings
# ---------------------------------------------------------------------------


def _secret(name: str) -> str:
    try:
        from agent.secret_scope import get_secret

        return str(get_secret(name) or "").strip()
    except Exception:  # an unscoped read under multiplexing counts as "not configured"
        return ""


def api_key() -> str:
    return _secret(KEY_ENV)


def base_url() -> str:
    return (_secret(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def provider_config(section: str) -> dict[str, Any]:
    """``<section>.empiriolabs`` from Duckwork' config.yaml, or {}."""
    try:
        from duckwork_cli.config import load_config

        config = load_config()
    except Exception:
        return {}
    block = config.get(section) if isinstance(config, dict) else None
    scoped = block.get(PROVIDER_NAME) if isinstance(block, dict) else None
    return scoped if isinstance(scoped, dict) else {}


def setup_schema(tag: str) -> dict[str, Any]:
    return {
        "name": DISPLAY_NAME,
        "badge": "paid",
        "tag": tag,
        "env_vars": [{"key": KEY_ENV, "prompt": f"{DISPLAY_NAME} API key", "url": API_KEYS_URL}],
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _url_is_safe(url: str) -> bool:
    """Download targets must be public http(s) URLs (Duckwork' SSRF check when available)."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        return False
    try:
        from tools.url_safety import is_safe_url
    except Exception:
        return urllib.parse.urlsplit(url).scheme == "https"
    return bool(is_safe_url(url))


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    """Re-check every redirect target and drop the API key on any redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 (urllib signature)
        if not _url_is_safe(newurl):
            raise urllib.error.URLError(f"redirect to a blocked address: {newurl}")
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            new_request.remove_header("Authorization")
        return new_request


_OPENER = urllib.request.build_opener(_CheckedRedirects)


def _read_limited(response: Any, limit: int) -> bytes:
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ApiError(f"response is larger than {limit // (1024 * 1024)} MB", code="too_large")
    encoding = str(response.headers.get("Content-Encoding") or "").lower() if response.headers else ""
    if "gzip" in encoding:
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = inflater.decompress(raw, limit + 1)
        if len(raw) > limit or inflater.unconsumed_tail:
            raise ApiError(f"response is larger than {limit // (1024 * 1024)} MB", code="too_large")
    return raw


def _send(request: urllib.request.Request, timeout: float, limit: int) -> tuple[int, Any, bytes]:
    """``(status, headers, body)``; HTTP errors come back as a status, transport errors raise."""
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200) or 200), response.headers, _read_limited(response, limit)
    except urllib.error.HTTPError as exc:
        with contextlib.closing(exc):
            try:
                body = exc.read(MAX_ERROR_BYTES)
            except Exception:
                body = b""
        return int(exc.code), exc.headers, body


def _error_message(parsed: Any, body: bytes, status: int) -> tuple[str, str]:
    """``(message, code)`` from an API error body."""
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("detail") or "").strip()
            code = str(error.get("code") or error.get("type") or "").strip()
            if message:
                return message, code
        elif isinstance(error, str) and error.strip():
            return error.strip(), ""
        for key in ("message", "detail"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip(), ""
    text = body.decode("utf-8", "replace").strip() if body else ""
    return (text[:300] if text and not text.startswith("<") else f"HTTP {status}"), ""


def request_json(
    method: str, url: str, *, payload: Optional[dict[str, Any]] = None, key: str = "", timeout: float = 60.0,
) -> dict[str, Any]:
    """Call the API and return its JSON object; raises :class:`ApiError` on any failure."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", USER_AGENT)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        status, _headers, body = _send(request, timeout, MAX_JSON_BYTES)
    except ApiError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ApiError(f"could not reach the {DISPLAY_NAME} API: {reason}", code="connection_error") from exc
    try:
        parsed = json.loads(body.decode("utf-8")) if body else None
    except ValueError:
        parsed = None
    if status >= 400:
        message, code = _error_message(parsed, body, status)
        raise ApiError(message, status=status, code=code)
    if not isinstance(parsed, dict):
        raise ApiError(f"the {DISPLAY_NAME} API returned an unexpected response", status=status, code="invalid_response")
    return parsed


def download(url: str, *, max_bytes: int, timeout: float = 120.0) -> bytes:
    """Fetch a generated file. No API key is sent; every hop must pass the URL safety check."""
    if not _url_is_safe(url):
        raise ApiError(f"refusing to download from a blocked address: {url}", code="unsafe_url")
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", USER_AGENT)
    try:
        status, _headers, body = _send(request, timeout, max_bytes)
    except ApiError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(f"download failed: {getattr(exc, 'reason', exc)}", code="download_failed") from exc
    if status >= 400:
        raise ApiError(f"download failed with HTTP {status}", status=status, code="download_failed")
    if not body:
        raise ApiError("download returned no data", code="download_failed")
    return body


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class _CatalogCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._failed: dict[str, float] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._failed.clear()

    def get(self, url: str, *, allow_network: bool) -> Optional[list[dict[str, Any]]]:
        now = _now()
        with self._lock:
            entry = self._rows.get(url)
            if entry and now - entry[0] < CATALOG_TTL_SECONDS:
                return entry[1]
            failed_at = self._failed.get(url)
            if not allow_network or (failed_at is not None and now - failed_at < FAILURE_BACKOFF_SECONDS):
                return entry[1] if entry else None
        try:
            payload = request_json("GET", url, timeout=CATALOG_TIMEOUT_SECONDS)
            items = payload.get("data")
            if not isinstance(items, list):
                raise ApiError("model catalog has no data list", code="invalid_response")
        except ApiError as exc:
            logger.debug("%s catalog fetch failed: %s", DISPLAY_NAME, exc)
            with self._lock:
                self._failed[url] = _now()
            return entry[1] if entry else None
        rows = [row for row in items if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]]
        with self._lock:
            self._rows[url] = (_now(), rows)
            self._failed.pop(url, None)
        return rows


_CATALOG = _CatalogCache()


def catalog(*, allow_network: bool = True) -> Optional[list[dict[str, Any]]]:
    """Live model catalog rows (cached for an hour), or None when it cannot be read."""
    return _CATALOG.get(base_url() + "/models", allow_network=allow_network)


def string_list(value: Any) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def param(row: Optional[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
    for spec in (row or {}).get("supported_parameters") or []:
        if isinstance(spec, dict) and spec.get("name") == name:
            return spec
    return None


def param_options(row: Optional[dict[str, Any]], name: str) -> list[str]:
    spec = param(row, name)
    return [str(option) for option in (spec or {}).get("options") or [] if str(option).strip()]


def required_params(row: dict[str, Any]) -> set[str]:
    return {
        str(spec.get("name")) for spec in row.get("supported_parameters") or []
        if isinstance(spec, dict) and spec.get("required")
    }


def serves(row: dict[str, Any], endpoint: str) -> bool:
    return endpoint in string_list(row.get("supported_endpoints")) and not row.get("deprecated")


def find_model(rows: list[dict[str, Any]], model: Optional[str], eligible: Callable[[dict], bool]) -> Optional[dict]:
    """The eligible row whose id or alias is ``model``."""
    wanted = str(model or "").strip()
    if not wanted:
        return None
    for row in rows:
        if eligible(row) and row["id"] == wanted:
            return row
    lowered = wanted.lower()
    for row in rows:
        if eligible(row) and lowered in (alias.lower() for alias in string_list(row.get("aliases"))):
            return row
    return None


def choose_model(
    rows: Optional[list[dict[str, Any]]], eligible: Callable[[dict], bool], default_id: str,
    *candidates: Optional[str],
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """``(model_id, row)``: the first candidate that is an eligible catalog model, else the release
    default, else the first featured eligible model, else the first eligible one. Without a catalog
    the first non-empty candidate (or the release default) is used as is."""
    if not rows:
        chosen = next((c.strip() for c in candidates if isinstance(c, str) and c.strip()), default_id)
        return chosen, None
    for candidate in (*candidates, default_id):
        row = find_model(rows, candidate, eligible)
        if row is not None:
            return row["id"], row
    pool = [row for row in rows if eligible(row)]
    if not pool:
        return None, None
    row = next((r for r in pool if r.get("is_featured")), pool[0])
    return row["id"], row


def catalog_rows_for_picker(rows: Optional[list[dict[str, Any]]], eligible: Callable[[dict], bool]) -> list[dict]:
    """``duckwork tools`` picker rows: id, display name, features and the base price from the catalog."""
    picker = []
    for row in rows or []:
        if not eligible(row):
            continue
        prices = row.get("pricing_rows") if isinstance(row.get("pricing_rows"), list) else []
        first = prices[0] if prices and isinstance(prices[0], dict) else {}
        price = " ".join(str(first.get(key) or "").strip() for key in ("value", "spec")).strip()
        features = ", ".join(feature.replace("_", " ") for feature in string_list(row.get("features"))[:3])
        picker.append({
            "id": row["id"], "display": str(row.get("display_name") or row["id"]),
            "strengths": features, "price": price,
            "modalities": string_list(row.get("input_modalities")) or ["text"],
        })
    return picker


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
_MAX_COUNT_RE = re.compile(r"\b(?:up to|one to|1 to|between \w+ and)\s+(\d+|[a-z]+)\b", re.IGNORECASE)


def max_count_from_description(spec: Optional[dict[str, Any]]) -> int:
    """How many images a parameter accepts, from its catalog description ("Up to 9 ..."); 1 when unstated."""
    text = str((spec or {}).get("description") or "")
    match = _MAX_COUNT_RE.search(text)
    if not match:
        return 1
    token = match.group(1).lower()
    value = int(token) if token.isdigit() else _NUMBER_WORDS.get(token, 1)
    return max(1, min(value, 20))


# ---------------------------------------------------------------------------
# Jobs and outputs
# ---------------------------------------------------------------------------


def job_url(job_id: str) -> str:
    return f"{base_url()}/jobs/{urllib.parse.quote(job_id, safe='')}"


def _job_error_message(job: dict[str, Any], status: str) -> str:
    error = job.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("detail") or "").strip()
        if message:
            return message
    elif isinstance(error, str) and error.strip():
        return error.strip()
    return f"the job ended with status {status}"


def wait_for_job(job_id: str, *, key: str, deadline_seconds: float, interval_seconds: float) -> dict[str, Any]:
    """Poll ``GET /v1/jobs/{job_id}`` until it completes; raises on failure, unknown status or deadline."""
    deadline = _now() + max(0.0, deadline_seconds)
    retries = 0
    while True:
        try:
            job = request_json("GET", job_url(job_id), key=key, timeout=30.0)
            retries = 0
        except ApiError as exc:
            if exc.status in RETRYABLE_POLL_STATUSES and retries < MAX_POLL_RETRIES and _now() < deadline:
                retries += 1
                _sleep(interval_seconds)
                continue
            exc.job_id = job_id
            raise
        status = str(job.get("status") or "").strip().lower()
        if status in JOB_SUCCEEDED:
            return job
        if status in JOB_FAILED:
            raise JobFailed(_job_error_message(job, status), code=status, job_id=job_id)
        if status not in JOB_IN_PROGRESS:
            raise ApiError(f"the job returned an unexpected status {status!r}", code="invalid_response", job_id=job_id)
        if _now() >= deadline:
            raise JobTimeout(f"job {job_id} is still running", code="timeout", job_id=job_id)
        _sleep(interval_seconds)


def first_output(payload: dict[str, Any]) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    """``(url, b64, item)`` of the first output in ``data`` or ``result.data``."""
    for container in (payload, payload.get("result")):
        items = container.get("data") if isinstance(container, dict) else None
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = item.get("url") if isinstance(item.get("url"), str) and item.get("url") else None
                b64 = item.get("b64_json") if isinstance(item.get("b64_json"), str) and item.get("b64_json") else None
                if url or b64:
                    return url, b64, item
    return None, None, {}


def resolve_output(
    payload: dict[str, Any], *, key: str, deadline_seconds: float, interval_seconds: float,
) -> tuple[Optional[str], Optional[str], dict[str, Any], str]:
    """Follow a job envelope when the response is one; ``(url, b64, item, job_id)``."""
    url, b64, item = first_output(payload)
    job_id = str(payload.get("job_id") or "")
    if (url or b64) or not job_id:
        return url, b64, item, job_id
    status = str(payload.get("status") or "").strip().lower()
    if status in JOB_FAILED:
        raise JobFailed(_job_error_message(payload, status), code=status, job_id=job_id)
    job = wait_for_job(job_id, key=key, deadline_seconds=deadline_seconds, interval_seconds=interval_seconds)
    url, b64, item = first_output(job)
    if not (url or b64):
        raise ApiError("the job completed without an output file", code="empty_response", job_id=job_id)
    return url, b64, item, job_id


def decode_b64(data: str) -> bytes:
    if data.startswith("data:") and "," in data:
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def safe_prefix(model: str) -> str:
    return "empiriolabs_" + re.sub(r"[^A-Za-z0-9._-]+", "_", model or "media")[:60]
