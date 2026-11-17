"""Together AI provider profile."""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class TogetherProfile(ProviderProfile):
    """Together AI's ``/v1/models`` returns a bare JSON list (not the OpenAI-standard
    ``{"data": [...]}`` wrapper). ``ProviderProfile.fetch_models`` already handles both
    shapes, but ``/model`` validation only consults it for profiles that override
    ``fetch_models`` (see ``models_validate.py::_profile_catalog``) — a plain
    ``ProviderProfile`` instance instead falls through to a generic catalog probe that
    assumes the OpenAI dict shape and crashes on a bare list. This override exists to
    route validation through the shape-aware path; it adds no behavior of its own."""

    def fetch_models(self, **kwargs: Any) -> list[str] | None:
        return super().fetch_models(**kwargs)


together = TogetherProfile(
    name="together", aliases=("together-ai", "togetherai"), display_name="Together AI",
    description="Together AI — OpenAI-compatible direct API, 270+ models",
    signup_url="https://api.together.ai/settings/api-keys",
    env_vars=("TOGETHER_API_KEY", "TOGETHER_BASE_URL"),
    base_url="https://api.together.xyz/v1", auth_type="api_key",
    default_headers={"User-Agent": "DuckworkAgent (duckwork-together-provider)"},
    default_aux_model="deepseek-ai/DeepSeek-V4.1-Flash",
    fallback_models=(
        "deepseek-ai/DeepSeek-V4.1-Flash", "moonshotai/Kimi-K3", "zai-org/GLM-5.3",
        "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8", "openai/gpt-oss-120b",
    ),
)

register_provider(together)
