# sidebar-cycle

A Duckwork Desktop plugin that steps through the **left sidebar's session rows in the order you see them**, one row per key press, and wraps from the last row to the first (and back).

| Shortcut | Action |
|---|---|
| `⌃⌘]` (Ctrl+Cmd+]) | Next sidebar session |
| `⌃⌘[` (Ctrl+Cmd+[) | Previous sidebar session |

Both are rebindable under **Settings → Keyboard Shortcuts** (`Next sidebar session (wraps)` / `Previous sidebar session (wraps)`).

## Why

The built-in `session.next` / `session.prev` walk sessions by **recency** and open the recent-session switcher HUD on repeated presses while Ctrl is held. When you want to move down the sidebar exactly as it is laid out — pinned rows, date groups, your manual drag order, active filters — this plugin does that instead.

## How it works

It uses only the public plugin SDK (`@duckwork/plugin-sdk`):

- **Order** — a zero-size marker rendered into each session row through the `SESSION_ROW_AREAS.leading` slot. Walking the markers in document order gives the sidebar's real render order.
- **Current session** — `host.state.focusedStoredSessionId`.
- **Navigation** — `host.openSession(id)`.
- **Long lists** — the Recents list is virtualized, so at the edge of the rendered window the plugin scrolls its own marker into view to render more rows before deciding to wrap.

It does not query, click, or restyle the app's own markup, so sidebar styling changes do not break it.

## Install

```bash
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable sidebar-cycle
```

Then reload desktop plugins (`⌘K` → **Reload desktop plugins**) or restart Duckwork Desktop.

## Requirements

Duckwork Desktop with the plugin SDK session-row slots (Duckwork `>=0.21.5`). Desktop-only; no Python half, tools, hooks, or environment variables.

## License

MIT
