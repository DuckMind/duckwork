# Abstract Provider for Duckwork Agent

This plugin adds [Abstract](https://abstract.inc)'s inference API to Duckwork Agent as
the `abstract` model provider. Duckwork talks to `https://api.abstract.inc/v1` over the
OpenAI Responses API (`codex_responses` mode) with live streaming.

## Install

The plugin has no runtime dependencies beyond Duckwork. Install it from this repository,
pinned to a full commit SHA:

```sh
duckwork plugins install https://github.com/DuckMind/duckwork --ref FULL_COMMIT_SHA
```

Replace `FULL_COMMIT_SHA` with the full reviewed commit hash. Review the installer's
scan and consent prompts.

## Configure

Get an API key at [platform.abstract.inc](https://platform.abstract.inc), or with the
`abstract` CLI (`abstract login`, then `abstract token`). Set it in the active Duckwork
profile's environment:

```bash
export ABSTRACT_API_KEY="your-api-key"
```

Select the provider and a model:

```bash
duckwork model --provider abstract
```

Or in `config.yaml`:

```yaml
model:
  provider: abstract
  default: glm-5.3:superfast
```

One-shot request:

```bash
duckwork -z "Reply with exactly: ok" --provider abstract -m glm-5.3:superfast
```

## Models

| Model | Input $/M | Cached input $/M | Output $/M |
|---|---|---|---|
| `glm-5.3:superfast` | 1.19 | 0.26 | 4.40 |
| `deepseek-v4-flash:superfast` | 0.10 | 0.05 | 0.25 |
| `kimi-k3:superfast` | 3.00 | 0.30 | 12.75 |

Prices are per million tokens; see [abstract.inc/pricing](https://abstract.inc/pricing)
for the current rates. Output is capped at 65,536 tokens per response. Input is text
only. The API refuses request bodies over 2 MiB.

The plugin uses a static catalog of these three models: Abstract's `/models` endpoint
also lists background (`:async`) lanes, which complete by submit-and-poll and are not
offered here. `deepseek-v4-flash:superfast` is the default auxiliary model
(compression, titles).

## What it does

The plugin registers one model provider at import and nothing else: no tools, hooks,
commands, threads or files. Duckwork' own client sends chat requests (prompts, context
and tool definitions) to `https://api.abstract.inc/v1` with `ABSTRACT_API_KEY`, which
Duckwork reads. Requests are billed to the key's Abstract account.

## License

MIT
