---
title: Installation
description: Install and enable duckwork-telemetry, set up the command-line tool, and install or update the dashboard plugin.
---

Duckwork plugins are opt-in: you must both install and enable the plugin.

## Requirements

- A working [Duckwork Agent](https://github.com/DuckMind/duckwork) install.
- Python 3.8 or newer in the environment that runs the Duckwork gateway.
- `pyyaml` in that same environment. The plugin reads and writes `pricing.yaml` and `budget.yaml` with it. The standalone dashboard needs it only for its budget features.
- `watchdog` lets the plugin hot-reload `budget.yaml` when it changes outside the gateway process. The code treats it as optional, but the package metadata declares it as a dependency, so `pip install` pulls it in. Without it, in-chat `/budget set` still applies immediately, but manual edits and CLI changes need a gateway restart.

## Option A: install from GitHub

```bash
duckwork plugins install nujovich/duckwork-telemetry
duckwork plugins enable duckwork-telemetry
```

## Option B: manual install

```bash
git clone https://github.com/DuckMind/duckwork ~/.duckwork/plugins/duckwork-telemetry
duckwork plugins enable duckwork-telemetry
```

## Restart the gateway

Plugin changes take effect only after the gateway restarts, because the gateway loads its plugin registry at startup.

```bash
duckwork gateway restart
```

:::caution
If you enable the plugin and cron jobs never show up in `/stats cron week`, a missing gateway restart is the most likely cause. Cron runs that started before the restart have no telemetry.
:::

## Command-line tool (optional)

To run `duckwork-telemetry` from a terminal outside of Duckwork sessions, link the bundled launcher onto your `PATH` once:

```bash
chmod +x ~/.duckwork/plugins/duckwork-telemetry/duckwork-telemetry
ln -s ~/.duckwork/plugins/duckwork-telemetry/duckwork-telemetry ~/.local/bin/duckwork-telemetry
```

A later `git pull` updates the tool in place, so there is no need to re-link. The launcher detects the Python interpreter that Duckwork uses; set `DUCKWORK_PYTHON` to override it.

If your Duckwork version supports plugin CLI commands, the same subcommands are also available as `duckwork telemetry ...`. See [Standalone CLI](/duckwork-telemetry/guides/standalone-cli/).

## Dashboard plugin

duckwork-telemetry also ships as a Duckwork dashboard plugin. When the Duckwork web dashboard starts, it scans `~/.duckwork/plugins/<name>/dashboard/manifest.json` and discovers the plugin from the same install path. There is nothing extra to install: you get a **Telemetry** tab plus widgets on the built-in pages. See [Dashboard](/duckwork-telemetry/guides/dashboard/) for what it shows.

The standalone dashboard (`dashboard/serve.py`) and the plugin manifest (`dashboard/manifest.json`) live in the same directory, so one `git pull` updates both surfaces together.

## Update

For a manual install (Option B), or an Option A install that is a git checkout:

```bash
cd ~/.duckwork/plugins/duckwork-telemetry
git pull
duckwork gateway restart
```

The dashboard picks up front-end changes on a page reload. If an update changes the plugin's backend routes, restart the Duckwork dashboard process as well, because its Python backend is loaded at startup.

Duckwork also exposes `GET /api/dashboard/plugins/rescan` to force a plugin rescan without a restart. Like the rest of the dashboard API, it requires the dashboard session token, so a plain unauthenticated `curl` returns `401`.

## Next steps

- [Quick start](/duckwork-telemetry/getting-started/quick-start/)
- [Setup wizard](/duckwork-telemetry/getting-started/setup-wizard/): what the plugin creates on first load.
