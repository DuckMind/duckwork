# Unbrowse for Duckwork Agent

A [Duckwork Agent](https://github.com/DuckMind/duckwork) plugin that gives the agent the hosted
Unbrowse tools and moves public-web work off Duckwork' built-in browser.

What it adds:

- **24 tools** in the `unbrowse` toolset, one per Unbrowse core tool: `unbrowse_scrape`,
  `unbrowse_discover`, `unbrowse_run`, `unbrowse_browse_open`/`_act`/`_snapshot`/`_finish`/`_close`,
  `unbrowse_credentials_*`, `unbrowse_map`, `unbrowse_sites`, `unbrowse_index`, `unbrowse_credits`, and
  more. Each call is a JSON-RPC `tools/call` to the hosted Unbrowse MCP. Dots in the MCP names become
  underscores, because OpenAI-style function names cannot contain dots. The tools are hidden until an
  API key is set.
- **A `web_extract` backend** named `unbrowse`: `web.extract_backend: unbrowse` sends Duckwork'
  `web_extract` through `unbrowse.scrape`. Unbrowse has no general web search, so keep another
  `web_search` backend.
- **A `pre_tool_call` guard** that blocks `browser_*` tools on public sites and tells the model which
  Unbrowse tool to call instead. By default it also blocks `web_extract` on public URLs, unless the
  extract backend is already Unbrowse. Local pages (localhost, loopback, private networks, `*.local`,
  `file:`) still use the built-in browser, because the Unbrowse cloud cannot reach them.
- **The Unbrowse skill**, available as `skill_view("unbrowse:unbrowse")`.

The plugin uses only the Python standard library: `urllib`, no dependencies.

## Install

Every example below uses the default `~/.duckwork`. If you set `DUCKWORK_HOME` or use a profile, the
paths follow it.

```bash
# From GitHub (subdirectory install; Duckwork downloads only this folder)
duckwork plugins install unbrowse-ai/unbrowse/plugins/duckwork --enable

# Or from a local checkout
cp -r plugins/duckwork ~/.duckwork/plugins/unbrowse        # or: ln -s "$PWD/plugins/duckwork" ~/.duckwork/plugins/unbrowse
duckwork plugins enable unbrowse
```

User plugins are opt-in. Nothing loads until the plugin is in `plugins.enabled`, which `--enable` or
`duckwork plugins enable unbrowse` adds. During an interactive install Duckwork asks for
`UNBROWSE_API_KEY` and saves it to `~/.duckwork/.env`. To set it yourself:

```bash
duckwork config set UNBROWSE_API_KEY ub_live_...     # writes ~/.duckwork/.env
```

Optional pip install, which Duckwork finds through the `duckwork_agent.plugins` entry point:

```bash
pip install "git+https://github.com/unbrowse-ai/unbrowse#subdirectory=plugins/hermes/pypi"
duckwork plugins enable unbrowse
```

`pypi/pyproject.toml` sits in a subfolder for a reason. With a `pyproject.toml` next to
`plugin.yaml`, Duckwork treats the plugin as having Python dependencies, asks for consent, and
`install --enable` will not enable it without a TTY.

## Configure

`~/.duckwork/config.yaml`:

```yaml
plugins:
  enabled: [unbrowse]
  entries:
    unbrowse:
      settings:
        blockBrowser: true        # guard browser_* on public sites (default true)
        blockWebExtract: auto     # auto | "true" | "false"; auto = block unless web.extract_backend is unbrowse
        blockWebSearch: false     # Unbrowse has no general web search; keep web_search by default
        # mcpUrl: https://unbrowse.ai/mcp   # UNBROWSE_MCP_URL wins
        # endUser: customer-123            # org keys: X-Unbrowse-End-User (UNBROWSE_END_USER wins)
        # timeout: 180                     # seconds per call
        # apiKey: ...                      # works, but prefer UNBROWSE_API_KEY in .env

# web_extract through Unbrowse
web:
  extract_backend: unbrowse

# Remove the built-in browser toolset entirely (stronger than the guard; also drops local-page browsing)
agent:
  disabled_toolsets: [browser]
```

Environment variables: `UNBROWSE_API_KEY` (required), `UNBROWSE_MCP_URL`, `UNBROWSE_END_USER`, and
`UNBROWSE_ALLOW_BUILTIN_BROWSER=1`, which turns the guard off.

### Ways to replace the built-in browser

| Option | Effect |
|---|---|
| The guard (default) | `browser_navigate` to a public URL, and any `browser_*` call not preceded by a local navigation in the same task, returns a block message naming `unbrowse_scrape`, `unbrowse_discover` then `unbrowse_run`, and `unbrowse_browse_open`. Localhost stays usable. |
| `agent.disabled_toolsets: [browser]` | The model never sees the browser tools. `web_search`/`web_extract` are not in that toolset and stay available. |
| `web.extract_backend: unbrowse` | `web_extract` itself runs on Unbrowse. |
| `tools.override` | **Not used.** Overriding `browser_navigate` and the other browser tools would force Unbrowse's session model into Duckwork' CDP/`@ref` snapshot contract, and it needs a separate capability grant. Separate `unbrowse_*` tools plus the guard give the same routing without replacing built-ins. |

## Verify

```bash
duckwork plugins doctor ~/.duckwork/plugins/unbrowse --ci   # 24 tool(s), 1 hook(s)
duckwork plugins validate ~/.duckwork/plugins/unbrowse
duckwork plugins list                                      # unbrowse  enabled  user
DUCKWORK_PLUGINS_DEBUG=1 duckwork plugins list               # discovery trace
```

In a session, `/plugins` lists `unbrowse v0.1.0 (24 tools, 1 hooks)`. Then ask for something like
"read https://example.com". The model should call `unbrowse_scrape`, and a `browser_navigate` to a
public site gets blocked with guidance.

`duckwork plugins list` reports a subdirectory install as `provenance: drift`, because the installed
folder has no `.git`. `duckwork plugins update` cannot track it, so reinstall with `--force` to update.

## Always-visible skill

Plugin skills are loaded explicitly (`skill_view("unbrowse:unbrowse")`) and are not in the system
prompt's skill index. To list the skill there:

```yaml
skills:
  external_dirs:
    - ~/.duckwork/plugins/unbrowse/skills
```

or `duckwork skills install unbrowse-ai/unbrowse/skill`.

## Alternative: config only, no plugin

Duckwork can mount the remote MCP itself. This needs Duckwork' `mcp` extra, because the `mcp` Python SDK
is not a core dependency:

```yaml
mcp_servers:
  unbrowse:
    url: https://unbrowse.ai/mcp
    headers:
      Authorization: "Bearer ${UNBROWSE_API_KEY}"
      mcp-protocol-version: "2025-11-25"   # the server refuses 2025-06-18 on its streaming path
```

Duckwork sanitizes MCP tool names: every character outside `[A-Za-z0-9_]` becomes `_`, and the name
gets the prefix `mcp__<server>__`. `unbrowse.scrape` becomes `mcp__unbrowse__unbrowse_scrape`, cut to
64 characters with a hash suffix when longer. This path also lists workspace-learned site tools
(`tools/list`). It has no browser guard, no `web_extract` backend and no bundled skill.

## Tests

```bash
cd plugins/duckwork
python -m pytest tests -q          # inside a Duckwork venv; host tests skip when Duckwork is not importable
DUCKWORK_PYTHON=/path/to/duckwork/venv/bin/python python -m pytest tests -q
UNBROWSE_LIVE=1 UNBROWSE_API_KEY=... python -m pytest tests/test_live.py -q   # hosted, opt-in
```

The host tests run the plugin in real Duckwork with a throwaway `DUCKWORK_HOME`. They cover the plugin
loader, the tool registry, `model_tools.handle_function_call`, `web_extract` routing and Plugin Doctor.

`skills/unbrowse` is copied from the repo's `skill/` directory by `node scripts/sync-plugins.mjs`. Do
not edit the copy.

## Network, credentials, license

- **Network:** only `https://unbrowse.ai/mcp` (or `UNBROWSE_MCP_URL`), called with the Python standard library (`urllib`). Pages are fetched by Unbrowse's hosted service. There is no telemetry and there are no runtime dependencies.
- **Credentials:** `UNBROWSE_API_KEY` (or the `apiKey` setting), sent only to Unbrowse as a bearer token. It is never logged or returned in tool results. Website passwords stay in Unbrowse's server-side vault.
- **Hooks:** one `pre_tool_call` guard. It denies `browser_*` and `web_extract` calls to public URLs and points to the Unbrowse tools. Local and private addresses pass, and `UNBROWSE_ALLOW_BUILTIN_BROWSER=1` turns it off.
- **License:** MIT.
