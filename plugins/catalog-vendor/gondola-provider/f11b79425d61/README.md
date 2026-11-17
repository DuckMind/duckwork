# duckwork-gondola-provider

Adds [Gondola](https://gondola-ai.com) as a native model provider for Fordex
Research's [Duckwork Agent](https://github.com/DuckMind/duckwork).

Gondola is a pay-as-you-go marketplace for Venice AI inference: each request is
routed to the cheapest available supplier and settled in USDC on Base. One
OpenAI-compatible endpoint, no subscription, no Venice account. Prompts and
completions are never persisted.

## What you get

- A `gondola` provider in `duckwork model`, `duckwork setup`, and `--provider gondola`
- Live model catalog from Gondola's public `GET /v1/models`, filtered to
  chat-capable models (the raw catalog also lists image and video models)
- A Gondola row in `duckwork doctor`'s API Connectivity section
- A curated fallback model list when the live fetch is unreachable

## Get an API key

1. Mint a key at <https://gondola-ai.com/wallet?tab=keys> (format: `gnd_...`)
2. Top up USDC on Base once at <https://gondola-ai.com/wallet>
3. Setup guides for other tools: <https://gondola-ai.com/guides>

## Recommended install

Clone straight into the directory Duckwork scans for model-provider plugins:

**macOS / Linux / WSL:**

```bash
mkdir -p "$HOME/.duckwork/plugins/model-providers"
git clone https://github.com/DuckMind/duckwork \
  "$HOME/.duckwork/plugins/model-providers/gondola-provider"
```

**Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\duckwork\plugins\model-providers" | Out-Null
git clone https://github.com/DuckMind/duckwork `
  "$env:LOCALAPPDATA\duckwork\plugins\model-providers\gondola-provider"
```

(replace the base directory with `$DUCKWORK_HOME` if you set that variable)

## Alternative: duckwork plugins install

```
duckwork plugins install Gondola-Market/duckwork-gondola-provider
```

This path is tracked by `duckwork plugins list/update/remove`, but the installer
places model-provider plugins in a directory the provider registry does not
scan, so one manual move is required afterwards. The on-screen after-install
note (also in [after-install.md](after-install.md)) has the exact commands.

## Configure

```bash
export GONDOLA_API_KEY=gnd_...   # or let the installer prompt and save it
duckwork model                     # pick Gondola, then a model
duckwork -z "hello" --provider gondola -m deepseek-v4-flash
```

Or pin it in `~/.duckwork/config.yaml`:

```yaml
model:
  provider: gondola
  default: deepseek-v4-flash
```

## Verify

Run `duckwork doctor`. With the plugin in place, Gondola appears under API
Connectivity; the probe is a `GET /v1/models` with your key as Bearer. Note
that this endpoint is public, so the row proves reachability, not key
validity: a wrong key still surfaces on the first paid request.

## Models

Curated fallbacks: `deepseek-v4-flash` (default aux), `claude-sonnet-5`,
`kimi-k2-7-code`, `qwen3-coder-480b-a35b-instruct-turbo`,
`venice-uncensored-1-2`. The live catalog (100+ text models incl.
`hermes-3-llama-3.1-405b`, plus image and video via Gondola's other
endpoints) is at <https://api.gondola-ai.com/v1/models> with per-model
pricing, context windows, and capability flags.

## Payments

The plugin authenticates with `GONDOLA_API_KEY`; each request is metered
against your prepaid USDC balance. Separately, Gondola's API accepts
accountless per-request x402 payments (HTTP 402 challenges, USDC on Base)
for clients that speak the protocol natively; Duckwork is not one of them, so
the plugin always uses key auth.

## Updating / removing

- Installed via git clone: `git pull` in the plugin directory, or delete it.
- Installed via `duckwork plugins install`: `duckwork plugins update gondola-provider`
  / `duckwork plugins remove gondola-provider` manage the flat install location
  only; if you moved the directory per after-install.md, manage it with git
  directly.

## Compatibility notes

Duckwork' plugin manifest has no minimum-version field, so this plugin tracks
`ProviderProfile` in `providers/base.py` on duckwork-agent `main`. If a Duckwork
update renames profile fields, reinstall the latest version of this plugin.

## License

MIT
