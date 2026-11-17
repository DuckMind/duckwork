"""EmpirioLabs AI model provider for Duckwork Agent.

Importing this module registers one ``ProviderProfile`` named ``empiriolabs``.
Duckwork sends chat requests through its own OpenAI-compatible client to
``https://api.empiriolabs.ai/v1`` (or ``EMPIRIOLABS_BASE_URL``) with
``EMPIRIOLABS_API_KEY``; this module never reads the key itself.

The plugin's own network use is limited to the public model catalog
(``GET /v1/models``). It reads the catalog to list the chat models that support
tool calling, to declare their context window, vision and reasoning support, to
pick a low-cost model for auxiliary tasks, and to send ``reasoning_effort`` only
when you choose a level and the model accepts it. The catalog is kept in memory
for an hour; nothing is written to disk.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
import zlib
from typing import Any, Optional

from providers import register_provider
from providers.base import ProviderProfile

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

PROVIDER_NAME = "empiriolabs"
DISPLAY_NAME = "EmpirioLabs AI"
DEFAULT_BASE_URL = "https://api.empiriolabs.ai/v1"
API_KEYS_URL = "https://platform.empiriolabs.ai/dashboard/api-keys"

CHAT_ENDPOINT = "POST /v1/chat/completions"
TOOL_CALLING_FEATURE = "function_calling"

# Picked from the live catalog on 2026-10-19 with the rule resolve_aux_model() applies at
# runtime (the lowest-priced featured chat model with tool calling and at least a 200K context).
# Duckwork uses it only when the runtime lookup has no answer.
DEFAULT_AUX_MODEL = "qwen3-7-flash"

# OFFLINE FALLBACK ONLY. Duckwork shows these two ids when the live catalog cannot be fetched;
# the model list itself always comes from GET /v1/models.
OFFLINE_FALLBACK_MODELS = ("glm-5-3", "qwen3-7-flash")

AUX_MIN_CONTEXT = 200_000
CATALOG_TTL_SECONDS = 3600.0
FAILURE_BACKOFF_SECONDS = 60.0
HOOK_TIMEOUT_SECONDS = 5.0
MAX_CATALOG_BYTES = 32 * 1024 * 1024

# Duckwork' reasoning-effort ladder, weakest to strongest.
EFFORT_LADDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Indirection points so tests can replace the network and the clock.
_urlopen = urllib.request.urlopen
_now = time.monotonic


# ---------------------------------------------------------------------------
# Catalog access
# ---------------------------------------------------------------------------


def _read_body(response: Any) -> bytes:
    """Response body, gunzipped when needed, capped at MAX_CATALOG_BYTES."""
    raw = response.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("model catalog response is too large")
    headers = getattr(response, "headers", None)
    encoding = str(headers.get("Content-Encoding") or "").lower() if headers is not None else ""
    if "gzip" in encoding:
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = inflater.decompress(raw, MAX_CATALOG_BYTES + 1)
        if len(raw) > MAX_CATALOG_BYTES or inflater.unconsumed_tail:
            raise ValueError("model catalog response is too large")
    return raw


def _fetch_rows(url: str, *, api_key: Optional[str] = None, timeout: float = 8.0) -> list[dict[str, Any]]:
    """GET a /models catalog and return its model rows. Raises on any failure."""
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", f"duckwork-empiriolabs/{__version__}")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with _urlopen(request, timeout=timeout) as response:
        payload = json.loads(_read_body(response).decode("utf-8"))
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("model catalog response has no data list")
    return [row for row in items if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]]


class _CatalogCache:
    """Per-URL in-memory catalog with a TTL and a short back-off after a failed fetch."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._failed: dict[str, float] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._failed.clear()

    def store(self, url: str, rows: list[dict[str, Any]]) -> None:
        with self._lock:
            self._rows[url] = (_now(), rows)
            self._failed.pop(url, None)

    def get(
        self, url: str, *, api_key: Optional[str] = None, timeout: float = HOOK_TIMEOUT_SECONDS,
        allow_network: bool = True,
    ) -> tuple[Optional[list[dict[str, Any]]], bool]:
        """``(rows, fetched_now)``. Serves a fresh cache entry, else fetches when allowed and not
        backing off; a failed fetch falls back to stale rows when there are any."""
        now = _now()
        with self._lock:
            entry = self._rows.get(url)
            if entry and now - entry[0] < CATALOG_TTL_SECONDS:
                return entry[1], False
            failed_at = self._failed.get(url)
            backing_off = failed_at is not None and now - failed_at < FAILURE_BACKOFF_SECONDS
        if not allow_network or backing_off:
            return (entry[1] if entry else None), False
        try:
            rows = _fetch_rows(url, api_key=api_key, timeout=timeout)
        except Exception as exc:  # network, HTTP, JSON: the caller degrades to its fallback
            logger.debug("EmpirioLabs AI catalog fetch failed (%s): %s", url, exc)
            with self._lock:
                self._failed[url] = _now()
            return (entry[1] if entry else None), False
        self.store(url, rows)
        return rows, True


_CATALOG = _CatalogCache()


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _is_chat_with_tools(row: dict[str, Any]) -> bool:
    """A chat-completions model that supports tool calling and is not marked deprecated."""
    return (
        CHAT_ENDPOINT in _string_list(row.get("supported_endpoints"))
        and TOOL_CALLING_FEATURE in _string_list(row.get("features"))
        and not row.get("deprecated")
    )


def _has_catalog_metadata(rows: list[dict[str, Any]]) -> bool:
    """False for a plain OpenAI-style list (an endpoint override that is not the EmpirioLabs AI API)."""
    return any("supported_endpoints" in row for row in rows)


def _supports_vision(row: dict[str, Any]) -> bool:
    return "image" in _string_list(row.get("input_modalities")) or "vision" in _string_list(row.get("features"))


def _supports_reasoning(row: dict[str, Any]) -> bool:
    capabilities = row.get("capabilities")
    flagged = isinstance(capabilities, dict) and capabilities.get("reasoning") is True
    return flagged or "reasoning" in _string_list(row.get("features"))


def _context_length(row: dict[str, Any]) -> Optional[int]:
    return _positive_int(row.get("context_length")) or _positive_int(row.get("context_window"))


def _base_price(row: dict[str, Any]) -> Optional[float]:
    """Input plus output price per token at the base tier, or None when not priced per token."""
    pricing = row.get("pricing")
    if isinstance(pricing, list):
        pricing = pricing[0] if pricing and isinstance(pricing[0], dict) else None
    if not isinstance(pricing, dict):
        return None
    try:
        return float(pricing.get("prompt")) + float(pricing.get("completion"))
    except (TypeError, ValueError):
        return None


def _reasoning_options(row: dict[str, Any]) -> tuple[str, ...]:
    """The model's declared ``reasoning_effort`` values, lower-cased, or () when it declares none."""
    for param in row.get("supported_parameters") or []:
        if isinstance(param, dict) and param.get("name") == "reasoning_effort":
            return tuple(str(option).strip().lower() for option in param.get("options") or [] if str(option).strip())
    return ()


def _find_row(rows: list[dict[str, Any]], model: str) -> Optional[dict[str, Any]]:
    """Match a model id exactly, then by one of its catalog aliases."""
    wanted = (model or "").strip()
    if not wanted:
        return None
    for row in rows:
        if row.get("id") == wanted:
            return row
    lowered = wanted.lower()
    for row in rows:
        if lowered in (alias.lower() for alias in _string_list(row.get("aliases"))):
            return row
    return None


def _clamp_effort(requested: str, options: tuple[str, ...]) -> Optional[str]:
    """Map a Duckwork effort onto the model's declared options without ever raising the cost: the
    requested level when offered, else the nearest weaker one, else the weakest offered level.
    ``none`` (reasoning off) maps to the weakest level when the model cannot switch reasoning off.
    A level outside Duckwork' ladder that the model does not declare is never sent."""
    if requested in options:
        return requested
    known = [option for option in options if option in EFFORT_LADDER]
    enabled = [option for option in known if option != "none"]
    if requested not in EFFORT_LADDER or not enabled:
        return None
    weakest = min(enabled, key=EFFORT_LADDER.index)
    if requested == "none":
        return weakest
    weaker = [option for option in enabled if EFFORT_LADDER.index(option) < EFFORT_LADDER.index(requested)]
    return max(weaker, key=EFFORT_LADDER.index) if weaker else weakest


def _requested_effort(reasoning_config: Any) -> Optional[str]:
    """``none`` when reasoning is switched off, the chosen level when one is set, else None."""
    if not isinstance(reasoning_config, dict):
        return None
    if reasoning_config.get("enabled") is False:
        return "none"
    effort = str(reasoning_config.get("effort") or "").strip().lower()
    return effort or None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class EmpirioLabsProfile(ProviderProfile):
    """``ProviderProfile`` whose model list and metadata come from the live EmpirioLabs AI catalog."""

    def _catalog_url(self, base_url: Optional[str] = None) -> str:
        caller_base = (base_url or "").strip().rstrip("/")
        if caller_base and caller_base != (self.base_url or "").rstrip("/"):
            return caller_base + "/models"
        return self.models_url or (self.base_url or DEFAULT_BASE_URL).rstrip("/") + "/models"

    def _declare_capabilities(self, rows: list[dict[str, Any]]) -> None:
        """Record per-model capabilities (by id and alias) in ``model_capabilities``."""
        for row in rows:
            if not _is_chat_with_tools(row):
                continue
            entry: dict[str, Any] = {
                "supports_tools": True,
                "supports_vision": _supports_vision(row),
                "supports_reasoning": _supports_reasoning(row),
            }
            context = _context_length(row)
            if context:
                entry["context_window"] = context
            for key in (row["id"], *_string_list(row.get("aliases"))):
                self.model_capabilities[key] = dict(entry)

    def _rows(self, *, allow_network: bool = True) -> Optional[list[dict[str, Any]]]:
        rows, fetched = _CATALOG.get(self._catalog_url(), allow_network=allow_network)
        if rows and fetched:
            self._declare_capabilities(rows)
        return rows

    # -- Duckwork hooks -------------------------------------------------------------------------

    def fetch_models(
        self, *, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 8.0,
    ) -> Optional[list[str]]:
        """Live chat models that support tool calling (Duckwork always sends tools), catalog order."""
        url = self._catalog_url(base_url)
        try:
            rows = _fetch_rows(url, api_key=api_key, timeout=timeout)
        except Exception as exc:
            logger.debug("EmpirioLabs AI fetch_models failed (%s): %s", url, exc)
            return None
        _CATALOG.store(url, rows)
        if not _has_catalog_metadata(rows):
            return [row["id"] for row in rows]
        self._declare_capabilities(rows)
        return [row["id"] for row in rows if _is_chat_with_tools(row)]

    def resolve_aux_model(self, *, vision: bool = False) -> str:
        """Lowest-priced featured chat model with tool calling and a 200K+ context (vision-capable
        when ``vision``); the lowest-priced eligible model when none is featured; "" without a catalog.
        Variant ids (``model:variantN``) and models without a token price are skipped."""
        try:
            rows = self._rows()
        except Exception:
            return ""
        if not rows:
            return ""
        candidates = []
        for row in rows:
            price = _base_price(row)
            if (
                not _is_chat_with_tools(row) or ":" in row["id"] or price is None or price <= 0
                or (_context_length(row) or 0) < AUX_MIN_CONTEXT or (vision and not _supports_vision(row))
            ):
                continue
            candidates.append((price, row))
        if not candidates:
            return ""
        featured = [item for item in candidates if item[1].get("is_featured")]
        pool = featured or candidates
        return min(pool, key=lambda item: item[0])[1]["id"]

    def default_vision_model(self) -> Optional[str]:
        return self.resolve_aux_model(vision=True) or None

    def get_model_context_length(self, model: str) -> Optional[int]:
        try:
            rows = self._rows()
        except Exception:
            return None
        row = _find_row(rows or [], model)
        return _context_length(row) if row else None

    def supported_reasoning_efforts(self, model: Optional[str]) -> Optional[tuple[str, ...]]:
        rows = self._rows(allow_network=False)
        row = _find_row(rows or [], model or "")
        options = _reasoning_options(row) if row else ()
        return options or None

    def build_api_kwargs_extras(
        self, *, reasoning_config: Optional[dict] = None, **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send a top-level ``reasoning_effort`` only when a level was chosen and the model declares
        one (clamped to its options). Uses the cached catalog only; never makes a request."""
        requested = _requested_effort(reasoning_config)
        if requested is None:
            return {}, {}
        rows = self._rows(allow_network=False)
        row = _find_row(rows or [], str(context.get("model") or ""))
        if row is None:
            return {}, {}
        chosen = _clamp_effort(requested, _reasoning_options(row))
        return ({}, {"reasoning_effort": chosen}) if chosen else ({}, {})


empiriolabs = EmpirioLabsProfile(
    name=PROVIDER_NAME,
    aliases=("empiriolabs-ai", "empirio"),
    api_mode="chat_completions",
    display_name=DISPLAY_NAME,
    description="Chat models with tool calling from the live EmpirioLabs AI catalog",
    signup_url=API_KEYS_URL,
    env_vars=("EMPIRIOLABS_API_KEY", "EMPIRIOLABS_BASE_URL"),
    base_url=DEFAULT_BASE_URL,
    models_url=DEFAULT_BASE_URL + "/models",
    auth_type="api_key",
    default_aux_model=DEFAULT_AUX_MODEL,
    fallback_models=OFFLINE_FALLBACK_MODELS,
)

register_provider(empiriolabs)
