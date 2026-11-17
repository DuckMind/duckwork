"""BharatCode provider profile.

OpenAI-compatible inference endpoint at https://bharatcode.ai/api/model/v1
Free for students with an .ac.in / .edu.in email.
"""

from providers import register_provider
from providers.base import ProviderProfile

bharatcode = ProviderProfile(
    name="bharatcode",
    aliases=("bharat-code", "bharatcode-ai"),
    display_name="BharatCode (Student Free)",
    description="BharatCode — free student tier (.ac.in/.edu.in): DeepSeek V4.1 Flash + Qwen 3.8 27B",
    signup_url="https://bharatcode.ai",
    env_vars=("BHARATCODE_API_KEY",),
    base_url="https://bharatcode.ai/api/model/v1",
    api_mode="chat_completions",
    auth_type="api_key",
    supports_vision=True,
    default_max_tokens=32768,
    fallback_models=(
        "deepseek-v4.1-flash",
        "qwen-3.8-27b",
    ),
)

register_provider(bharatcode)
