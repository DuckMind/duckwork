![HYPD: manage paid media safely with AI](assets/banner.png)

# HYPD AI: Paid Ads & Analytics for Duckwork

Read-only paid-media analysis in plain language for **Google Ads, Meta (Facebook) Ads, Microsoft Ads, LinkedIn Ads, Google Analytics (GA4), Search Console and Merchant Center**, plus keyword and competitor research and landing-page checks.

**Read-only.** HYPD reports on your accounts and never changes your campaigns, budgets or ads.

## Install

```
duckwork plugins install hypd-ai-ads
```

Or straight from this repository:

```
duckwork plugins install HYPD-AI/hypd-duckwork-plugin
```

Then start a new session. On the first HYPD tool call, a browser window opens to sign in to HYPD.

### Requirements

- A HYPD account: sign up at [app.hypd.ai](https://app.hypd.ai) and connect at least one ad account on the **Sources** page.
- **Node.js 20.18.1 or newer with npm.** The plugin's connector runs a pinned [`mcp-remote@0.1.49`](https://www.npmjs.com/package/mcp-remote) through `npx`, which handles the HYPD sign-in.

### Without Node

Add HYPD as a native MCP server instead. Duckwork then signs in without the connector:

```
duckwork mcp add hypd --url https://mcp.hypd.ai/mcp --auth oauth
```

## What's included

| Skill | What it does |
|---|---|
| `hypd-getting-started` | Connect HYPD and your ad accounts; fixes for sign-in problems |
| `hypd-tools` | How HYPD's tools work and the rules they enforce |
| `hypd-overview` | What HYPD can do and typical questions |
| `hypd-workflows` | Ready-made analyses: account audit, wasted spend, negative keywords, keyword research, performance-drop diagnosis, monthly client report, Merchant Center feed checks, Meta diagnosis, creative and competitor analysis, landing-page audit |

Try: *"Audit my Google Ads account"*, *"Where am I wasting spend?"*, *"Why did performance drop last week?"*

## Security and data

- **Network endpoints.** `npx` downloads the pinned `mcp-remote@0.1.49` from the npm registry on first run. After that the only destination is HYPD's own server, `https://mcp.hypd.ai` (MCP endpoint `/mcp`, plus OAuth `/authorize`, `/token` and `/register`).
- **Credentials.** OAuth 2.1 with PKCE in your browser. No API keys, and nothing to put in `.env`. `mcp-remote` stores its tokens in `~/.mcp-auth` on your machine. Your ad-platform credentials stay with HYPD and never pass through the plugin.
- **Read-only.** No tool creates, edits, pauses or deletes anything in any connected platform.
- **No telemetry from the plugin.** The plugin adds no hooks, scripts or analytics of its own. HYPD's server processes your tool calls to answer them, as described in the [Privacy Policy](https://www.hypd.ai/privacy).

Report security issues privately: see [SECURITY.md](SECURITY.md).

## Links

[Website](https://www.hypd.ai) · [Dashboard](https://app.hypd.ai) · [Documentation](https://docs.hypd.ai) · [Privacy Policy](https://www.hypd.ai/privacy) · [Terms](https://www.hypd.ai/terms) · Support: [contact@hypd.ai](mailto:contact@hypd.ai)

## License

MIT
