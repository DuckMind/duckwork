# Firecrawl extension

The retained Firecrawl workflow material covers site mapping, crawling, and page extraction. This fork does not install an MCP package or configure provider credentials. Configure a compatible Firecrawl MCP server in Duckwork using [current provider documentation](https://docs.firecrawl.dev/) and store its API key in Duckwork' secret/config mechanism.

Confirm the expected tools are available in Duckwork before asking for a crawl. Crawling sends target URLs/content to the provider and may consume credits. Check current plan limits and obtain approval for the specific crawl. Local script alternatives, when available, can be run with `duckwork seo run <script.py>`.

The original source repository was [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo); that link records provenance and is not a Duckwork installer.
