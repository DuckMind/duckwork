"""AnyAPI.ai provider profile for Duckwork Agent.

Registers AnyAPI.ai as a first-class provider over its OpenAI-compatible
Chat Completions endpoint. Everything else — credential resolution, the
``/model`` picker, ``duckwork doctor``, the ``--provider`` flag — auto-wires
from the provider registry, so this plugin touches no core files.

Duckwork is an agent, so the model picker is filtered to the routes AnyAPI tags
as tool-capable. The ``/v1/models`` response carries that capability surface
in its ``tags`` array; routes without tool calling are dropped. The filter
falls back to the unfiltered list whenever the catalog is unreachable or
filters down to nothing, so a degraded picker never becomes an empty one.

Maintained by AnyAPI (https://anyapi.ai).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import urllib.request
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

PROVIDER_ID = "anyapi.ai"
API_KEY_ENV = "ANYAPI_API_KEY"
BASE_URL_ENV = "ANYAPI_BASE_URL"

OPENAI_BASE_URL = "https://api.anyapi.ai/v1"
MODELS_URL = "https://api.anyapi.ai/v1/models"

# AnyAPI tags each route with the request surfaces it accepts. Duckwork is an
# agent, so keep only the routes that advertise tool calling.
_TOOL_TAGS = frozenset({"function_calling", "chat_completions:function_calling"})

_CATALOG_CACHE: list[str] | None = None


def _tool_capable(entry: dict[str, Any]) -> bool:
    """True when a catalog entry advertises tool-calling support."""
    tags = entry.get("tags")
    if not isinstance(tags, list):
        return False
    return bool(_TOOL_TAGS & {tag for tag in tags if isinstance(tag, str)})


def _supported_kwargs(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Drop profile fields the installed Duckwork build does not define.

    ``ProviderProfile`` gains fields over time. Passing one to an older build
    raises ``TypeError`` at import, which the plugin loader swallows — the
    provider then silently fails to register and the user sees "unknown
    provider" with no cause. Declaring the full modern field set and filtering
    it to what this build accepts degrades to a slightly less capable profile
    instead.
    """
    try:
        known = {field.name for field in dataclasses.fields(cls)}
    except TypeError:  # pragma: no cover — non-dataclass profile base
        return dict(kwargs)
    dropped = sorted(set(kwargs) - known)
    if dropped:
        logger.debug(
            "anyapi.ai: this Duckwork build has no profile field(s) %s — skipping",
            ", ".join(dropped),
        )
    return {key: value for key, value in kwargs.items() if key in known}


class AnyApiProfile(ProviderProfile):
    """AnyAPI.ai aggregator — tool-capable catalog filtering."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Return the tool-capable model ids from the AnyAPI catalog.

        A caller-supplied ``base_url`` that differs from the default means the
        user pointed Duckwork at a proxy or a self-hosted relay. That catalog is
        not ours to interpret, so defer to the generic ``/v1/models`` path.
        """
        global _CATALOG_CACHE  # noqa: PLW0603

        caller_base = (base_url or "").strip()
        if caller_base and caller_base.rstrip("/") != self.base_url.rstrip("/"):
            return super().fetch_models(
                api_key=api_key, base_url=base_url, timeout=timeout
            )

        if _CATALOG_CACHE is not None:
            return _CATALOG_CACHE

        models = self._fetch_tool_capable(api_key=api_key, timeout=timeout)
        if models:
            _CATALOG_CACHE = models
            return models

        return super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)

    def _fetch_tool_capable(
        self, *, api_key: str | None, timeout: float
    ) -> list[str] | None:
        """Fetch and filter the capability-annotated catalog, or None."""
        request = urllib.request.Request(MODELS_URL)
        if api_key:
            request.add_header("Authorization", f"Bearer {api_key}")
        request.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode())
        except Exception as exc:
            logger.debug("fetch_models(anyapi.ai): catalog failed: %s", exc)
            return None

        entries = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            logger.debug("fetch_models(anyapi.ai): unexpected catalog shape")
            return None

        seen: set[str] = set()
        models: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict) or not _tool_capable(entry):
                continue
            model_id = entry.get("id")
            if isinstance(model_id, str) and model_id and model_id not in seen:
                seen.add(model_id)
                models.append(model_id)

        if not models:
            logger.debug("fetch_models(anyapi.ai): catalog filtered to zero models")
            return None
        return models


PROFILE_FIELDS: dict[str, Any] = {
    "name": PROVIDER_ID,
    "aliases": ("any-api",),
    "display_name": "AnyAPI.ai",
    "description": "AnyAPI.ai — one key for 400+ models (OpenAI-compatible gateway)",
    "signup_url": "https://anyapi.ai",
    "env_vars": (API_KEY_ENV, BASE_URL_ENV),
    "base_url": OPENAI_BASE_URL,
    "hostname": "anyapi.ai",
    "auth_type": "api_key",
    "api_mode": "chat_completions",
    # AnyAPI relays OpenAI-compatible multimodal content to whichever upstream
    # serves the model.
    "supports_vision": True,
    # Cheap, tool-capable — suits compression, title generation, and vision
    # auxiliary calls.
    "default_aux_model": "anthropic/claude-haiku-4.5",
    # Shown only when the live catalog is unreachable. Flagships spanning the
    # vendors AnyAPI fronts.
    "fallback_models": (
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-opus-4.8",
        "openai/gpt-5.4",
        "google/gemini-3-flash-preview",
        "deepseek/deepseek-v4.1-flash",
        "qwen/qwen3.8-max",
    ),
}

anyapi = AnyApiProfile(**_supported_kwargs(AnyApiProfile, PROFILE_FIELDS))

register_provider(anyapi)
