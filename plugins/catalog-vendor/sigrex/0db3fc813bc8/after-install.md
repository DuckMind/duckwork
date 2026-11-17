# Sigrex is installed

Two steps are left before the Sigrex tools appear.

**1. Enable the plugin**

```bash
duckwork plugins enable sigrex
```

**2. Connect your Sigrex account**

```bash
duckwork mcp add sigrex --url https://mcp.sigrex.io --auth oauth --connect-timeout 300
```

Your browser opens the Sigrex sign-in page. Sign in and approve access, then
press Enter to keep all tools. To sign in again later, run
`duckwork mcp login sigrex`.

In Duckwork Desktop: **Capabilities → Connectors → Add your own**, with name
`sigrex`, type Streamable HTTP, URL `https://mcp.sigrex.io` and auth OAuth.
Save, then choose **Authenticate** on the Sigrex card.

Start a new session and try: "Show me my active Sigrex strategies."

The connection has full access to your Sigrex account, including actions that
can place live trades. More: https://github.com/sigrexio/agent-plugin