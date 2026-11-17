# Duckwork Memory UI Plugin

Read-only [Duckwork Agent](https://github.com/DuckMind/duckwork) plugin for inspecting memory in Duckwork Dashboard and Duckwork Desktop.

The Dashboard and Desktop interfaces are separate delivery artifacts. They share only the profile-aware Python backend API.

Current scope:

- Built-in memory:
  * `MEMORY.md` - agent notes / environment facts / project conventions
  * `USER.md` - user profile / preferences
- Session search:
  * explicit read-only search over previous Duckwork sessions via Duckwork' `session_search` tool
  * optional source/type filter such as CLI, Telegram, cron, Discord, web, or API sessions
- External memory providers:
  * Holographic memory:
    + local SQLite fact store, default: `$DUCKWORK_HOME/memory_store.db`
    + facts, categories, trust scores, retrieval counters, timestamps
  * Mem0 memory:
    + read-only Mem0 Platform memories via Duckwork' `mem0` provider config
    + memories, user/agent scope, scores returned by search, timestamps, metadata
  * Honcho memory:
    + read-only Honcho workspace, host, peer, and provider configuration state
    + user/AI peer cards, representations, conclusions, and context search
  * Mnemosyne memory:
    + read-only local SQLite store inspection for episodes, facts, instructions, gists, and graph rows
    + explicit recall and injected-context preview through the Duckwork Mnemosyne provider
  * Hindsight memory:
    + read-only/query-only Hindsight provider configuration state
    + explicit recall and reflect actions; no automatic retain/write flow
    + contents view via the official Hindsight client for memory units and retained source documents
  * ByteRover memory:
    + read-only ByteRover CLI (`brv`) project status and registered locations
    + explicit BM25 search and optional query/synthesis action; no curate/write flow

This plugin is intentionally read-only. It does not add, edit, replace, or remove memories. That is deliberate: writes should go through Duckwork' `memory` and `fact_store` tools or provider classes so validation, locking, mirroring, FTS, HRR vectors, and memory-bank maintenance are preserved.

## Screenshots

Current screenshots show the Duckwork Dashboard interface. The Duckwork Desktop interface exposes the same memory sources through a native full-page view.

Built-in memory view:

![Duckwork Memory UI built-in memory view](docs/assets/duckwork-memory-dashboard1.png)

Holographic memory view:

![Duckwork Memory UI holographic memory view](docs/assets/duckwork-memory-dashboard2.png)

Mem0 memory view:

![Duckwork Memory UI Mem0 memory view](docs/assets/duckwork-memory-dashboard3.png)

Honcho memory view:

![Duckwork Memory UI Honcho memory view](docs/assets/duckwork-memory-dashboard4.png)

Hindsight memory view:

![Duckwork Memory UI Hindsight memory view](docs/assets/duckwork-memory-dashboard5.png)

Mnemosyne memory view:

![Duckwork Memory UI Mnemosyne memory view](docs/assets/duckwork-memory-dashboard7.png)

Byterover memory view:

![Duckwork Memory UI Byterover memory view](docs/assets/duckwork-memory-dashboard6.png)

## Requirements

- Duckwork Agent with Duckwork Dashboard or Duckwork Desktop.
- For Dashboard: [dashboard plugin support](https://duckwork-agent.fordex.com/docs/user-guide/features/extending-the-dashboard).
- For Desktop: [Duckwork Desktop Plugin SDK](https://duckwork-agent.fordex.com/docs/developer-guide/desktop-plugin-sdk).
- Optional: external memory provider enabled.

The built-in memory view works always, while external memory provider sections are shown only when configured.

## Dashboard and Desktop delivery

- `dashboard/` is a web Dashboard plugin with its own manifest, tracked browser bundle, and stylesheet.
- `desktop/plugin.js` is a standalone, uncompiled ESM disk plugin. It imports only the Duckwork Desktop SDK, React, and the JSX runtime; it does not require an npm build.
- The Desktop plugin registers the `/memory` full-page route, a `Memory` sidebar item, and an `Open Memory` command-palette action.
- Desktop requests use the plugin-scoped, profile-aware `ctx.rest` client. That client reaches the same `/api/plugins/duckwork-memory-ui/` backend used by Dashboard.

The Desktop UI and Python backend are enabled separately. The regular plugin must be installed and present in `plugins.enabled` so Duckwork mounts `dashboard/plugin_api.py`; copying or enabling only the Desktop disk plugin is not sufficient.

## Installation

The default profile lives at `~/.duckwork`. A named profile lives at `~/.duckwork/profiles/<name>`; use `duckwork -p <name> ...` for plugin commands and set `DUCKWORK_HOME="$HOME/.duckwork/profiles/<name>"` for the copy commands below.

### Install directly from GitHub

```bash
duckwork plugins install xraysight/duckwork-memory-ui --enable
```

This installs and enables the shared backend plus the Dashboard interface.

To enable the Duckwork Desktop interface, copy the disk plugin to `$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui/plugin.js`:

```bash
DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
mkdir -p "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui"
cp "$DUCKWORK_HOME/plugins/duckwork-memory-ui/desktop/plugin.js" \
  "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui/plugin.js"
```

Duckwork Desktop inventories the UI separately under `Settings → Plugins`; enable `Duckwork Memory UI` there if it is disabled.

### Update existing installation

```bash
duckwork plugins update duckwork-memory-ui
DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
mkdir -p "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui"
cp "$DUCKWORK_HOME/plugins/duckwork-memory-ui/desktop/plugin.js" \
  "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui/plugin.js"
```

The second copy step is required because Dashboard/general plugins and Desktop disk plugins use separate delivery directories.

### Install from a local checkout

From this repository directory:

```bash
DUCKWORK_HOME="${DUCKWORK_HOME:-$HOME/.duckwork}"
mkdir -p "$DUCKWORK_HOME/plugins/duckwork-memory-ui"
cp plugin.yaml __init__.py "$DUCKWORK_HOME/plugins/duckwork-memory-ui/"
cp -R dashboard "$DUCKWORK_HOME/plugins/duckwork-memory-ui/"
mkdir -p "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui"
cp desktop/plugin.js "$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui/plugin.js"
```

Make sure `duckwork-memory-ui` is enabled as a regular Duckwork plugin so its Python backend can be mounted. The Desktop UI toggle does not enable backend code.

### Reload the interfaces

#### Dashboard

If the dashboard is already running, force plugin discovery:

```bash
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

Then refresh the browser. A new `Memory` tab should appear.

If the plugin API route returns 404 after installing, restart the dashboard. Duckwork mounts plugin backend routes at dashboard startup.

```bash
duckwork dashboard
```

or stop/start your existing dashboard process/service.

#### Desktop

Duckwork Desktop watches its plugin directory and normally hot-reloads `plugin.js`. If the `Memory` navigation item does not appear, run `Reload desktop plugins` from the command palette and check `Settings → Plugins`.

If it still fails to load, run `duckwork logs gui -f`. If the Desktop UI loads but its scoped API calls return 404, restart the Duckwork gateway after confirming that `duckwork-memory-ui` is present in `plugins.enabled`; backend routes are mounted at gateway startup.

## Development and repository layout

- `desktop/` contains the production Desktop disk plugin source. Keep it as uncompiled ESM without JSX syntax or unsupported imports.
- `dashboard/` contains the Dashboard manifest, shared Python API, and tracked `dist/` browser assets. `dashboard/dist/` is release content, not a disposable local build directory.
- `tests/` contains the Python test suite and production Desktop VM smoke harness.

Run the complete verification suite from the repository root:

```bash
git diff --check
node --check desktop/plugin.js
node --experimental-vm-modules tests/desktop_plugin_smoke.mjs desktop/plugin.js
uv run --with pytest==9.1.1 --with pyyaml==6.0.3 python -m pytest -q
```

## What the UI shows

Both interfaces expose the same configured providers, snapshot filters, visible data, and explicit provider operations, although each uses controls native to its host:

- Snapshot `search` and `limit` apply across providers; `category` and `min_trust` apply only to Holographic facts.
- Hindsight exposes contents, recall, and reflect. Mnemosyne exposes contents, recall with temporal weight, and prefetch preview. ByteRover exposes snapshot search and explicit query/synthesis.
- Session search is always user-triggered and supports a source filter. Desktop also exposes newest/oldest sorting; Dashboard currently submits newest-first.
- Dashboard and Desktop both call the same query-only endpoints. Neither interface exposes provider retain, remember, curate, update, or delete operations.

Top summary:

- built-in entry count
- active Duckwork home
- snapshot generation time
- holographic total fact count only when `memory.provider` is currently `holographic`
- Mem0 memory count only when `memory.provider` is currently `mem0`
- Honcho peer-card fact count only when `memory.provider` is currently `honcho`
- Mnemosyne episode count only when `memory.provider` is currently `mnemosyne`
- Hindsight bank/status only when `memory.provider` is currently `hindsight`
- ByteRover registered location count only when `memory.provider` is currently `byterover`

Built-in memory section:

- Agent memory card (`MEMORY.md`)
- User profile card (`USER.md`)
- path, file existence, modification time
- entry count and char usage bar
- parsed entries

Session search section:

- explicit query box for previous Duckwork sessions
- optional session type/source filter
- results in the selected order (newest first by default) with snippets and short message context
- no automatic search on page load and no memory writes

Holographic memory section, displayed only when `memory.provider` is currently `holographic`:

- DB existence
- whether `memory.provider` is currently `holographic`
- total facts
- facts shown after filters
- entity count
- memory bank count
- filters for search, category, min trust, and limit; click `Apply / refresh` to run them
- fact cards with category, trust score, counters, content, tags, timestamps

Mem0 memory section, displayed when `memory.provider` is currently `mem0`:

- whether Mem0 is the active provider
- whether an API key is present and configured `user_id` and `agent_id`
- memories returned by `get_all()` or `search()` after clicking `Apply / refresh` button
- memory cards with score, user/agent scope, content, timestamps, and metadata

Honcho memory section, displayed when `memory.provider` is currently `honcho`:

- whether Honcho is the active provider
- resolved host, workspace, user peer, AI peer, recall mode, and session strategy
- whether an API key or self-hosted/base URL is configured, without exposing secrets
- user and AI peer cards
- user and AI representations
- conclusions returned for user and AI peers
- context search after clicking `Apply / refresh` button

Mnemosyne memory section, displayed when `memory.provider` is currently `mnemosyne`:

- whether Mnemosyne is the active provider
- local data directory and SQLite DB path
- table counts for episodic memory, Memoria facts/instructions/preferences/timelines, gists, triples, and vector row indexes
- memory and fact cards from the local SQLite store, with search and limit filters
- explicit `Recall` query button for ranked memory retrieval through Duckwork' Mnemosyne provider
- explicit `Preview inject` button for the exact prefetch/auto-inject context returned by the provider
- no remember/sleep/update/forget/import/export endpoint

Hindsight memory section, displayed when `memory.provider` is currently `hindsight`:

- whether Hindsight is the active provider
- resolved mode, bank, budget, memory mode, and auto-retain/auto-recall flags
- whether API/LLM keys are present, without exposing secrets
- explicit `Recall` query button for ranked memory retrieval
- explicit `Reflect` query button for synthesis over memories
- automatically displayed Hindsight contents with a manual reload action for extracted memory units plus retained source documents
- no retain/write endpoint

ByteRover memory section, displayed when `memory.provider` is currently `byterover`:

- whether ByteRover is the active provider
- whether the `brv` CLI is available
- configured project root and optional search scope
- registered ByteRover locations
- explicit BM25 `Search / refresh` action through `brv search --format json`
- explicit `Run query` action through `brv query --format json`
- no `curate`, `review approve`, version-control, sync, or write endpoints

## Holographic DB path resolution

The plugin reads the DB path from:

```yaml
plugins:
  duckwork-memory-store:
    db_path: ...
```

If not configured, it falls back to:

```text
$DUCKWORK_HOME/memory_store.db
```

`$DUCKWORK_HOME`, `${DUCKWORK_HOME}`, and `~` are expanded.

The SQLite connection is opened in read-only mode using `mode=ro`.

## Mem0 configuration

Mem0 support follows Duckwork' bundled `mem0` memory provider convention:

- put secrets in `$DUCKWORK_HOME/.env`, especially `MEM0_API_KEY`
- put non-secret Mem0 scope/config in `$DUCKWORK_HOME/mem0.json`

Example `$DUCKWORK_HOME/.env`:

```bash
MEM0_API_KEY=your-key
```

Example `$DUCKWORK_HOME/mem0.json`:

```json
{
  "user_id": "duckwork-user",
  "agent_id": "duckwork",
  "rerank": true
}
```

Environment values also supported by Duckwork' provider:

- `MEM0_API_KEY`
- `MEM0_USER_ID`
- `MEM0_AGENT_ID`
- `MEM0_RERANK`

`mem0.json` may technically override these values if fields are present, matching Duckwork' provider behavior, but keeping `api_key` in `.env` is the recommended safer layout. The API key is only used server-side to instantiate `mem0.MemoryClient`; it is never returned in plugin responses.
The plugin performs read-only calls:

- `client.get_all(filters={"user_id": ...})` when no search query is provided
- `client.search(query=..., filters={"user_id": ...}, rerank=..., top_k=...)` when search is provided

## Honcho configuration

Honcho support follows Duckwork' bundled `honcho` memory provider convention and reuses Duckwork' provider helpers for config resolution and client creation. Supported config locations are resolved by Duckwork, including:

- `$DUCKWORK_HOME/honcho.json`
- `~/.duckwork/honcho.json`
- `~/.honcho/config.json`
- environment variables such as `HONCHO_API_KEY`, `HONCHO_BASE_URL`, and `HONCHO_ENVIRONMENT`

This fallback order is intentional in Duckwork' Honcho provider contract. For named profiles, Duckwork derives a profile-specific Honcho host key and selects its matching host block; the UI mirrors that resolution instead of imposing different path rules. A profile-local `$DUCKWORK_HOME/honcho.json` still has highest priority.

Honcho is a workspace/peer/session memory system rather than a flat memory list. The UI therefore shows peer cards, representations, conclusions, and context search rather than claiming a complete list of all memories. The API key is only used server-side through Duckwork' Honcho provider helpers; it is never returned in plugin responses.

The plugin performs read-only calls such as:

- `HonchoClientConfig.from_global_config()` and `get_honcho_client(...)`
- `client.peer(...)` for user and AI peers
- `peer.context(target=..., search_query=..., search_top_k=...)`
- `peer.representation(...)` or peer card fallbacks when needed
- `peer.conclusions_of(target).list(...)`

It does not call Honcho dialectic reasoning (`peer.chat()` / `honcho_reasoning`) automatically from page load or `/snapshot`.

## Mnemosyne configuration

Mnemosyne support follows Duckwork' Mnemosyne memory provider convention. The plugin reads non-secret state from:

- `memory.provider: mnemosyne` in `$DUCKWORK_HOME/config.yaml`
- `$DUCKWORK_HOME/mnemosyne/data/mnemosyne.db` by default
- optional `memory.mnemosyne.data_dir` / `memory.mnemosyne.db_path`
- optional environment variables such as `MNEMOSYNE_DATA_DIR`, `MNEMOSYNE_DB_PATH`, `MNEMOSYNE_PREFETCH_CONTENT_CHARS`, and `MNEMOSYNE_AUTO_SLEEP_ENABLED`

The SQLite connection is opened in read-only mode using `mode=ro`. The backend reads ordinary text tables such as `episodic_memory`, `memoria_facts`, `memoria_instructions`, `memoria_preferences`, `memoria_timelines`, `gists`, and `triples`. It deliberately does not query sqlite-vec virtual tables directly; it only counts their rowid side tables when present so the UI works without loading sqlite-vec into the serving Duckwork process.

The plugin performs query-only provider calls:

- `MnemosyneMemoryProvider.initialize(...)`
- `provider.handle_tool_call("mnemosyne_recall", ...)` for explicit recall
- `provider.prefetch(...)` for injected-context preview

It does not expose `mnemosyne_remember`, `mnemosyne_sleep`, `mnemosyne_update`, `mnemosyne_forget`, `mnemosyne_import`, or any other write/maintenance tool.

## Hindsight configuration

Hindsight support uses the active Duckwork `hindsight` memory provider, whether installed from the catalog or bundled by an older host. The plugin reads configuration from the active Duckwork profile:

- `$DUCKWORK_HOME/hindsight/config.json`
- environment variables such as `HINDSIGHT_MODE`, `HINDSIGHT_API_URL`, `HINDSIGHT_DAEMON_URL`, `HINDSIGHT_BANK_ID`, and `HINDSIGHT_BUDGET`

The daemon/API endpoint is resolved with this precedence:

```text
hindsight/config.json api_url > scoped HINDSIGHT_API_URL > scoped HINDSIGHT_DAEMON_URL > mode default
```

For `local_embedded` (also selected by the `local` alias), the mode default is the optional `hindsight_embed` SDK's `get_embed_manager().get_url(profile)`, using the configured profile name or `duckwork`. This resolves the named profile's port from SDK configuration, metadata, or allocation; a named profile may use a port other than 8888. If the SDK is unavailable or its lookup fails, the plugin reads `HINDSIGHT_API_PORT` from `~/.hindsight/profiles/<profile>.env` for a safe profile name and valid port, then falls back to `http://localhost:8888`. The env fallback cannot recover a port after an env rewrite removes that key; the SDK remains authoritative when available. It does not guarantee preservation of a deleted custom port. `local_external` defaults to `http://localhost:8888`, and `cloud` defaults to the Hindsight Cloud URL. Explicit endpoint overrides skip SDK and profile env discovery in every mode.

Endpoint discovery does not start or stop a daemon, initialize the provider, or call its API. The SDK manager constructor may create `~/.hindsight/profiles` while resolving the URL. A remote endpoint, for example `HINDSIGHT_DAEMON_URL=http://192.168.42.20:8888`, is used as configured and does not trigger local daemon startup.

Opening the Hindsight section automatically loads its contents. If a local embedded loopback connection is refused, reset, or disconnected, that read path may run `hindsight-embed daemon start` and retry once with a fresh client. Each attempt closes its client. Authentication, validation, and normal HTTP errors are not retried. Remote, `local_external`, and `cloud` endpoints never start a daemon. "Read-only" means the plugin exposes no memory mutation operation; local process startup can still occur during a contents read.

When local daemon startup is needed, the plugin resolves `hindsight-embed` from `PATH`, the current Python environment, Duckwork' bundled venv under `$DUCKWORK_HOME/duckwork-agent/venv/bin`, the default `~/.duckwork/duckwork-agent/venv/bin`, or `~/.local/bin`. If the binary cannot be found, the error includes safe diagnostics for `PATH`, `sys.executable`, and checked paths.

Secrets such as `HINDSIGHT_API_KEY` and `HINDSIGHT_LLM_API_KEY` are only detected as boolean `*_present` flags and are never returned in plugin responses. Hindsight is query-oriented rather than a complete list API, so the interfaces only call recall/reflect after the user clicks a button. `/snapshot` includes status/config only; the interfaces may separately load the read-only `/hindsight/contents` view on page mount.

Recall and reflect resolve Duckwork' installed Hindsight provider through the host provider resolver, with a bundled import fallback for older hosts that lack that resolver. Contents use the official `hindsight_client` SDK. The calls are:

- `HindsightMemoryProvider.initialize(...)`
- `client.arecall(...)` for explicit recall
- `client.areflect(...)` for explicit reflection
- `Hindsight(...).memory.list_memories(...)` for visible memory units
- `Hindsight(...).documents.list_documents(...)` and `get_document(...)` for retained source documents
- `Hindsight(...).banks.get_agent_stats(...)` for bank counts/status

Recall and reflect show only native Hindsight results. Retained source documents are displayed separately in the contents view; they are not used as a fallback for recall or reflect.

It does not expose `hindsight_retain` or any write UI.

## ByteRover configuration

ByteRover support uses the local `brv` CLI. The plugin reads non-secret configuration from `$DUCKWORK_HOME/byterover.json`, from `plugins.duckwork-memory-ui.byterover` in Duckwork config, or from environment variables.

Example `$DUCKWORK_HOME/byterover.json`:

```json
{
  "brv_path": "brv",
  "project_root": "/path/to/project",
  "search_scope": "docs/",
  "query_timeout": 60
}
```

Environment values:

- `BRV_PATH`
- `BYTEROVER_PROJECT_ROOT`
- `BYTEROVER_SEARCH_SCOPE`
- `BYTEROVER_QUERY_TIMEOUT`

The plugin performs read-only/query-only CLI calls:

- `brv locations --format json`
- `brv status --format json [--project-root ...]`
- `brv search QUERY --format json --limit N [--scope ...]`
- `brv query QUERY --format json` only after the user clicks `Run query`

The query timeout controls how long the backend waits for the ByteRover subprocess; it is not passed as a `brv` CLI option.

It does not expose `brv curate`, `brv review approve`, version-control, push/pull, sync, or other mutation commands.

## API documentation

Backend routes, query parameters, and `curl` examples are documented in [README-API.md](README-API.md).

## Security notes

The plugin displays memory content. Treat this as private data.

Duckwork plugin API routes are intended for trusted Dashboard or Desktop clients. Do not expose the serving dashboard or gateway publicly with untrusted plugins installed unless you understand the risk.

This plugin does not expose mutation endpoints, but it can reveal personal preferences, environment details, project facts, and other durable context stored in memory.

## Design decisions

### Why read-only first?

Memory writes are semantically loaded:

- Built-in memory has limits, delimiter parsing, locking, duplicate handling, and prompt-injection scanning.
- Holographic facts maintain FTS indexes, entity links, HRR vectors, trust scores, and memory banks.
- Mnemosyne maintains embeddings, Memoria-derived structured tables, graph rows, sleep/consolidation flows, and provider-level recall semantics.
- Built-in `memory(add)` may mirror into holographic memory, but `replace`, `remove`, and direct file edits do not reliably mirror.

An interface that writes directly to files or SQLite can silently corrupt memory semantics.

### Why plugin backend instead of direct browser access?

The Dashboard browser and Desktop renderer cannot and should not read local files or SQLite directly. `plugin_api.py` runs inside the serving Duckwork process, resolves the active profile's `DUCKWORK_HOME`, and exposes a narrow JSON API.

## Potential roadmap

Plugin extensions to consider (**feel free to contribute!**):

1. Safer mutation endpoints
   - built-in add/replace/remove via `tools.memory_tool.MemoryStore`
   - holographic add/update/remove via `plugins.memory.holographic.store.MemoryStore`
   - explicit warnings around mirroring and conflict semantics

2. Adapter abstraction
   - `BuiltinAdapter`
   - `HolographicAdapter`
   - `Mem0Adapter`
   - `HonchoAdapter`
   - `HindsightAdapter`
   - `MnemosyneAdapter`
   - `ByteroverAdapter`

3. Diff and hygiene tools
   - find duplicates
   - compare built-in entries mirrored to holographic facts
   - identify stale/low-trust facts
   - identify facts with no entities

4. Export
   - JSON export
   - Markdown export
   - redacted export for sharing/debugging

5. Better search
   - FTS5 query mode for holographic facts
   - entity filter
   - tag filter
   - date ranges

6. Optional surface integrations
   - small Dashboard memory usage widget in `config:top`
   - Desktop status-bar memory usage indicator
   - warning badge when built-in memory is near char limit

## Troubleshooting

### The Dashboard Memory tab does not appear

Check plugin discovery:

```bash
curl http://127.0.0.1:9119/api/dashboard/plugins | jq
```

Force rescan:

```bash
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

Verify the file exists:

```bash
test -f ~/.duckwork/plugins/duckwork-memory-ui/dashboard/manifest.json && echo ok
```

### Backend endpoint returns 404

Confirm that `duckwork-memory-ui` is present in `plugins.enabled`. Backend routes are mounted at process startup, so restart `duckwork dashboard` for the Dashboard interface or the Duckwork gateway used by Desktop.

### The Desktop Memory page does not appear

Check that `$DUCKWORK_HOME/desktop-plugins/duckwork-memory-ui/plugin.js` exists and that the folder name matches the exported plugin ID, then open `Settings → Plugins` and enable `Duckwork Memory UI`. If needed, run `Reload desktop plugins` from the command palette and inspect `duckwork logs gui -f`.

### Holographic section says DB missing

Check whether the DB exists:

```bash
test -f ~/.duckwork/memory_store.db && echo exists
```

If you configured a custom path, inspect:

```bash
duckwork config
```

Look for:

```yaml
plugins:
  duckwork-memory-store:
    db_path: ...
```

### Browser console says SDK is undefined

The plugin script is loading before or outside the Duckwork dashboard plugin runtime, or the dashboard crashed earlier. Refresh the dashboard and inspect browser devtools console/network.

## Current limitations

- Read-only only.
- Holographic search uses simple SQL `LIKE`, not FTS5 query syntax yet.
- Mem0 API mode depends on the `mem0ai` package being installed in the serving Duckwork environment and a configured Mem0 API key.
- Local `mem0.Memory` stores are not supported; this plugin mirrors Duckwork' current cloud/API-oriented Mem0 provider.
- Honcho support depends on Duckwork' bundled Honcho provider helpers and a configured Honcho API key or base URL.
- Hindsight recall and reflect require an installed Duckwork Hindsight provider (catalog or older bundled copy) and a configured Hindsight Cloud/local setup. Contents require `hindsight_client`; embedded endpoint discovery uses `hindsight_embed` when available and has a limited env/default fallback.
- ByteRover support depends on the `brv` CLI being available in the serving Duckwork environment and, for project-specific status/search, a configured or auto-detected ByteRover project.
- No pagination yet; use `limit` filter.

## License

MIT License. See [LICENSE](LICENSE).
