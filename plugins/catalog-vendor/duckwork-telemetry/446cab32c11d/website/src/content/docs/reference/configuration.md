---
title: Configuration and data location
description: Where duckwork-telemetry keeps its files, and which settings and environment variables change its behavior.
---

## Data location

All telemetry state lives in a `telemetry/` directory under your Duckwork home:

```text
~/.duckwork/telemetry/
├── telemetry.db        SQLite database (WAL mode)
├── telemetry.log       plugin log: errors, debug output, one-time warnings
├── pricing.yaml        your price overrides plus auto-fetched prices
├── budget.yaml         your spend guardrails
├── enforcement_mode    sidecar written at startup so the dashboards know the mode (enforce or observe)
└── .pricing_refresh    sentinel: its modification time is the last pricing refresh
```

If `pricing.yaml` and `budget.yaml` do not exist, the plugin still works. It falls back to its built-in prices and runs with budgets disabled, and the [setup wizard](/duckwork-telemetry/getting-started/setup-wizard/) creates defaults on first load.

The database grows over time and nothing purges old rows automatically. See [Known limitations](/duckwork-telemetry/reference/known-limitations/#database-retention).

## Plugin setting

The plugin has one setting, `mode`, configured through Duckwork:

```yaml
plugins:
  entries:
    duckwork-telemetry:
      settings:
        mode: enforce   # default; set to observe for telemetry-only
```

`enforce` keeps budget blocking active. `observe` records and reports without enforcing. The value is read when the plugin registers, so a change needs a restart of the Duckwork process that owns the plugin. See [Setup wizard](/duckwork-telemetry/getting-started/setup-wizard/#enforcement-mode).

## Environment variables

| Variable | Effect |
| --- | --- |
| `DUCKWORK_HOME` | The Duckwork home. Telemetry lives in `$DUCKWORK_HOME/telemetry/`. Defaults to `~/.duckwork`. |
| `DUCKWORK_TELEMETRY_HOME` | Opt-in shared telemetry root. Outranks `DUCKWORK_HOME` for `telemetry.db`, `budget.yaml`, and `pricing.yaml`. See [Profiles and shared home](/duckwork-telemetry/guides/profiles/). |
| `DUCKWORK_TELEMETRY_NO_SETUP` | Set to `1` to skip the first-load auto-setup. |
| `DUCKWORK_PYTHON` | Python interpreter used by the `duckwork-telemetry` launcher. Defaults to the interpreter Duckwork uses. |

Telemetry paths resolve with the precedence `DUCKWORK_TELEMETRY_HOME`, then `DUCKWORK_HOME`, then `~/.duckwork`.

:::note
With `DUCKWORK_TELEMETRY_HOME` set, the database, `budget.yaml`, `pricing.yaml`, and `enforcement_mode` move to the shared root. `telemetry.log`, the `.pricing_refresh` sentinel, and the setup wizard's file lookups still use `DUCKWORK_HOME`. Duckwork's own `state.db` and `cron/` are never relocated.
:::

## File formats

- [`pricing.yaml`](/duckwork-telemetry/guides/pricing/#pricingyaml): per-model prices, defaults, and metadata tags.
- [`budget.yaml`](/duckwork-telemetry/guides/budgets/#budgetyaml): limits per scope, thresholds, and estimated-data handling.

For the full list of files and the database schema, see [User config files](/duckwork-telemetry/internals/user-config-files/) and [Database layer](/duckwork-telemetry/internals/database-layer/) in the Internals section.
