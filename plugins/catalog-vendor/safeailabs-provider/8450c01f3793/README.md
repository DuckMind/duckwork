# Safe AI Labs provider for Duckwork Agent

Adds Safe AI Labs to Duckwork Agent as the `safeailabs` model provider (alias
`safe-ai-labs`). Safe AI Labs serves an OpenAI-compatible Chat Completions API
with one endpoint per region.

## Install

The plugin has no dependencies beyond Duckwork 0.22.0 or later.

```sh
duckwork plugins install safeailabs-provider
```

Before it is in the catalog, install this repository at a full commit SHA:

```sh
duckwork plugins install https://github.com/DuckMind/duckwork --ref FULL_COMMIT_SHA
```

## Configure

Create a key at https://safeailabs.ai/keys and put it in `~/.duckwork/.env`:

```sh
SAFE_AI_KEY=sail_...
```

Then pick the provider:

```sh
duckwork model --provider safeailabs
```

or a one-shot request:

```sh
duckwork -z "Reply with exactly: ok" --provider safeailabs -m sail-frontier
```

The base URL is `https://us.api.safeailabs.ai/v1`. To use another region, set
`SAFE_AI_BASE_URL` to that region's base URL, listed at
https://safeailabs.ai/docs/regions.

### Timeouts

Duckwork drops a stream that has sent no tokens for 180 seconds on a host it
does not class as local, and the API's keep-alives do not reset that clock. On
a Safe AI Labs API plan a long prompt waits for the plan's token rate before
its first token: about 44 minutes for a 200,000-token prompt on the smallest
plan. Raise the limit for this provider in `~/.duckwork/config.yaml`:

```yaml
providers:
  safeailabs:
    stale_timeout_seconds: 3600
```

## Models

The model list comes from `GET /v1/models` on the configured base URL. When
that call fails the picker offers `sail-frontier`, whose context
window (1,048,576 tokens) the plugin declares. It declares no output limit:
Duckwork sends no `max_tokens`, and the API allows up to 65,536 output tokens.

## Test

```sh
DUCKWORK_AGENT_ROOT=/path/to/duckwork-agent python -m pytest -q tests
```

`SAFE_AI_LIVE_TEST=1` adds a check of the live `/v1/models`; with `SAFE_AI_KEY`
also set it sends two billable chat requests.

## Disclosure

The plugin registers one model provider at import and nothing else: no tools,
hooks, commands or threads. Chat requests and the model list go to
`*.api.safeailabs.ai` through Duckwork's own client with `SAFE_AI_KEY`, which
Duckwork reads. The plugin opens no connections, reads and writes no files,
starts no processes and does not update itself.
