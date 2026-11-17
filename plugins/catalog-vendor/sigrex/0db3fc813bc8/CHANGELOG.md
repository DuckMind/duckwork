# Changelog

## 1.0.0 - 2026-09-25

- First release.
- Sigrex MCP server (`https://mcp.sigrex.io`, Streamable HTTP, OAuth).
- `sigrex` workflow skill with references for code strategies, LLM sessions
  and the signal payload.

## 1.0.1 - 2026-09-26

- Added the catalog banner (`assets/banner.png`, 1200×600).
- No changes to the MCP server configuration or the `sigrex` skill.

## 1.0.4 - 2026-10-02

- Duckwork Agent: documented the connect step. Duckwork signs in only to MCP
  servers the user adds, so the README, the new `after-install.md` and the
  `sigrex` skill now give the one-time `duckwork mcp add` command and the Duckwork
  Desktop steps.
- The `sigrex` skill tells the agent what to do when the Sigrex tools are not
  available yet.
- No changes to the MCP server configuration.