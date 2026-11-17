"""Reka as a Duckwork model provider: pick Reka in ``duckwork model`` or pass ``--provider reka``.

Reka serves open-weight models behind an OpenAI-compatible API at https://api.reka.ai/v1. What
this plugin adds over pointing a custom endpoint there:

* The model list is a conservative allowlist of models whose catalog metadata declares function
  calling and at least the 64K tokens of context Duckwork requires. Unknown models are left out
  until their capabilities are reviewed; a live model ID alone does not prove compatibility.
* Context window, tool support, reasoning support and image input are declared for each listed
  model, so Duckwork does not have to guess them.
* Reasoning effort goes out as the top-level ``reasoning_effort`` field Reka reads. With no effort
  configured nothing is sent and Reka applies its own model-specific default;
  ``none`` asks for thinking off explicitly.
* Images inside tool results (screenshots, ``vision_analyze``) reach the model as Duckwork' text
  summary, because tool-image compatibility has not been qualified across models. Images you
  attach to a message still go to the models that accept them.
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

API_KEY_ENV = "REKA_API_KEY"
BASE_URL_ENV = "REKA_BASE_URL"
BASE_URL = "https://api.reka.ai/v1"

# Duckwork' reasoning-effort levels, weakest first.
EFFORT_LADDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Recognized request values; live acceptance and behavior remain model-specific.
REKA_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

# Models offered in the picker: id -> (context window in tokens, accepts image input).
# Declared capabilities confirmed via authenticated /v1/models on 2026-10-22;
# catalog presence does not prove availability. Order sets the preferred picker order
# and fallback default. Review context and tool support before adding unknown models.
# A model is added only after it passes a live chat check through Duckwork; catalog
# presence alone cannot add one.
MODELS: dict[str, tuple[int, bool]] = {
    "qwen3.8-27b": (262_144, True),
    "glm5.3-flash": (1_048_576, True),
    "deepseek41-flash-20261017": (1_048_576, True),
    "deepseek4-flash": (262_144, False),
    "deepseek-v4-pro": (1_048_576, False),
    "qwen3.6-27b": (262_144, False),
}


def runs_in_duckwork(model_id: Any) -> bool:
    """Whether *model_id* is a canonical, curated model ID.

    IDs are exact and case-sensitive, matching Duckwork' capability lookup and the string sent
    to the API. Do not coerce malformed values, strip whitespace, or guess aliases: doing so
    could advertise a different ID from the one actually published by the endpoint.
    """
    return isinstance(model_id, str) and model_id in MODELS


def reasoning_effort_for(reasoning_config: Any) -> str | None:
    """The ``reasoning_effort`` value to send, or None to leave the field out.

    Unset sends nothing. Turning reasoning off sends ``none``. A Duckwork level Reka does not have
    (``ultra``) becomes the strongest one it does (``max``). A name that is not a Duckwork level is
    never guessed onto the wire.
    """
    if not isinstance(reasoning_config, dict):
        return None
    requested = str(reasoning_config.get("effort") or "").strip().lower()
    if reasoning_config.get("enabled") is False or requested == "none":
        return "none"
    if requested in REKA_EFFORTS:
        return requested
    if requested in EFFORT_LADDER:
        rank = EFFORT_LADDER.index(requested)
        return [level for level in REKA_EFFORTS if EFFORT_LADDER.index(level) < rank][-1]
    return None


class RekaProfile(ProviderProfile):
    """Reka's OpenAI-compatible endpoint with a top-level reasoning_effort and a runnable model list."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        effort = reasoning_effort_for(reasoning_config)
        return {}, ({"reasoning_effort": effort} if effort else {})

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ) -> list[str] | None:
        models = super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)
        if models is None:
            return None
        # The endpoint may reorder, repeat, or add rows. Preserve the curated picker order
        # and return each known, available model exactly once. Never invent an unavailable
        # model here; Duckwork owns the final picker merge with its fallback list.
        available = {model for model in models if runs_in_duckwork(model)}
        return [model for model in MODELS if model in available]


reka = RekaProfile(
    name="reka",
    aliases=("reka-ai",),
    display_name="Reka",
    description="Reka - OpenAI-compatible API for open-weight models",
    signup_url="https://developer.reka.ai",
    env_vars=(API_KEY_ENV, BASE_URL_ENV),
    base_url=BASE_URL,
    auth_type="api_key",
    default_aux_model="qwen3.8-27b",
    fallback_models=tuple(MODELS),
    supports_vision_tool_messages=False,
    model_capabilities={
        model_id: {
            "context_window": context_window,
            "supports_tools": True,
            "supports_reasoning": True,
            "supports_vision": vision,
        }
        for model_id, (context_window, vision) in MODELS.items()
    },
)

register_provider(reka)
