# Duckwork Plugin: eatwise

Portable Agent Plugins v1 package bundling the
[eatwise-mcp](https://github.com/harrylabsj/eatwise-mcp) MCP server — the local-first
engine behind **Eatwise (外卖营养教练)**, a Chinese dietary coach: deterministic meal
nutrition reviews, personal daily targets, and consented on-device profile/meal history.
Same engine family as the WorkBuddy expert 外卖营养教练 (chichulaide monorepo,
`ai_backend/`); the engine repo is a byte-for-byte extract (only the version line moved
0.1.1 → 0.2.0).

- `mcp.json` launches the server via
  `npx -y --allow-git=all --package git+https://github.com/harrylabsj/eatwise-mcp#cbc08f64609f64ee453ca21cca427a7eaeaa3158 eatwise-mcp`
  — pinned to an immutable commit; the pin is the only update path. Needs Node.js ≥ 22.5
  on PATH (uses built-in `node:sqlite`; zero npm dependencies).
- `--allow-git=all` is required because **npm 12 disables git-type fetching by default**
  (`allow-git` defaults to `none`); on npm ≤ 11 the flag is a harmless no-op warning.
- All data is confined to the plugin data directory via
  `CHICHULAIDE_LOCAL_HISTORY_PATH=${PLUGIN_DATA}/history.sqlite3`.
- Server key `ew` keeps tool line names short:
  `mcp__agent_plugin_eatwise_<hash8>__ew__configure_local_storage` is 63 chars — inside
  the host's 64-character limit.

## Privacy summary

Local-first by construction: no network calls, no accounts, no analytics, no payments.
Profile and meal data are written only after explicit user consent
(`configure_local_storage`); the profile schema rejects name/phone/city/ID/medical fields.
`export_local_data` and `delete_local_data` are user-initiated tools. Meals are retained
180 days by default (user-adjustable). See the engine's
[PRIVACY.md](https://github.com/harrylabsj/eatwise-mcp/blob/main/PRIVACY.md).
