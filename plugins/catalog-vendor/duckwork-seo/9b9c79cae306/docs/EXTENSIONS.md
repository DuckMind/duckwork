# Optional integrations

The source fork includes nine optional extension packages. Their SEO prompts and scripts remain bundled, but the old installers edited Claude Code settings and are not shipped as Duckwork setup flows. Configure a server through Duckwork `mcp_servers` or install the provider's Duckwork-compatible plugin separately. Exact server command, permissions, credentials, and cost depend on the provider account; local tests do not validate those services.

| Extension | Preserved capability | External dependency / limit |
|---|---|---|
| DataForSEO | SERP, keyword, backlink, listing, and AI visibility workflows; cost ledger utilities | DataForSEO MCP/account; paid endpoints must be approved per operation |
| Banana | SEO image generation prompts and helper scripts | Banana-compatible MCP and API key; generation may incur cost |
| Firecrawl | Site map/crawl workflow | Firecrawl MCP and account; crawl limits and billing depend on plan |
| Ahrefs | Backlink and keyword workflow | Ahrefs-compatible MCP and account/subscription |
| SE Ranking | AI share-of-voice workflow | SE Ranking API key and plan |
| Profound | LLM citation tracking workflow | Profound API key and plan |
| Bing Webmaster | Direct Bing Webmaster and IndexNow scripts | Site ownership and API credentials; IndexNow submission changes public indexing state |
| Matomo | Reporting API scripts and token setup helper | Reachable Matomo URL and read access token; private hosts require the explicit local-target allowlist |
| Unlighthouse | Multi-page Lighthouse run helper | Node/npm and its package/browser dependencies; no provider API verification performed |

Only the 26 core workflow skills and 19 role skills under `skills/` are registered with Duckwork `skill_view`. Provider files under `extensions/*/skills/` are companion references, not hub-discovered skills; inspect them with `duckwork seo show extensions/<provider>/skills/<skill>/SKILL.md` or use the registered core workflow instead. Optional provider commands live in the extension setup guides; only Banana currently has extension-specific helper scripts, invoked with `duckwork seo run --extension banana <script.py>`.

Configure MCP servers in the active Duckwork profile's `~/.duckwork/config.yaml` under `mcp_servers` (or edit it with `duckwork config edit`). Use each provider's current official setup guide for its command, transport, permissions, and authentication. Keep credentials in Duckwork' secret/config mechanism. Before invoking a paid or externally mutating endpoint, obtain user approval for the specific operation. Where no compatible MCP is configured, use the bundled offline or free-script analysis and report the missing data source.

## What has been checked

Bundled source files, runtime allowlisting, and offline tests are locally inspectable. No provider credentials are present in this repository. No live DataForSEO, Google, Bing, Matomo, Firecrawl, Ahrefs, SE Ranking, Profound, Banana, or Unlighthouse service call has been made; provider compatibility is therefore unverified.
