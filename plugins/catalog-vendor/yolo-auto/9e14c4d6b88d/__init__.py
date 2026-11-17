"""Yolo-Auto provider profile for Duckwork Agent.

Registers Yolo-Auto (https://yolo-auto.com) as the ``yolo-auto`` provider over
its OpenAI-compatible Chat Completions endpoint. Everything else, credential
resolution, the ``/model`` picker, ``duckwork doctor``, the ``--provider`` flag,
and the setup wizard, auto-wires from the provider registry, so this plugin
touches no Duckwork core files.

Model auto-discovery is the default Duckwork path: the picker fetches
``{base_url}/models`` with Bearer auth on lookup. Yolo-Auto's ``/v1/models``
returns exactly the models the caller's API key can use, plan-filtered, already
ordered, so the picker stays honest without any curated list. ``fallback_models``
only matters offline or when the endpoint is down.

Duckwork core moves fast and a plugin does not choose the user's build, so the
profile fields we set are filtered to what the installed ``ProviderProfile``
dataclass actually accepts. See ``_supported_kwargs``: passing a newer field to
an older build raises TypeError at import, and the loader swallows it, leaving
the user with "unknown provider" and no cause. Filtering degrades to a slightly
less capable profile instead of a silent registration failure.

Maintained by Yolo-Auto. No affiliate, referral, or attribution headers are
added to model requests.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

PROVIDER_ID = "yolo-auto"
API_KEY_ENV = "YOLO_AUTO_API_KEY"
BASE_URL_ENV = "YOLO_AUTO_BASE_URL"

OPENAI_BASE_URL = "https://yolo-auto.com/v1"
SIGNUP_URL = "https://yolo-auto.com/app"

# Declared context window. Yolo-Auto enforces per-plan windows on the request
# path: Free, Solo, and Unlimited cap at 131072; Pro carries 262144. Declaring
# the common denominator keeps Duckwork from packing prompts that the proxy would
# reject for most keys. Users on Pro can raise it with a model_overrides entry.
DECLARED_CONTEXT_WINDOW = 131_072

# Shown when the live GET /v1/models fetch fails or returns nothing: offline
# starts, expired DNS, that kind of thing. The endpoint itself filters by plan,
# so the live picker is always the honest one; this list only keeps the picker
# non-empty when the network is not. Only the flagship models are named here;
# everything else exists solely through live discovery.
FALLBACK_MODELS = (
    "yolo",
    "yolo-small",
)

# Duckwork resolves per-model capabilities from the models.dev catalog, which
# does not know Yolo-Auto's public model ids. Declaring them once feeds the
# /model picker's reasoning badge, image routing, context-window lookup, and
# the dashboard's /api/model/info. Values mirror what the Yolo-Auto proxy
# actually enforces or translates per model:
#   - yolo is the flagship alias: tool calls, image input, and a thinking knob
#     the proxy maps reasoning levels onto
#   - yolo-small is text-only and always thinks; its request profile passes
#     bodies through unchanged, so it advertises no level switch and Duckwork
#     should not offer one
# Any other model your key can run still appears in the picker through live
# discovery; Duckwork falls back to its generic unknown-model handling for
# models not declared here.
MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {
    "yolo": {
        "supports_reasoning": True,
        "supports_vision": True,
        "supports_tools": True,
        "context_window": DECLARED_CONTEXT_WINDOW,
        "model_family": "qwen",
    },
    "yolo-small": {
        "supports_reasoning": True,
        "supports_vision": False,
        "supports_tools": True,
        "context_window": DECLARED_CONTEXT_WINDOW,
        "model_family": "nemotron",
    },
}


def _supported_kwargs(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Drop profile fields the installed Duckwork build does not define."""
    try:
        known = {field.name for field in dataclasses.fields(cls)}
    except TypeError:  # pragma: no cover: non-dataclass profile base
        return dict(kwargs)
    dropped = sorted(set(kwargs) - known)
    if dropped:
        logger.debug(
            "yolo-auto: this Duckwork build has no profile field(s) %s: skipping",
            ", ".join(dropped),
        )
    return {key: value for key, value in kwargs.items() if key in known}


PROFILE_FIELDS: dict[str, Any] = {
    "name": PROVIDER_ID,
    "aliases": ("yoloauto", "yolo_auto"),
    "display_name": "Yolo-Auto",
    "description": "Yolo-Auto: flat-rate OpenAI-compatible API with live model discovery",
    "signup_url": SIGNUP_URL,
    # The final *_BASE_URL entry is the user-facing base-URL override, per the
    # Duckwork provider-plugin contract.
    "env_vars": (API_KEY_ENV, BASE_URL_ENV),
    "base_url": OPENAI_BASE_URL,
    "hostname": "yolo-auto.com",
    "auth_type": "api_key",
    "api_mode": "chat_completions",
    # The flagship alias accepts image content inside tool-result messages.
    # This is a provider-wide wire capability flag; per-model routing reads
    # MODEL_CAPABILITIES, where yolo-small says False.
    "supports_vision": True,
    # The flagship alias is vision-capable, tool-capable, and fast enough for
    # compression, title generation, and vision auxiliary calls.
    "default_aux_model": "yolo",
    "fallback_models": FALLBACK_MODELS,
    "model_capabilities": MODEL_CAPABILITIES,
}

register_provider(ProviderProfile(**_supported_kwargs(ProviderProfile, PROFILE_FIELDS)))
