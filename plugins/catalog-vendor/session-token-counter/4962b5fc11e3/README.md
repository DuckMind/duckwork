# Session Token Counter

A Duckwork Desktop plugin: the accumulated token usage of the session you are looking at,
pinned to the right of the status bar.

```
Σ 1.3M tok (37%)
```

Hover it for the exact numbers.

```
input: 1 234 567
output: 45 678
total: 1 280 245
context: 37%
```

## What it shows

| Field | Meaning |
|---|---|
| `input` / `output` / `total` | Tokens the gateway reports for the focused session |
| `context` | Occupancy of the current context window, in percent |

The indicator follows the focused chat: switch tiles or sessions and it re-reads that
session's usage. It needs no polling — it renders `host.state.focusedUsage`, the same
live `UsageStats` the core status bar reads.

## Requirements

- Duckwork Desktop from a build whose plugin SDK exposes `host.state.focusedUsage`
  (Duckwork **0.20.2** or newer).
- No gateway-side or Python code: this is a Desktop-only, single-file plugin.

## Install

**Install from Git.** Settings → Plugins → **Install from Git**, and use the identifier:

```
Vsemagush/session-token-counter
```

**One-click link.** The `repo` probe shows what will be installed before anything is written:

```html
<a href="duckwork://plugin/install?repo=Vsemagush/session-token-counter&enable=1">Install in Duckwork</a>
```

The same target as a plain URL, for pasting into the app or a message:

```
duckwork://plugin/install?repo=Vsemagush/session-token-counter&enable=1
```

**By hand.** Copy `desktop/plugin.js` to the app-level plugin root and reload:

```
$DUCKWORK_HOME/desktop-plugins/session-token-counter/plugin.js
```

(`~/.duckwork/desktop-plugins/...` by default; the folder name must match the plugin `id`.)
Then run ⌘K → **Reload desktop plugins**. The app hot-reloads the file on every later save.

## Development

No build step: the file is plain ESM, loaded uncompiled by the app. Only
`@duckwork/plugin-sdk`, `react` and `react/jsx-runtime` resolve as imports.

```bash
node --test tests/plugin.test.mjs  # registration, labels, tooltips, missing values
duckwork plugins validate .          # the admission checks the catalog CI runs
```

## License

MIT — see [LICENSE](LICENSE).
