# Setup: connecting Mnemoverse memory

This plugin declares a hosted MCP server at `https://mcp.mnemoverse.com/mcp`. Authentication is a one-time browser sign-in (OAuth 2.1 with PKCE); no API key is pasted anywhere.

Steps Claude should follow when the user installs or activates this plugin:

1. Check the available tools. If `memory_read`, `memory_write` and `memory_stats` are present, the connection already works; say so and stop.
2. If the tools are missing, the user needs a Mnemoverse account: free tier at https://console.mnemoverse.com, no credit card. Installing the plugin does not open a browser, and Claude Code does not start the sign-in by itself. Ask the user to run `/mcp`, select the Mnemoverse server (from this plugin it is listed as `plugin:mnemoverse:mnemoverse`) and choose Authenticate, then complete the sign-in in the browser and grant the requested scopes, which include `memory:read` and `memory:write`.
3. If the server is not listed in `/mcp`, have the user add it for all their projects: `claude mcp add --transport http --scope user mnemoverse https://mcp.mnemoverse.com/mcp`, then authenticate from `/mcp` as in step 2. Without `--scope user` the server is added for the current project only.
4. If a call fails after it used to work, the token has usually expired; the next call refreshes it. If it does not, have the user run `/mcp`, select the server and choose Re-authenticate.

Detailed rules live in the bundled `setup` skill. Never store secrets, API keys, passwords, payment data, or personal identifiers in memory.
