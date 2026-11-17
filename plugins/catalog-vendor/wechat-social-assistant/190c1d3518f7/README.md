<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Duckwork Plugin: wechat-social-assistant

Portable Agent Plugins v1 package bundling the
[wechat-social-assistant](https://github.com/harrylabsj/wechat-social-assistant)
MCP server (local-first WeChat relationship memory for macOS) with a workflow
skill.

- `mcp.json` launches the server via
  `uvx --from wechat-social-assistant==1.5.1 wsa-mcp` — the engine is pinned
  to the immutable PyPI release; PyPI artifacts cannot be replaced after
  upload. Needs `uv` on PATH (Python 3.11+ is fetched by uv when missing).
- All data (SQLite, captures, exports, backups) is confined to the plugin
  data directory via `WSA_ALLOWED_ROOT=${PLUGIN_DATA}` +
  `WSA_MCP_ENFORCE_PATHS=1`; file-like tool arguments outside it are rejected
  by the server.
- The bundled `skills/wechat-social-assistant/SKILL.md` teaches the capture →
  review → follow-up workflow and the hard safety boundaries (never sends
  messages, never reads WeChat's databases, write tools need explicit user
  confirmation).

## Server key note

The MCP server key is `wsa` (short form) to keep tool line names within the
host's 64-character limit. Because the plugin name itself is long
(`wechat-social-assistant`), the host may still replace tool names with a
stable 8-character hash suffix — functionality is unaffected.

## Privacy summary

Local-first by design: no cloud calls, data files are created 0600/0700, OCR
evidence is never overwritten by reviews, retention purge is dry-run first,
and backups are OpenSSL-encrypted with a user-supplied passphrase.
