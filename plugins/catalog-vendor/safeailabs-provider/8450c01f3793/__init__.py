"""Safe AI Labs as a Duckwork model provider: pick Safe AI Labs in ``duckwork model`` or pass
``--provider safeailabs``.

An OpenAI-compatible API with one endpoint per region. The default base URL is the US region;
``SAFE_AI_BASE_URL`` points it at another region's ``https://<region>.api.safeailabs.ai/v1``.
"""

from providers import register_provider
from providers.base import ProviderProfile

MODEL = "sail-frontier"

safeailabs = ProviderProfile(
    name="safeailabs",
    aliases=("safe-ai-labs",),
    api_mode="chat_completions",
    display_name="Safe AI Labs",
    description="Safe AI Labs (OpenAI-compatible, one endpoint per region)",
    signup_url="https://safeailabs.ai/keys",
    env_vars=("SAFE_AI_KEY", "SAFE_AI_BASE_URL"),
    base_url="https://us.api.safeailabs.ai/v1",
    auth_type="api_key",
    fallback_models=(MODEL,),
    default_aux_model=MODEL,
    # /v1/models reports the same window; declared here so a cold start does not fall back to
    # Duckwork's 200,000-token default for a model it has not seen. No output cap is declared:
    # Duckwork sends no max_tokens and the server allows up to 65,536.
    model_capabilities={
        MODEL: {
            "context_window": 1_048_576,
            "supports_tools": True,
            "supports_reasoning": True,
            "supports_vision": True,
        },
    },
)

register_provider(safeailabs)
