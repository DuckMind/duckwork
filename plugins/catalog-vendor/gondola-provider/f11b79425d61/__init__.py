"""Gondola provider profile for Duckwork Agent.

Gondola (https://gondola-ai.com) is a pay-as-you-go marketplace for Venice AI
inference: each request is routed to the cheapest available supplier and
settled in USDC on Base. One OpenAI-compatible endpoint, no subscription.
Prompts and completions are never persisted.

Modeled on plugins/model-providers/novita/__init__.py (registration shape) and
openrouter/__init__.py (fetch_models override + module cache) in
Fordex/duckwork-agent.
"""

import logging

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

_CACHE: list[str] | None = None


def _is_chat_model(entry: dict) -> bool:
    """Keep only chat-capable ids from Gondola's mixed catalog.

    /v1/models lists text, image, and video models (263 ids as of 2026-08,
    ~60% of them non-chat). Prefer the `endpoint` field, fall back to
    `modality`, and include the entry when neither exists so a future shape
    change degrades to the stock behavior instead of an empty picker.
    """
    endpoint = entry.get("endpoint")
    if isinstance(endpoint, str):
        return endpoint == "/v1/chat/completions"
    modality = entry.get("modality")
    if isinstance(modality, str):
        return modality == "text"
    return True


class GondolaProfile(ProviderProfile):
    """Gondola marketplace profile with a chat-only model catalog."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        global _CACHE  # noqa: PLW0603
        if _CACHE is not None:
            return _CACHE

        effective_base = base_url or self.base_url
        if not effective_base:
            return None
        url = effective_base.rstrip("/") + "/models"

        import json
        import urllib.request

        req = urllib.request.Request(url)
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "duckwork-gondola-provider/1.0")
        try:
            try:
                # Duckwork' hardened opener when running inside the agent;
                # plain urllib when exercised standalone (tests, py_compile).
                from duckwork_cli.urllib_security import open_credentialed_url as _open
            except Exception:  # pragma: no cover - standalone fallback

                def _open(r, timeout):
                    return urllib.request.urlopen(r, timeout=timeout)  # noqa: S310

            with _open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            items = data if isinstance(data, list) else data.get("data", [])
            ids = [
                m["id"]
                for m in items
                if isinstance(m, dict) and "id" in m and _is_chat_model(m)
            ]
            if ids:
                _CACHE = ids
            return ids or None
        except Exception as exc:
            logger.debug("fetch_models(gondola): %s", exc)
            return None


gondola = GondolaProfile(
    name="gondola",
    aliases=("gondola-ai",),
    display_name="Gondola",
    description="Gondola, a USDC-settled marketplace for Venice AI inference routed to the cheapest supplier",
    signup_url="https://gondola-ai.com/wallet?tab=keys",
    # GONDOLA_API_KEY is the credential; the _BASE_URL-suffixed var is treated
    # as a base-URL override, not a key, by doctor's _key_vars/_base_var split.
    env_vars=("GONDOLA_API_KEY", "GONDOLA_BASE_URL"),
    base_url="https://api.gondola-ai.com/v1",
    # models_url intentionally unset: the public no-auth catalog lives at
    # {base_url}/models, which is fetch_models()'s default resolution.
    auth_type="api_key",
    default_aux_model="deepseek-v4-flash",
    # Tool-calling models only, per the fallback_models contract in
    # providers/base.py (verified against /v1/models capability flags).
    fallback_models=(
        "deepseek-v4-flash",
        "claude-sonnet-5",
        "kimi-k2-7-code",
        "qwen3-coder-480b-a35b-instruct-turbo",
        "venice-uncensored-1-2",
    ),
)

register_provider(gondola)
