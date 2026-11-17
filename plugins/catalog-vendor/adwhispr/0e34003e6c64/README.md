# AdWhispr for Duckwork Agent

Research what is working in any ad market, clone the winners for your own brand, and run the campaigns, all from Duckwork Agent. This portable Agent Plugins v1 package connects Duckwork to AdWhispr's hosted MCP server and bundles twenty-four workflow skills.

- **Research**: find the brands verified to be advertising in your niche right now, their longest-running Meta and TikTok ads, their Instagram content and creator partnerships, and real Google Keyword Planner data in about 180 countries.
- **Cloning**: turn a proven ad (a Meta ad, an Instagram reel, a TikTok, or your own video) into a finished image or a finished video with native AI voice, made for your brand and product. Every video script is shown for approval before any credit is charged.
- **Execution**: launch and manage campaigns on Meta (Facebook and Instagram), Google (Search and Performance Max), TikTok, X, and ChatGPT Ads. Every campaign is created paused.

## Install

After the plugin is accepted into the Duckwork catalog:

```bash
duckwork plugins install adwhispr --no-enable
duckwork plugins enable adwhispr
```

Until then, install directly from this repository:

```bash
duckwork plugins install adwhispr/adwhispr-duckwork-plugin --no-enable
duckwork plugins enable adwhispr
```

Start a new Duckwork session or run `/reload-mcp`. The first connection opens a browser for the AdWhispr sign-in (a free account works, no card); finish it and return to Duckwork. Connect ad accounts from chat when you need them: the agent sends you a link to each platform's own consent screen.

The plugin needs Node.js 20.18.1 or newer with `npx` on `PATH`. Duckwork launches the exactly pinned `mcp-remote@0.1.49` package as a local stdio-to-HTTP OAuth bridge; nothing is installed globally.

## Try it

- "Who has the best ads in my niche? My site is example.com."
- "Show me Gymshark's longest-running ads and what angles they use."
- "Clone their best video ad for my brand."
- "Turn this TikTok into an ad for my product: https://www.tiktok.com/@brand/video/123"
- "What's wasting money in my Google Ads account?"
- "Launch a Google Search campaign on these keywords at $20 a day."
- "Run my new video as a Meta ad against my two best images."

Load `adwhispr-get-started` for a first run, or `adwhispr-agent` for the safety contract and the map of which skill handles what. Duckwork namespaces portable skills under the installed plugin; use `skills_list` to find the qualified names.

## Safety contract

`plugin.json` marks the AdWhispr server `untrusted` for Duckwork (`extensions.com.fordex.duckwork.servers.adwhispr.trust`). Duckwork therefore asks you before every AdWhispr tool that is not annotated read-only, and refuses those tools in cron and headless runs. The research and read tools carry MCP `readOnlyHint: true` on the server, so they run without a prompt.

AdWhispr manages advertising accounts that can spend real money and makes videos that cost credits. The bundled skills require the agent to:

- create every campaign **paused**; nothing spends until the user resumes it;
- use the two-step **preview and confirm** on every launch, budget, targeting, keyword, and resume call (the server issues a single-use confirm token);
- render a video only after the user's latest message explicitly approves that script, quoting their words;
- never ask for passwords, tokens, or API keys in chat (ad accounts connect through browser links);
- never launch a competitor's media as the user's creative; clones keep the structure and make everything else new.

These rules are enforced by the AdWhispr server (paused creation, confirm tokens, the approval gate) and restated in the skills.

## Included components

- One stdio MCP entry backed by the hosted Streamable HTTP server at `https://adwhispr.com/api/mcp`
- Twenty-four research, cloning, and campaign skills
- OAuth 2.1 with PKCE and dynamic client registration
- An exact `mcp-remote@0.1.49` runtime pin; no bootstrap script, hook, native tool, or self-updater

## Included skills

| Skill | Purpose |
| --- | --- |
| `adwhispr-agent` | Safety contract and routing for every AdWhispr job: competitor ad research, ad cloning, and campaign execution on Meta, Google, TikTok, X and ChatGPT Ads |
| `adwhispr-brand-vs-brand` | Put two brands' ad strategies side by side: ad volume, longevity, format mix, and the angles each leans on |
| `adwhispr-budget-reallocation` | Move ad budget from losers to winners with evidence and explicit approval |
| `adwhispr-campaign-review` | Review the user's own ad campaign performance and manage running campaigns |
| `adwhispr-chatgpt-ads` | Launch and manage ChatGPT ads (OpenAI Ads) from chat: chat-card ads with context-hint targeting inside ChatGPT |
| `adwhispr-clone-image-ad` | Clone a competitor's winning image ad into a finished image for the user's brand, tweak it, and launch it as a paused Meta ad |
| `adwhispr-clone-video-ad` | Clone a winning video ad into a finished, ready-to-launch video for the user's brand, from a Meta ad, an Instagram reel, a TikTok link, or the user's own video, with a free script approval before any credit is charged |
| `adwhispr-clone-winning-ads` | Turn a competitor's proven ad into the user's own finished creative and get it live |
| `adwhispr-competitor-keyword-spy` | Find the Google keywords associated with a competitor's site and where the gaps are |
| `adwhispr-competitor-research` | Find which brands in the user's niche are running ads RIGHT NOW and surface their proven winners |
| `adwhispr-creative-fatigue-refresh` | Spot ad creatives that are wearing out and line up refreshed replacements |
| `adwhispr-get-started` | Introduce AdWhispr and get a new user to their first result in two minutes |
| `adwhispr-google-ads` | Launch and manage Google Ads from chat: Search campaigns with real keyword data, Performance Max, call ads, budgets and performance |
| `adwhispr-instagram-research` | Pull any public Instagram account's organic posts, paid partnerships and UGC creators, ranked by views, likes, comments or recency |
| `adwhispr-keyword-universe-builder` | Build a complete keyword universe for any product or topic with real Google Keyword Planner data in ~180 countries and 35 languages |
| `adwhispr-longest-running-ads` | Surface the ads a brand or niche has kept running the longest \u2014 the closest honest signal to a proven winner |
| `adwhispr-meta-ads` | Launch and manage Meta (Facebook and Instagram) ads from chat: single images, carousels, videos, creative tests, retargeting, and radius targeting |
| `adwhispr-new-ad-watch` | Watch a competitor for newly launched ads and what changed in their library |
| `adwhispr-niche-ad-report` | A full advertising report on any niche: who is verified to be running ads right now, how much, and what their proven winners look like |
| `adwhispr-tiktok-ads` | Launch and manage TikTok ads from chat, and clone proven TikTok ads into shoot-ready scripts |
| `adwhispr-video-from-script` | Make a finished video ad from the user's own script, or write an original concept from what is winning in their niche and render it |
| `adwhispr-wasted-spend-audit` | Audit the user's connected ad account for wasted spend: what is running, what is quietly burning budget, and the fixes ranked by dollars at stake |
| `adwhispr-winning-angle-extractor` | Extract the angles and offers behind a brand's longest-running ads, categorized into reusable patterns |
| `adwhispr-x-ads` | Launch and manage X (Twitter) ads from chat: promoted posts, creative tests, keyword and interest targeting, conversions |

## Authentication

`mcp.json` stores no credentials. On first connection the pinned `mcp-remote` bridge discovers AdWhispr's OAuth metadata, opens the browser sign-in, completes the PKCE exchange, and stores the tokens locally in `~/.mcp-auth/mcp-remote-0.1.49/`. To sign in again, remove only the AdWhispr entry from that directory and run `/reload-mcp`.

Why a bridge? Agent Plugins v1 has no portable field for OAuth on a remote MCP entry. Duckwork supports OAuth in its native MCP configuration, but the portable plugin translator cannot carry that setting yet, so the pinned bridge keeps installation to one command.

## Scheduled work

Duckwork can run recurring jobs with its `cronjob` tool, for example a Monday campaign review (`adwhispr-campaign-review`) or a weekly look at what a competitor launched (`adwhispr-new-ad-watch`). Scheduled runs use AdWhispr calls like an interactive session; weekly is a sensible default.

Scheduled runs are read-only. The plugin marks the AdWhispr server `untrusted` (see below), so Duckwork refuses every tool that can write or spend in a cron or headless run. A scheduled brief can report and recommend; launching, budget changes, resuming and video renders happen only in an interactive session where you approve them.

## Development

Validate the package with the same admission command the Duckwork catalog uses:

```bash
duckwork plugins validate .
```

## Support and security

- Website: [adwhispr.com](https://adwhispr.com/?utm_source=duckwork&utm_medium=plugin&utm_campaign=duckwork_plugin)
- Docs: [adwhispr.com/docs](https://adwhispr.com/docs?utm_source=duckwork&utm_medium=plugin&utm_campaign=duckwork_plugin)
- Issues: [GitHub Issues](https://github.com/DuckMind/duckwork)
- Security reports: [SECURITY.md](SECURITY.md)

Licensed under the [MIT License](LICENSE).
