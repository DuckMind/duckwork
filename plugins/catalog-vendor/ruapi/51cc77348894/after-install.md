# RuAPI providers installed

Set your key and pick a model:

    export RUAPI_API_KEY="..."
    duckwork --provider ruapi --model claude-sonnet-5-5
    duckwork --provider ruapi-openai --model gpt-5.5

`ruapi` serves Claude models over the native Anthropic Messages API, so prompt
caching and thinking work as with Anthropic. `ruapi-openai` serves GPT, Gemini,
DeepSeek, GLM, Qwen, Kimi and other chat models over the OpenAI-compatible API.
Both use the same key. Or run `duckwork model` and choose either provider.

Create an account and an API key at
<https://www.ruapi.ai/register?utm_source=duckwork&utm_medium=plugin>; the setup
guide is at <https://github.com/DuckMind/duckwork>
(по-русски: <https://github.com/DuckMind/duckwork>).
