---
title: Standalone CLI
description: Query telemetry from a terminal, with date filters and JSON output.
---

The `duckwork-telemetry` command reads the same SQLite database as the in-session `/stats` and `/budget` commands, so the gateway does not need to be running. [Installation](/duckwork-telemetry/getting-started/installation/#command-line-tool-optional) explains how to put it on your `PATH`.

If your Duckwork version supports plugin CLI commands, every subcommand below is also available as `duckwork telemetry <subcommand>`.

## Stats

```bash
# Session summary
duckwork-telemetry stats today
duckwork-telemetry stats week
duckwork-telemetry stats month

# Per cron job
duckwork-telemetry stats cron
duckwork-telemetry stats cron-week

# By provider and by model
duckwork-telemetry stats providers
duckwork-telemetry stats models
```

The full set of `stats` subcommands is:

| Group | Subcommands |
| --- | --- |
| Summary | `today` (default), `week`, `month`, `last-7-days`, `last-30-days` |
| Cron jobs | `cron`, `cron-week`, `cron-month` |
| Providers | `providers`, `providers-week`, `providers-month` |
| Models | `models`, `models-week`, `models-month` |

:::note
The CLI spells window variants with a hyphen (`providers-week`), where the chat command uses a space (`/stats providers week`). The `efficiency`, `smells`, and `raw` views are chat-only: they are available through [`/stats`](/duckwork-telemetry/guides/slash-commands/) but not through the standalone CLI.
:::

The summary presets `today`, `week`, and `month` start at 00:00 UTC of the day that begins the window (today, 7 days ago, 30 days ago). The cron, provider, and model subcommands use rolling windows of 7 days, 24 hours, and 24 hours by default (`-week` is 7 days, `-month` is 30 days).

## Budget

```bash
duckwork-telemetry budget                       # status of every scope
duckwork-telemetry budget cron                  # per-cron-job status
duckwork-telemetry budget forecast monthly      # burn-rate projection (defaults: monthly, global)
duckwork-telemetry budget forecast daily profile faro

duckwork-telemetry budget set global daily 5.00
duckwork-telemetry budget set profile monthly 50 --id faro
```

`budget set <scope> <window> <usd>` takes the optional override id as `--id`. See [Budgets](/duckwork-telemetry/guides/budgets/) for what the limits do.

## Date range filters

Every `stats` subcommand accepts `--from` and `--to`. Values are ISO-8601 dates or timestamps, or the literal `now`. `--from` is inclusive and `--to` is exclusive. A date without a time means 00:00:00 UTC of that day.

```bash
# Everything since a specific instant (good for post-deploy windows)
duckwork-telemetry stats models --from 2026-06-16T12:00:00Z

# Bounded range
duckwork-telemetry stats providers --from 2026-06-10 --to 2026-06-15

# Date-only is 00:00:00 UTC of that day
duckwork-telemetry stats today --from 2026-06-01
```

:::caution
In the standalone CLI, `--to` only takes effect together with `--from`. On its own it is ignored and the subcommand's default window applies. The in-chat `/stats` command does honor a lone `--to`.
:::

### Use case: validating a pricing fix

Suppose you fix how a model is priced. The rolling 24-hour window in `stats models` keeps mixing calls from before and after the fix until the old ones age out, so the aggregate is misleading even though new calls are right. Pass the fix's deploy time to see only post-fix calls immediately:

```bash
duckwork-telemetry stats models --from 2026-06-16T12:00:00Z
```

The same flags work inside Duckwork chat through `/stats`, so you do not need to leave the session to run the check.

## JSON output

`--json` prints machine-readable output for scripting.

```bash
duckwork-telemetry stats today --json | jq '.cost_usd'
duckwork-telemetry stats models --from 2026-06-16T12:00:00Z --json \
  | jq '.[] | {model, calls: .total_calls, cost: .cost_usd}'
duckwork-telemetry budget --json | jq '.global'
duckwork-telemetry budget forecast daily --json | jq '.status'
```

Summary subcommands return one object. `cron`, `providers`, and `models` return an array of rows. `budget --json` returns `global`, `cron_jobs`, and `senders` entries; use the text view or the dashboard to see `profile` scopes.

## Pricing snapshots

Every real LLM call captures a pricing snapshot of the tariff that Duckwork core resolved for that model. Two subcommands work with that history. Both are dry-run by default and need `--apply` to write.

```bash
# Seed snapshots for historical models that never got one
duckwork-telemetry pricing backfill
duckwork-telemetry pricing backfill --apply
duckwork-telemetry pricing backfill --json

# Compare pricing.yaml against the core snapshots
duckwork-telemetry pricing drift
duckwork-telemetry pricing drift --apply                 # rewrite drifted entries
duckwork-telemetry pricing drift --threshold 5           # flag drift above 5% (default 1%)
duckwork-telemetry pricing drift --model deepseek/deepseek-v4-pro
duckwork-telemetry pricing drift --json
```

`pricing backfill` seeds a current snapshot for every historical `(provider, model)` pair in `llm_calls` that has none, mainly dated model ids that never matched a live capture. It is a coverage seed, not a historical reconstruction: the tariff written is whatever Duckwork core resolves today. It is idempotent and safe to re-run, and it needs the Duckwork core importable in the same Python environment.

`pricing drift` compares the input and output rates in `pricing.yaml` with the latest core snapshot per model. Cache and reasoning rates are excluded because `pricing.yaml` has no direct analog. It skips `_subscription: true` entries, because a declared `$0` is intentional, and flags anything beyond `--threshold` percent. If some models in `llm_calls` still lack a snapshot, the report tells you to run `pricing backfill` first so that a clean result is not a false all-clear. With `--apply` it merges the core rates back into `pricing.yaml`, never clobbering other fields, and tags each repaired entry `_source: core-snapshot`.

See [Pricing](/duckwork-telemetry/guides/pricing/) for how snapshots fit into cost calculation, and [Pricing engine](/duckwork-telemetry/internals/pricing-engine/) for the design rationale.

:::note
Pricing backfill, drift, and refresh are CLI-only by design. There is no `/pricing` chat command.
:::

## Profile consolidation

`duckwork-telemetry sync-profiles` points every Duckwork profile at one shared telemetry home. See [Profiles and shared home](/duckwork-telemetry/guides/profiles/).
