# Pay agent plugin

The official [Pay](https://pay.sh) plugin for AI agents. Discover priced APIs
and pay per request (HTTP 402, x402, MPP) with stablecoins, without API keys.
Every payment is confirmed by you before funds move.

This is a portable [Agent Plugins v1](https://agent-plugins.org/specification)
package. It contains:

- **`mcp.json`**: the hosted Pay MCP server (`https://connect.pay.sh/mcp`,
  Streamable HTTP, OAuth sign-in). No local binary, wallet file or API key.
- **`skills/pay`**: an [Agent Skill](https://agentskills.io) that teaches the
  agent how to pick a provider, plan spend, make the smallest useful paid call,
  and stop on a declined payment.

There is no executable code and nothing that downloads or updates itself.

## Install in Duckwork Agent

From the Duckwork plugin catalog:

```bash
duckwork plugins install pay
duckwork plugins enable pay
```

Or directly from this repository:

```bash
duckwork plugins install solana-foundation/pay/agent-plugins/pay --no-enable
duckwork plugins enable pay
```

Then connect your Pay account. Duckwork signs in only to MCP servers you add
yourself, so add the Pay server once:

```bash
duckwork mcp add pay --url https://connect.pay.sh/mcp --auth oauth --connect-timeout 300
```

Your browser opens the Pay sign-in page. Approve access; the command waits up
to five minutes. Duckwork then lists the Pay tools. They load in your next
session (or after `/reload-mcp`). To sign in again later, run
`duckwork mcp login pay`. Over SSH, follow Duckwork's redirect-paste or
port-forwarding instructions.

Keep the name `pay`: your entry then takes the place of the plugin's server
entry, and the plugin keeps providing the `pay` skill.

In **Duckwork Desktop**, open **Capabilities → Connectors**, choose **Add your
own**, enter name `pay`, type Streamable HTTP, URL
`https://connect.pay.sh/mcp`, auth OAuth, then choose **Authenticate**.

You can browse the catalog before funding the account. When a call needs a
wallet, Pay replies with a setup link.

### Local wallet instead

To keep the wallet on your machine, install the
[`pay-cli`](../pay-cli/README.md) plugin instead. It runs the local `pay mcp`
server. Both plugins can be installed side by side.

## What to know before installing

- **Spends money.** The `curl` tool pays HTTP 402 challenges from your Pay
  balance in stablecoins. Pay asks for confirmation of each payment through MCP
  elicitation; Duckwork shows the request to you and declines it when nobody can
  answer (cron, unattended runs). Hosted Pay also enforces its own spending
  policy. Hosted confirmations do not use local Touch ID.
- **Network calls.** Tool calls go to `connect.pay.sh`, and paid requests reach
  the catalog provider you choose through the Pay gateway.
- **Remote tool set.** The tools are served by the hosted MCP server at runtime
  and are not covered by the pinned commit. The plugin marks the server
  `untrusted`, so Duckwork asks before each write-capable call while the plugin's
  own server entry is in use.
- **Shared account.** Chats that share a Duckwork profile share its Pay account.
  Use a personal profile.
- **Credentials.** OAuth tokens are stored by Duckwork's MCP client in your
  Duckwork home. The plugin reads no credential files.
- **No telemetry** is sent by the plugin.

## License

MIT
