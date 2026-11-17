"""Runcrate (runcrate.ai) model provider for Duckwork Agent.

Duckwork drives Runcrate-served open models over the OpenAI-compatible API at
https://api.runcrate.ai/v1 with a RUNCRATE_API_KEY (rc_live_...). The model
list comes live from GET /v1/models (public); fallback_models is the static
list Duckwork shows when that call fails.
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

# Every value is passed through as the top-level reasoning_effort field. On
# DeepSeek V4.1 Flash, DeepSeek V3.2 and Kimi K2.6, "none" turns thinking off
# (checked live 2026-10-24); models that cannot turn it off ignore it.
_WIRE_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


class RuncrateProfile(ProviderProfile):
    """Runcrate profile: maps Duckwork reasoning settings to reasoning_effort."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(reasoning_config, dict):
            return {}, {}
        if reasoning_config.get("enabled") is False:
            return {}, {"reasoning_effort": "none"}
        effort = str(reasoning_config.get("effort") or "").strip().lower()
        if effort in _WIRE_EFFORTS:
            return {}, {"reasoning_effort": effort}
        return {}, {}


runcrate = RuncrateProfile(
    name="runcrate",
    aliases=("runcrate-ai", "runcrate.ai"),
    display_name="Runcrate",
    description="Runcrate: open models (DeepSeek, GLM, Qwen, gpt-oss, Kimi) on one OpenAI-compatible API",
    signup_url="https://www.runcrate.ai/dashboard/api-keys",
    env_vars=("RUNCRATE_API_KEY", "RUNCRATE_BASE_URL"),
    base_url="https://api.runcrate.ai/v1",
    auth_type="api_key",
    default_aux_model="deepseek-ai/DeepSeek-V4.1-Flash",
    # [0] is the setup default. These are the open models that are free with a
    # GitHub-linked Runcrate account; the live catalog lists the rest.
    fallback_models=(
        "deepseek-ai/DeepSeek-V4.1-Flash",
        "deepseek-ai/DeepSeek-V4.1-Flash-1017",
        "zai-org/GLM-5.3",
        "zai-org/GLM-5.3-Flash",
        "Qwen/Qwen3.8-Flash",
        "openai/gpt-oss-120b",
    ),
)

register_provider(runcrate)
