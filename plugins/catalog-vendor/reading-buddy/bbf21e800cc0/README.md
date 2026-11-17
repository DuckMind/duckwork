# Duckwork Plugin: reading-buddy

Portable Agent Plugins v1 package bundling the
[reading-buddy](https://github.com/harrylabsj/reading-buddy) MCP server
(local-first WeRead reading companion: shelf/stats/notes sync, private reading
cards and reviews) with a workflow skill (English authoritative +
`SKILL.zh-CN.md` translation variant).

- `mcp.json` launches the server via
  `npx -y --allow-git=all --package git+https://github.com/harrylabsj/reading-buddy#e5f6673790acbcd459c7a51cb428a85393c785e3 reading-buddy-mcp`
  — pinned to an immutable commit; the pin is the only update path. Needs
  Node.js 20+ on PATH.
- `--allow-git=all` is required because **npm 12 disables git-type fetching by
  default** (`allow-git` defaults to `none`); on npm ≤ 11 the flag is a
  harmless no-op warning and git fetching worked by default.
- All data (SQLite-free JSON store, cards, reviews) is confined to the plugin
  data directory via `READING_DATA_DIR` / `READING_CONFIG_DIR`; the server runs
  in its credential-isolated `skill` auth mode. `WEREAD_API_KEY`, when set in
  the user environment, is inherited by the server process; without it the
  built-in demo mode still works.
- Server key `rb` keeps tool line names short:
  `mcp__agent_plugin_reading-buddy_<hash8>__rb__reading_search_books` is 63
  chars — inside the host's 64-character limit.

## Privacy summary

Local-first: no analytics, no posting to WeRead, credentials never leave the
machine, and the explicit-save tool (`reading_save_card`) writes only what the
user has reviewed and confirmed.
