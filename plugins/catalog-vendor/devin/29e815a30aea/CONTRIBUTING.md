# Contributing

Keep changes focused and preserve Duckwork' approval and profile boundaries.
Include a regression test for behavior changes and update the affected documentation.

## Repository layout

- The root Python modules and `plugin.yaml` are the agent plugin.
  Keep the entry points where the Duckwork loader expects them.
- `desktop/` contains the Desktop renderer and `dashboard/` its API.
- `tests/` contains the fake CLI and regression checks.
- `docs/getting-started/` contains installation and usage.
- `docs/guides/` contains Local, Cloud and optional MCP guides.
- `docs/reference/` contains settings, permissions and limitations.
- `docs/development/` contains architecture, run data, process cleanup and testing.
- `assets/` contains README branding and screenshots, not runtime dependencies.

## Use a local checkout

Use one plugin installation method. `duckwork plugins install` refuses to replace a
linked checkout. Older Duckwork Desktop builds may skip linked plugins; update
Desktop or install from Git instead.

Resolve the active profile's home through Duckwork rather than assuming a default folder.
Run these commands in the Duckwork Python environment for that profile.

macOS and Linux:

```sh
duckwork_home="$(python -c 'from duckwork_constants import get_duckwork_home; print(get_duckwork_home())')"
mkdir -p "$duckwork_home/plugins"
ln -s "/path/to/duckwork-devin" "$duckwork_home/plugins/devin"
duckwork plugins enable devin
```

Windows PowerShell:

```powershell
$duckworkHome = python -c "from duckwork_constants import get_duckwork_home; print(get_duckwork_home())"
New-Item -ItemType Directory -Force -Path "$duckworkHome\plugins"
New-Item -ItemType Junction -Path "$duckworkHome\plugins\devin" -Target "C:\path\to\duckwork-devin"
duckwork plugins enable devin
```

Restart Duckwork after changing plugin code. Enable the Desktop half separately under
**Capabilities → Plugins → Devin**.

## Local checks

The Python suite uses a fake Devin CLI and does not start paid Local or Cloud work.
From the repository root:

```sh
cd tests
python -m pytest
cd ..
ruff check .
ruff format --check .
node --check desktop/plugin.js
node tests/desktop_smoke.mjs /path/to/duckwork-agent/node_modules
```

The isolated test environment needs `pytest`, `ruff` and `psutil==7.2.2`.
Duckwork provides `psutil` at runtime. Desktop smoke needs Duckwork' installed React
and React DOM. For host contract checks, set `DUCKWORK_AGENT_DIR` to the Duckwork checkout;
for Desktop checks, set `DUCKWORK_DESKTOP_NODE_MODULES` to its `node_modules` directory.

See [development and testing](docs/development/testing.md) for coverage and platform details.
Never include credentials, private run history or generated caches in a change.
See [TRADEMARKS.md](TRADEMARKS.md) before changing branding assets.
