"""Fordex Router provider profile (default provider; docs/specs/fordex-provider.md).

One OpenAI-compatible endpoint (``https://router.fordex.ai/v1``) with Bearer auth.
Keys look like ``sk-duckmind-<random>``. ``FORDEX_ROUTER_API_KEY`` is the product
env var; ``ROUTER_API_KEY`` is the name used by the router's own setup guide.
The live catalog comes from ``GET /v1/models``; ``fallback_models`` is the
offline list from the guide, with the recommended default first.
"""

from providers import register_provider
from providers.base import ProviderProfile

FORDEX_ROUTER_BASE_URL = "https://router.fordex.ai/v1"
FORDEX_ROUTER_DEFAULT_MODEL = "gpt-6-luna"
FORDEX_ROUTER_KEY_PREFIX = "sk-duckmind-"

fordex_router = ProviderProfile(
    name="fordex-router",
    aliases=("fordex-router-api", "router-fordex"),
    display_name="Fordex Router",
    description="Fordex Router (Recommended: GPT-6 Luna and more via router.fordex.ai)",
    signup_url="https://router.fordex.ai",
    env_vars=("FORDEX_ROUTER_API_KEY", "ROUTER_API_KEY", "FORDEX_ROUTER_BASE_URL"),
    base_url=FORDEX_ROUTER_BASE_URL,
    hostname="router.fordex.ai",
    default_aux_model="gpt-5.6-luna",
    fallback_models=(
        FORDEX_ROUTER_DEFAULT_MODEL,
        "gpt-6-chat-thinking",
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "codex-auto-review",
    ),
)

register_provider(fordex_router)
