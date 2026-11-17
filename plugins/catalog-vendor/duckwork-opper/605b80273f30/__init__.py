"""Opper provider profile for Duckwork Agent.

Opper (https://opper.ai) is an EU-hosted AI gateway: 700+ models from 30+
providers behind one OpenAI-compatible API and one key. This plugin registers
``opper`` as a first-class provider so ``duckwork model``, ``--provider opper``,
``duckwork doctor`` and the auxiliary-model defaults all work without touching
Duckwork core.

Install::

    duckwork plugins install opper-ai/duckwork-opper --enable
    echo 'OPPER_API_KEY=<your key>' >> ~/.duckwork/.env
    duckwork model            # pick "Opper", then a model

Model ids are Opper *pool* names such as ``claude-sonnet-4-6`` or ``gpt-5.5``:
Opper picks the underlying provider and region per request. Prefix a vendor
(``anthropic/claude-sonnet-4-6``, ``azure/gpt-5.5``) to pin one route. The live
catalogue is fetched from ``https://api.opper.ai/v3/compat/models``; every
route, including EU-pinned ones, is listed at https://opper.ai/models.
"""

from providers import register_provider
from providers.base import ProviderProfile

opper = ProviderProfile(
    name="opper",
    aliases=("opper-ai", "opperai", "opper.ai"),
    display_name="Opper",
    description="Opper — EU-hosted AI gateway, 700+ models behind one OpenAI-compatible API",
    signup_url="https://platform.opper.ai",
    # The trailing *_BASE_URL entry is Duckwork' user override hook (docs: env_vars).
    env_vars=("OPPER_API_KEY", "OPPER_BASE_URL"),
    base_url="https://api.opper.ai/v3/compat",
    auth_type="api_key",
    # Cheap, tool- and vision-capable pool for compression / titles / vision.
    default_aux_model="gpt-5.4-mini",
    # Shown when the live /models fetch fails. Bare Opper pool names (verified
    # against https://api.opper.ai/v3/models on 2026-09-14); tool-calling only.
    fallback_models=(
        "claude-sonnet-4-6",
        "claude-opus-5",
        "gpt-5.5",
        "gpt-5.4-mini",
        "gemini-3.8-flash",
        "deepseek-v4-pro",
        "kimi-k3",
        "mistral-large-2512",
    ),
)

register_provider(opper)
