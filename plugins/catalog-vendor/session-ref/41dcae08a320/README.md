# session-ref

**Reference another Duckwork session by name — no copying session IDs.**

Type `@session` in the Desktop composer and pick from live session suggestions
(or type part of a session's title right after `@` and it filters as you
type). Picking inserts a compact reference like `@session:"Weekly review"`
into your draft.

> **Spaces in titles:** the `@` popover stops at the first space (that's the
> app's trigger, not this plugin). You don't need to type the full title —
> type the first word and pick from the list, e.g. `@session:Jev` → "Jev
> Setup". Typing `@session` with nothing after it lists your most recent
> sessions to choose from.

That reference is **not expanded or injected** — no session context is copied
into your message. Duckwork sees the reference and resolves it with its own
session-search, so it knows exactly which session you mean, and your context
window stays clean.

## What it does

- Registers a `composer.atCompletions` source (the `@` popover) with the
  Duckwork Desktop plugin SDK.
- Session suggestions come from the gateway's `session.list` RPC — real
  titles, filtered as you type, ordered by relevance then recency.
- Inserts `@session:"<title>"` on pick. No autocomplete, no server-side
  expansion, no context injection — reference only, by design.

## Install (Desktop app on this machine)

```bash
mkdir -p ~/.duckwork/desktop-plugins/session-ref
cp desktop/plugin.js ~/.duckwork/desktop-plugins/session-ref/plugin.js
```

Then in the app: **⌘K → Reload desktop plugins**. Check no error toast
appears; type `@session` in any composer to try it.

## Install (catalog, once accepted)

```bash
duckwork plugins install session-ref
duckwork plugins enable session-ref
```

## Requirements

- Duckwork Desktop (the app loads the plugin; the CLI/gateway alone does not)
- Duckwork >= 0.21 (the `composer.atCompletions` SDK seam)

## How the agent resolves `@session:"<title>"`

The reference reaches the agent as literal text. The agent should resolve it
with its `session_search` tool (read by session id, or discovery by query
matching the title) before answering — and may say it can't find it if the
title was renamed. Titles are unique per Duckwork' session-title rules, so a
title reference is unambiguous at the moment it's sent.

## Development

```bash
# plain JS, no build — edit desktop/plugin.js and reload the app
node --check desktop/plugin.js
```

## License

MIT © kama-dev