# Wallaby for Duckwork Agent

A model-provider plugin that puts Wallaby in Duckwork' provider list. Pick it in the setup wizard, paste your key, and Duckwork runs on Kimi K3 — no YAML editing, no endpoint trivia.

Wallaby is curated inference for open-weight models: per-token billing, itemized statements on every call, and $0.50 of free credit to start. (The "token" in Wallaby Token is the LLM metering unit, not a cryptocurrency.)

## Install

```bash
duckwork plugins install Dawncoral/wallaby-duckwork-plugin
```

Answer `y` when it asks to enable the plugin (or run `duckwork plugins enable wallaby-provider` later).

Or by hand:

```bash
mkdir -p ~/.duckwork/plugins/model-providers
git clone https://github.com/DuckMind/duckwork ~/.duckwork/plugins/model-providers/wallaby
```

## Set up

Run the wizard and pick **Wallaby**:

```bash
duckwork model
```

It asks for your API key (create one at [wallabytoken.com](https://wallabytoken.com) — new accounts get the $0.50 trial credit) and stores it in your keychain. The Base URL defaults to Wallaby's endpoint — press Enter once more to accept it. Then pick `kimi-k3` as the model, press Enter again to confirm, and choose a reasoning effort when prompted (`medium` is a fine default).

Tested on Duckwork Agent v0.19.0.

Prefer config files? Two lines in `~/.duckwork/config.yaml`, plus one environment variable:

```yaml
model:
  default: kimi-k3
  provider: wallaby
```

```bash
export WALLABY_API_KEY=sk-your-wallaby-key
```

## Verify

```bash
duckwork -z "What model are you? Answer in one sentence."
```

A working setup answers immediately and introduces itself as Kimi.

## What this plugin is

Two files. `__init__.py` registers a `ProviderProfile` (name, base URL, env var, fallback model list); `plugin.yaml` declares `kind: model-provider` so Duckwork discovers it under `~/.duckwork/plugins/`. The setup wizard, `duckwork auth`, the model picker, and the transport all wire themselves to that profile — no core changes, no hooks, no telemetry. The plugin makes no network calls of its own; it only tells Duckwork where the API is.

User plugins override bundled providers of the same name, so this also works as a patch layer if Wallaby ever ships in-tree.

## Links

- Wallaby Token: https://wallabytoken.com
- Duckwork Agent: https://github.com/DuckMind/duckwork

## License

MIT
