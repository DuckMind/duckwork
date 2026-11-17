# duckwork-together-provider

A [Duckwork Agent](https://duckwork-agent.fordex.com) model-provider plugin
for [Together AI](https://www.together.ai) — an OpenAI-compatible inference
API with 270+ serverless open-weight models.

## Install

```bash
duckwork plugins install pepijndevos/duckwork-together-provider
```

Or manually: drop `__init__.py` and `plugin.yaml` into
`$DUCKWORK_HOME/plugins/together/` (flat, matching the `kind: model-provider`
discovery rule — see the [Model Provider Plugins](https://duckwork-agent.fordex.com/docs/developer-guide/model-provider-plugin)
guide).

Then set your key in `~/.duckwork/.env`:

```
TOGETHER_API_KEY=your-key-here
```

Get a key at <https://api.together.ai/settings/api-keys>.

## What it adds

- `together` provider (aliases `together-ai`, `togetherai`) selectable via
  `duckwork model`, `--provider together`, or `/model <model-id> --provider together`.
- Live model-catalog discovery from Together's `/v1/models` endpoint — this
  plugin overrides `fetch_models()` specifically so model-switch validation
  routes through the shape-aware catalog fetch instead of a generic probe
  that assumes the OpenAI `{"data": [...]}` envelope (Together's `/v1/models`
  returns a bare JSON array; see upstream
  [duckwork-agent#141782](https://github.com/DuckMind/duckwork)).
- A curated `fallback_models` list (current-generation, good price/performance
  picks) used when the live catalog is unreachable.

## Disclosure

- Network calls: only to `https://api.together.xyz/v1` (inference) and its
  `/models` endpoint (catalog discovery), both using the API key you provide.
- No credentials are read from disk directly — the API key is resolved
  through Duckwork's own provider-credential routes (`TOGETHER_API_KEY` /
  `TOGETHER_BASE_URL` env vars), the same mechanism every built-in provider
  (OpenRouter, Fireworks, GMI, ...) uses.
- No telemetry, no background processes, no self-updating code.
- No core overrides — registers through the public `register_provider()` /
  `ProviderProfile` API only.

## Why standalone, not in-tree

duckwork-agent's contribution policy treats third-party vendor model-provider
integrations as plugins, not core-tree additions (see
[CONTRIBUTING.md](https://github.com/DuckMind/duckwork)
and the prior [in-tree PR, closed as not-planned](https://github.com/DuckMind/duckwork)).
This repo ships it the way the policy asks for.

## License

MIT
