# duckwork-openpaths

[OpenPaths](https://openpaths.io/) as a standalone Duckwork Agent model-provider plugin. Routes inference through OpenPaths' OpenAI-compatible endpoint, including the `auto`, `auto-easy-task`, `auto-medium-task`, `auto-hard-task` and `auto-think` task-tier routes.

## Install

```
duckwork plugins install openpaths
export OPENPATHS_API_KEY=...
duckwork model          # pick OpenPaths
```

Or from the repo directly: `duckwork plugins install lee101/duckwork-openpaths`. Or drop this directory in `$DUCKWORK_HOME/plugins/model-providers/openpaths/`.

## Config

| Variable | Purpose |
| --- | --- |
| `OPENPATHS_API_KEY` | API key from https://openpaths.io/ |
| `OPENPATHS_BASE_URL` | Optional endpoint override (default `https://openpaths.io/v1`) |

Default model is `auto-medium-task`; auxiliary tasks (compression, summaries) use `auto-easy-task`. The live model list is fetched from `{base_url}/models` with the curated list as fallback.

## Behavior

- Duckwork reasoning effort maps to OpenPaths `reasoning_effort`: disabled -> `none`, `xhigh` -> `high`, `low|medium|high|auto` pass through.
- `auto-think`, `auto-think-task` and `autothink` default to `auto` when no effort is configured.

## Disclosure

Prompts, tool results and conversation context are sent to openpaths.io (and onward to the upstream model vendors it routes to) using your `OPENPATHS_API_KEY`. The plugin makes no other network calls, reads no files, and registers no tools or hooks.

## Test

```
uv run --project /path/to/duckwork-agent pytest tests
```

## License

MIT
