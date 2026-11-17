"""OpenPaths provider profile (OpenAI-compatible, openpaths.io).

Request quirk: top-level ``reasoning_effort`` in OpenPaths' vocabulary (none/low/medium/high/auto);
``xhigh`` is sent as ``high`` and the ``auto-think`` routes default to ``auto``.
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

_AUTO_THINK_MODELS = frozenset({"auto-think", "auto-think-task", "autothink"})
_EFFORTS = frozenset({"none", "low", "medium", "high", "auto"})


def openpaths_reasoning_effort(model: str | None, reasoning_config: dict | None) -> str | None:
    if isinstance(reasoning_config, dict):
        if reasoning_config.get("enabled") is False:
            return "none"
        effort = str(reasoning_config.get("effort") or "").strip().lower()
        if effort == "xhigh":
            return "high"
        if effort in _EFFORTS:
            return effort
    if (model or "").strip().lower() in _AUTO_THINK_MODELS:
        return "auto"
    return None


class OpenPathsProfile(ProviderProfile):
    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        effort = openpaths_reasoning_effort(model, reasoning_config)
        return {}, ({"reasoning_effort": effort} if effort else {})


register_provider(OpenPathsProfile(
    name="openpaths",
    aliases=("openpath", "open-paths", "open-path"),
    display_name="OpenPaths",
    description="OpenPaths (auto task-tier model routing)",
    signup_url="https://openpaths.io/",
    env_vars=("OPENPATHS_API_KEY", "OPENPATHS_BASE_URL"),
    base_url="https://openpaths.io/v1",
    auth_type="api_key",
    default_aux_model="auto-easy-task",
    fallback_models=(
        "auto-medium-task",
        "auto",
        "auto-easy-task",
        "auto-hard-task",
        "auto-think",
        "autothink",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
        "gemini-3.1-pro-preview",
        "gemini-2.5-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ),
))
