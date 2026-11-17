# StalkChain is installed

Two steps are left before the StalkChain tools appear.

**1. Enable the plugin**

```bash
duckwork plugins enable stalkchain
```

**2. Connect your StalkChain account**

```bash
duckwork mcp add stalkchain --url https://data.stalkchain.com/mcp/directory --auth oauth --connect-timeout 300
```

Your browser opens the StalkChain sign-in page. Sign in with email or X and
approve access, then press Enter to keep all tools. To sign in again later, run
`duckwork mcp login stalkchain`.

In Duckwork Desktop: **Capabilities → Connectors → Add your own**, with name
`stalkchain`, type Streamable HTTP, URL `https://data.stalkchain.com/mcp/directory`
and auth OAuth. Save, then choose **Authenticate** on the StalkChain card.

Keep the name `stalkchain`, so your connection replaces the unauthenticated
server entry in the plugin.

Start a new session and try: "What are the top traders buying on Solana right now?"

Each tool call spends credits from your StalkChain account. StalkChain never
trades, moves funds or signs anything. More: https://github.com/StalkC/stalkchain-plugin
