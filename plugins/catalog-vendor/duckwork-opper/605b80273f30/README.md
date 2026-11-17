# duckwork-opper

[Opper](https://opper.ai) as a first-class model provider for [Duckwork Agent](https://github.com/DuckMind/duckwork).

Opper is the EU-hosted AI gateway: 700+ models from 30+ providers behind one OpenAI-compatible API, one key, no markup on provider rates. This plugin registers the `opper` provider profile so `duckwork model`, `--provider opper`, `duckwork doctor` and the auxiliary-model defaults work out of the box. It ships as a standalone plugin because Duckwork [does not take third-party provider plugins in-tree](https://github.com/DuckMind/duckwork).

## Install

```bash
duckwork plugins install opper-ai/duckwork-opper --enable
echo 'OPPER_API_KEY=<your key>' >> ~/.duckwork/.env   # create one at https://platform.opper.ai
duckwork model                                        # choose "Opper", then a model
```

Or set it directly in `~/.duckwork/config.yaml`:

```yaml
model:
  provider: opper
  default: claude-sonnet-4-6
```

Then check with `duckwork doctor` (probes `OPPER_API_KEY` and `https://api.opper.ai/v3/compat/models`).

## Model ids

Use bare **pool** names: `claude-sonnet-4-6`, `claude-opus-5`, `gpt-5.5`, `gpt-5.4-mini`, `gemini-3.8-flash`, `deepseek-v4-pro`, `kimi-k3`, `mistral-large-2512`. A pool is every provider serving that model; Opper picks the route per request (cheapest, fastest, or EU-pinned via Control Plane rules). To pin one provider or region, prefix it: `anthropic/claude-sonnet-4-6`, `azure/gpt-5.5`, `aws/claude-sonnet-4-6-eu`. The picker fetches the live catalogue from `/v3/compat/models`; the full route list is at <https://opper.ai/models>.

Switch mid-session with `/model opper:gpt-5.4-mini`.

## What the profile sets

| Field | Value |
|---|---|
| `name` / aliases | `opper` / `opper-ai`, `opperai`, `opper.ai` |
| `api_mode` | `chat_completions` (streaming, tools, structured output) |
| `base_url` | `https://api.opper.ai/v3/compat` (override with `OPPER_BASE_URL`) |
| `env_vars` | `OPPER_API_KEY`, `OPPER_BASE_URL` |
| `default_aux_model` | `gpt-5.4-mini` (compression, titles, vision side tasks) |
| `fallback_models` | tool-calling pools shown when the live catalogue is unreachable |

## Without the plugin

Duckwork can already reach Opper as a named custom provider. Add this to `~/.duckwork/config.yaml` and use `/model custom:opper:claude-sonnet-4-6`:

```yaml
providers:
  opper:
    api: https://api.opper.ai/v3/compat
    key_env: OPPER_API_KEY
    transport: chat_completions
```

The plugin adds the picker entry, aliases, `duckwork doctor` checks and aux-model defaults on top of that.

## Pricing and residency

Token rates are the model providers' rates with no markup. Opper charges a 3% fee when you buy credits (5.5% with Control Plane features). Pay-as-you-go, no subscription. Hosted in the EU (AWS Stockholm); requests can be pinned to EU-hosted regions, and audit logs and traces stay in EU storage. Details: <https://opper.ai/pricing>, <https://opper.ai/llm-gateway>.

## Development

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/DuckMind/duckwork /tmp/duckwork-agent
(cd /tmp/duckwork-agent && git sparse-checkout set --cone providers plugins/model-providers duckwork_cli)
pip install pytest pyyaml
PYTHONPATH=/tmp/duckwork-agent pytest -q
```

The tests copy the plugin into a temporary `$DUCKWORK_HOME/plugins/duckwork-opper/` and resolve it through Duckwork' real discovery path.

## License

MIT
