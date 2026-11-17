"""Abstract model provider for Duckwork Agent."""

from providers.base import ProviderProfile

from providers import register_provider

MODELS = (
    "glm-5.3:superfast",
    "deepseek-v4-flash:superfast",
    "kimi-k3:superfast",
)

abstract = ProviderProfile(
    name="abstract",
    aliases=("abstract-inc",),
    api_mode="codex_responses",
    display_name="Abstract",
    description="Abstract — GLM-5.3, DeepSeek-V4-Flash and Kimi-K3 over the Responses API",
    signup_url="https://platform.abstract.inc/",
    env_vars=("ABSTRACT_API_KEY",),
    base_url="https://api.abstract.inc/v1",
    auth_type="api_key",
    # The live /models list also names lanes this plugin does not offer,
    # so the picker uses the static catalog below.
    supports_model_listing=False,
    fallback_models=MODELS,
    default_aux_model="deepseek-v4-flash:superfast",
    default_max_tokens=65536,
    model_capabilities={
        model: {"supports_vision": False} for model in MODELS
    },
)

register_provider(abstract)
