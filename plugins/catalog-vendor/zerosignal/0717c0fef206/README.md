# duckwork-zerosignal-provider

A [Duckwork Agent](https://github.com/DuckMind/duckwork) model-provider plugin for
[ZeroSignal](https://zerosignal.ai): a local proxy onto a pay-per-request, privacy-preserving
inference network. Your wallet is the credential, so there is no API key to manage.

With the plugin installed, ZeroSignal appears as a provider in `duckwork model` and `/model`,
the picker lists the models the proxy currently serves, and Duckwork' reasoning-effort setting
is forwarded to the network as `reasoning_effort`.

## Prerequisites

The ZeroSignal proxy must be running and funded on the same machine:

```sh
zs-proxy proxy start
zs-proxy fund
```

See the [ZeroSignal docs](https://github.com/DuckMind/duckwork) for
installing `zs-proxy` and for the other ways to point Duckwork at the proxy.

## Install

Once the plugin is listed in the Duckwork plugin catalog:

```sh
duckwork plugins install zerosignal
```

Until then, clone it into your Duckwork home:

```sh
git clone https://github.com/DuckMind/duckwork \
  ~/.duckwork/plugins/model-providers/zerosignal
```

Then give Duckwork a key value so it treats the provider as configured. The proxy ignores the
`Authorization` header, so any non-empty value works. Add to `~/.duckwork/.env`:

```sh
ZEROSIGNAL_API_KEY=zerosignal-local
```

Run `duckwork model`, pick **ZeroSignal**, and choose a model.

## Configuration

| Variable | Purpose |
| --- | --- |
| `ZEROSIGNAL_API_KEY` | Required by Duckwork, ignored by the proxy. Any non-empty value. |
| `ZEROSIGNAL_BASE_URL` | Optional. Set it if the proxy listens somewhere other than `http://127.0.0.1:9376/v1`. |

The Duckwork reasoning effort (`agent.reasoning_effort` in `config.yaml`, or `--reasoning` on
the command line) is sent to the proxy as a top-level `reasoning_effort`. Serving nodes
reject levels outside what they declare, so the plugin clamps the requested level onto the
model's `allowed_efforts` from the proxy's `/v1/models` catalog, never upward (Duckwork'
default `medium` becomes `low` on a node that declares `low/high/max`). Models the catalog
does not describe get the request as-is.

## Development

The plugin is validated and tested against one pinned `duckwork-agent` commit, recorded as
`duckwork_ref` under `[tool.duckwork-zerosignal-provider]` in `pyproject.toml`. Duckwork does not
build wheels outside Nix, so install it editable from a checkout at that commit:

```sh
python3.11 -m venv .venv && . .venv/bin/activate
ref="$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["tool"]["duckwork-zerosignal-provider"]["duckwork_ref"])')"
git clone https://github.com/DuckMind/duckwork duckwork-agent-src && git -C duckwork-agent-src checkout "$ref"
pip install -e ./duckwork-agent-src
pip install -e ".[dev]"

duckwork plugins validate .    # the catalog admission check
pytest
```

`.github/workflows/validate.yml` runs the same steps. To move to a newer Duckwork, bump
`duckwork_ref`, re-run both, and mention the upstream commit range in the commit message.

## License

MIT. See [LICENSE](LICENSE).
