# Sigrex agent plugin

The official [Sigrex](https://sigrex.io) plugin for AI agents. Build, run and
manage your trading automation in plain language: code and AI strategies,
trading bots, webhooks and signals across crypto exchanges, DEXs and
prediction markets.

This is a portable [Agent Plugins v1](https://agent-plugins.org/specification)
package, so it works in any agent that supports the format. It contains:

- **`mcp.json`**: the official Sigrex MCP server (`https://mcp.sigrex.io`,
  Streamable HTTP, OAuth sign-in). No API keys to copy.
- **`skills/sigrex`**: an [Agent Skill](https://agentskills.io) that teaches
  the agent how Sigrex fits together, how to write code strategies and AI
  trading sessions, and the safety rules for anything that can place a trade.
- **`openclaw.plugin.json`** and **`package.json`**: the same server and skill
  declared for [OpenClaw](https://clawhub.ai/sigrex/plugins/sigrex), so it
  installs natively from ClawHub.

There is no executable code and nothing that downloads or updates itself.

**Requirements:** a free [Sigrex account](https://app.sigrex.io/signup). To
trade live you also need exchange API keys connected in Sigrex, and AI
strategies need an LLM provider key added in your Sigrex settings.

## Install

### Duckwork Agent

Plugin page: https://duckwork-agent.fordex.com/docs/plugins/sigrex

From the Duckwork plugin catalog:

```bash
duckwork plugins install sigrex
duckwork plugins enable sigrex
```

Or directly from this repository:

```bash
duckwork plugins install sigrexio/agent-plugin --no-enable
duckwork plugins enable sigrex
```

Then connect your Sigrex account. Duckwork signs in only to MCP servers you
add yourself, so add the Sigrex server once:

```bash
duckwork mcp add sigrex --url https://mcp.sigrex.io --auth oauth --connect-timeout 300
```

Your browser opens the Sigrex sign-in page. Sign in and approve access; the
command waits up to five minutes. Duckwork then lists the Sigrex tools; press
Enter to keep them all. The tools are available from your next session (or
after `/reload-mcp`). To sign in again later, run `duckwork mcp login sigrex`.

In **Duckwork Desktop**, open **Capabilities → Connectors**, choose **Add your
own** and enter:

| Field | Value |
| --- | --- |
| Name | `sigrex` |
| Type | Streamable HTTP |
| URL | `https://mcp.sigrex.io` |
| Auth | OAuth |

Save, then choose **Authenticate** on the Sigrex card. This link opens Duckwork
Desktop with the same form filled in:

```text
duckwork://mcp/install?name=sigrex&config=eyJ1cmwiOiJodHRwczovL21jcC5zaWdyZXguaW8iLCJhdXRoIjoib2F1dGgifQ
```

Keep the name `sigrex`. Your own entry then takes the place of the server
entry in the plugin, and the plugin keeps providing the `sigrex` skill.

### OpenClaw

Plugin page: https://clawhub.ai/sigrex/plugins/sigrex

From ClawHub (needs OpenClaw 2026.9.7 or newer):

```bash
openclaw plugins install clawhub:@sigrex/sigrex
```

The plugin is enabled on install. If `openclaw plugins list` shows it
disabled, run `openclaw plugins enable sigrex`.

Then connect your Sigrex account: in the OpenClaw Control UI, open the Sigrex
plugin's page and choose **Connect** under **Accounts** (this needs an
administrator connection). Sign in, approve access, and the Sigrex tools become
available. Until you connect, OpenClaw leaves the Sigrex server out of your
agent instead of failing.

Get new releases with `openclaw plugins update --all`. To stay on one version,
install `clawhub:@sigrex/sigrex@1.0.3` instead.

### Other agents

Any agent that supports Agent Plugins v1 can load this folder as a plugin.
If your agent only supports MCP servers, connect `https://mcp.sigrex.io`
directly (see the [MCP server docs](https://docs.sigrex.io/more/mcp-server));
you can also copy `skills/sigrex` into your agent's skills folder if it
supports Agent Skills.

## What you can ask

- "Show me my active strategies and when each one last triggered."
- "Create a strategy for ETHUSDC that goes long when RSI drops below 30 and
  exits at 1% profit. Keep it inactive so I can review it."
- "Duplicate my BTC momentum strategy for SOL and AVAX."
- "My POPCAT strategy hasn't traded in two days. Read its code and storage and
  tell me why."
- "Build an AI session that checks BTC every 15 minutes and journals its
  reasoning."
- "Pause all my bots in the hyperliquid folder."
- "What's the current price of SOL on Binance?"

## Security

- **The connection has full access to your Sigrex account.** The agent can
  create, modify and delete resources, start strategies and send live trading
  signals. Only enable this plugin in agents and profiles you trust.
- The bundled skill tells the agent to create things inactive, to use `TEST`
  signals first, to redact credentials, and to ask before any action that
  activates, trades, shares or deletes. Still review what it proposes.
- Your OAuth token is stored and refreshed by your agent. No credentials live
  in this repository. Disconnect by disabling or removing the plugin, or
  revoke access in your Sigrex account.
- Trading carries risk. Nothing here is financial advice, and Sigrex does not
  support backtesting.

## Links

- MCP server docs: https://docs.sigrex.io/more/mcp-server
- Sigrex docs: https://docs.sigrex.io
- Support: open an issue on this repository

## License

MIT. See [LICENSE](LICENSE).
