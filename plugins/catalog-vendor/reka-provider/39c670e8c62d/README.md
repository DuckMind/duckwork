# Reka for Duckwork

Connect Duckwork directly to [Reka](https://developer.reka.ai) using its existing
model picker and API client. Requires Duckwork **0.21.6 or later** and a Reka API key.
The plugin adds no runtime dependencies.

## Connect

```sh
duckwork plugins install "https://github.com/DuckMind/duckwork" --enable
duckwork model
```

If the installer asks for `REKA_API_KEY`, paste your key (the prompt hides it) or
press Enter to add it in the next step. In `duckwork model`, select **Reka**, enter
your API key if Duckwork asks for it, press Enter to keep the default endpoint, choose **qwen3.8-27b**, then pick a reasoning effort.
Higher levels can help with harder tasks but are slower; **Disable reasoning** is
the fastest. Duckwork saves the key and model selection for the active profile. For
a named profile, use `duckwork -p PROFILE` for both commands. No manual YAML edit is
needed.

## Configuration

Duckwork reads `REKA_API_KEY` and sends requests to `https://api.reka.ai/v1`.
`REKA_BASE_URL` optionally selects another authorized endpoint. The provider ID is
`reka`; use this canonical name in `reka:qwen3.8-27b` model syntax.

```sh
duckwork chat --provider reka -m qwen3.8-27b
```

The picker offers six models that support tool calling, have at least the 64K
tokens of context Duckwork needs for an agent turn, and passed a live chat check
through Duckwork:

| Model | Context window | Image input |
|---|---:|---|
| `qwen3.8-27b` (default) | 262,144 | Yes |
| `glm5.3-flash` | 1,048,576 | Yes |
| `deepseek41-flash-20261017` | 1,048,576 | Yes |
| `deepseek4-flash` | 262,144 | No |
| `deepseek-v4-pro` | 1,048,576 | No |
| `qwen3.6-27b` | 262,144 | No |

Qwen 3.8 27B is the default and also runs Duckwork's background tasks. Your Reka
account decides which models you can call, so a model in the picker is not a
guarantee of access. After updating the plugin, run `duckwork model --refresh` to
clear cached model IDs. The plugin doesn't update itself: run
`duckwork plugins update reka-provider` every few weeks to get new models and fixes.

The plugin sends Reka's top-level `reasoning_effort`: unset stays omitted,
off sends `none`, and Duckwork's `ultra` maps to `max`. Which levels a model
accepts varies by model. Images you attach follow each model's declared
capability. Images inside tool results use Duckwork's text fallback.

## Scope

Prompts, tool definitions and results, supported user images, and model-list
requests go to the configured Reka endpoint through Duckwork. Credentials and
configuration stay managed by Duckwork. The plugin registers one provider; it adds
no tools, background services, telemetry, credential files, or update mechanism.

MIT license; the license text is included in the installed directory.
