<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Proofable MCP plugin

Identity, scoped access, and proof for AI agents.

This plugin adds the hosted Proofable MCP server and three workflow skills. Install it, finish sign-in in your client, then ask:

```text
Show my Proofable profile and the proofs I can reuse.
```

## Install

Claude Code:

```text
/plugin marketplace add proofable/mcp
/plugin install proofable-mcp@proofable
```

Cursor reads the bundled `.mcp.json`. Codex loads the skills; register the server with:

```bash
npx -y @proofable/sdk setup --client codex
codex mcp login proofable
```

Duckwork Agent loads the three skills from this package. Add the hosted server once, then sign in:

```bash
duckwork mcp add proofable --url https://mcp.proofable.me/mcp --auth oauth
duckwork mcp login proofable
```

Any client that reads Agent Plugins packages can use this folder as is: `plugin.json` declares the package, and `skills/` carries the three workflow skills. Register `https://mcp.proofable.me/mcp` as a Streamable HTTP MCP server with OAuth.

Keep one Proofable connection per client. Do not add a manual `proofable` entry when the plugin or the MCP catalog already registered one.

Included skills:

- `proofable-setup`
- `proofable-trust-workflow`
- `proofable-integrate`

See [Set up Proofable](https://docs.proofable.me/mcp/setup) for every supported client.
