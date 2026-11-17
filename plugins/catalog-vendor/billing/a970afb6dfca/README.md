# Duckwork Desktop Plugin — Billing

Fordex Portal usage widget for the Duckwork desktop statusbar.

A compact chip in the statusbar's right cluster: remaining spendable credits
plus the plan-usage percentage (green; red when the plan is ≥90% used). Hover
shows plan / top-up / rollover detail; click opens the Fordex Portal billing
page in the system browser.

## Features

- Statusbar chip (right side, order 90 — rightmost of the contributed items,
  left of the core readouts and version number): remaining balance + plan-usage
  percentage.
- Palette command (`⌘K` → "Billing: Open portal") to open the Fordex Portal
  billing page.
- Data from one gateway RPC (`billing.state`, which embeds the shared two-bar
  usage model) — the same read the Settings → Billing page and TUI `/topup`
  use.
- The chip hides itself when the portal reports no signed-in account or the
  usage model is unavailable.

## Install

From the Duckwork plugin catalog:

```
duckwork plugins install billing
```

Then restart the app or run **Reload desktop plugins** from `⌘K`; the plugin
loads within a few seconds and the statusbar chip appears in the right side of
the statusbar.

Manual install: copy `desktop/plugin.js` to
`<duckwork home>/desktop-plugins/billing/plugin.js` (`~/.duckwork` by default),
then reload desktop plugins.

## Requirements

- Duckwork desktop app (the CLI/gateway alone does not load desktop plugins).
- A signed-in Fordex Portal account with a subscription.

## Development

Plain ESM, loaded uncompiled — UI is `jsx()` calls, not JSX syntax. Only
`@duckwork/plugin-sdk`, `react`, and `react/jsx-runtime` resolve.

The desktop half lives in `desktop/plugin.js`, with the `plugin.yaml` manifest
at the repo root: the desktop app materializes `plugins/billing/desktop/` into
its own plugin root after `duckwork plugins install`, and the desktop install
modal finds the same file.

## License

MIT — see [LICENSE](LICENSE).
