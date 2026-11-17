---
name: hypd-getting-started
description: Connect HYPD and the user's ad accounts. Use when HYPD is not connected yet, a HYPD tool returns an authentication or connection error, no accounts come back, or the user asks how to set up or start using HYPD.
---

# Getting started with HYPD

1. **Create a HYPD account** at https://app.hypd.ai (no card needed to start).
2. **Connect at least one source** on the Sources page (https://app.hypd.ai/sources): Google Ads, Meta, Microsoft Ads, LinkedIn Ads, Google Analytics, Search Console or Merchant Center.
3. **Sign in to HYPD from the agent.** On the first HYPD tool call, a browser window opens for HYPD sign-in. Approve it and the tools load. This plugin's connector runs through `npx`, so it needs **Node.js 20.18.1 or newer** with npm.
4. **Verify** by asking: "List my Google Ads accounts."

## If something goes wrong

- **No browser opened, or the connector fails to start:** check `node --version` (20.18.1 or newer) and that `npx` is on the PATH, then start a new session.
- **Node is not an option:** add HYPD as a native MCP server instead, which signs in without Node:

  ```
  duckwork mcp add hypd --url https://mcp.hypd.ai/mcp --auth oauth
  ```

- **Signed in but no accounts:** the HYPD account has no connected source yet. Connect one at https://app.hypd.ai/sources, then ask again.

Help: contact@hypd.ai · Docs: https://docs.hypd.ai
