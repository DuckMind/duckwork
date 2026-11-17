# MCP and provider integration

Duckwork SEO preserves workflows that can use SEO providers, but it does not ship a universal provider configuration. MCP server commands, transport, permissions, authentication, and billing differ by provider and can change. Configure each server under `mcp_servers` in the active Duckwork profile's `~/.duckwork/config.yaml` (or use `duckwork config edit`) and follow the provider's official setup guide. Store secrets in Duckwork' configured secret mechanism; never commit them here.

## Provider families

| Provider | Workflow area | Notes |
|---|---|---|
| DataForSEO | SERP, keywords, backlinks, listings, AI visibility | Paid endpoints; confirm estimated spend before each operation. |
| Ahrefs | Backlinks and keyword metrics | Requires compatible MCP server and account access. |
| Firecrawl | Site map, crawl, and extraction | Crawls can consume credits and transmit target URLs/content to the service. |
| Banana | Image generation | Requires compatible MCP and API key; generation may incur cost. |
| SE Ranking | Search and AI visibility | Requires provider access and API plan. |
| Profound | LLM citation tracking | Requires provider API key and plan. |
| Bing Webmaster | Search performance and IndexNow | IndexNow submission changes public indexing state. |
| Matomo | Analytics reporting | Requires a reachable instance and read-scoped token. Private targets remain subject to URL safety controls. |
| Unlighthouse | Local multi-page Lighthouse | Requires Node/npm and browser/package dependencies; it is not an MCP provider. |
| PageSpeed Insights | Lighthouse and CrUX data | No PageSpeed MCP server is configured by this fork; use a Duckwork-compatible integration and current Google documentation if needed. |

The extension docs describe retained scripts and source-provider assumptions. They are not installers: old scripts that edited Claude Code configuration were removed, and old Claude settings examples are historical only. A configured Duckwork server's actual tool names should be checked with Duckwork before invoking a workflow.

## Safe operation

Plugin discovery and local validation make no provider calls. No provider credential or compatibility is implied by the presence of an extension. Before paid calls or external writes/submissions, obtain approval for the specific operation. If a provider is missing, continue only with the offline/free analysis available and state the missing data source.

Google API examples in the retained scripts pass credentials through the `X-Goog-Api-Key` request header. Do not put API keys in URL query parameters, where URLs can be retained by logs and intermediaries.
