# Setup and project mount

Load this file only when the user needs install, sign-in, access keys, or project mount help.

## Install

Install Proofable on this host, then finish sign-in in the client itself:

`https://mcp.proofable.me/mcp`

If the host already has a Proofable plugin, use the plugin path. Do not also write a second `proofable` entry.

If the client shows no sign-in, use its own MCP login command after the URL is registered.

Have the CLI?

```bash
proofable setup
```

Servers and CI:

```bash
proofable setup --access-key <npk_...>
```

Create access keys under **Account → Access keys** on [proofable.me](https://proofable.me/profile?tab=account). Never paste keys into chat or committed files.

Hosted MCP sign-in: **`https://mcp.proofable.me/mcp`** (discovery/anonymous: `https://mcp.proofable.me/mcp`)

After sign-in, call `proofable_context` once. Reuse a current proof before starting another verification. Full page: https://docs.proofable.me/mcp/setup

## Connect an agent to a project

After Proofable is connected on the machine:

```bash
proofable mount <agentId> --apply <host>
```

| Layer | How |
|-------|-----|
| **Machine** | Plugin, install link, or URL-only MCP config. CLI optional. |
| **Project** | `proofable mount <agentId> --apply <host>` |
| **Session** | `proofable_context` → `proofable_agent_mount` when acting as the agent |

Use `proofable mount` only when acting as a registered profile agent. For proofs and secrets, a completed sign-in plus `proofable_context` is enough.
