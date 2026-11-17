"""Wallaby Token provider profile for Duckwork Agent.

Registers Wallaby as a first-class model provider: the setup wizard,
`duckwork auth`, `duckwork model`, and the model picker all pick it up from
here. No core changes needed — Duckwork discovers user plugins under
~/.duckwork/plugins/ (flat or model-providers/ category, kind: model-provider).
"""

from providers import register_provider
from providers.base import ProviderProfile

wallaby = ProviderProfile(
    name="wallaby",
    display_name="Wallaby",
    description="Wallaby Token — curated open-weight inference (Kimi K3)",
    signup_url="https://wallabytoken.com",
    env_vars=("WALLABY_API_KEY",),
    base_url="https://api.wallabytoken.com/v1",
    fallback_models=("kimi-k3",),
)

register_provider(wallaby)
