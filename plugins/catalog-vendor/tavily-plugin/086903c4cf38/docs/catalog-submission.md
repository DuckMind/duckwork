# Catalog submission

A Tavily owner or major contributor submits a PR to `Fordex/duckwork-agent`.
Fordex maintainers review and merge the entry; there is no self-service publishing.

Submission is paused while the repository remains internal. The submission
guide requires a public repository that anyone can clone; package validation
does not satisfy that publication prerequisite.

1. Run package tests and `duckwork plugins validate /path/to/plugin --install-deps`.
2. Push the reviewed package commit and resolve its full 40-character SHA.
3. In a separate Duckwork branch, add `plugin-catalog/tavily-plugin.yaml` using the
   metadata below and the **real pushed SHA**. Never submit a branch, tag,
   short SHA, or placeholder.
4. Run Duckwork's catalog schema check and plugin validation at that exact commit.
   Review every scanner warning.
5. Include the disclosures below and verification evidence in the PR. Request
   vendor verification in prose; only Fordex maintainers set `tier: verified`.

```yaml
name: tavily-plugin
title: Tavily
repo: https://github.com/DuckMind/duckwork
# sha: insert the reviewed, pushed 40-character commit SHA
description: Web search, extraction, mapping, crawling, and research through Tavily MCP, with Tavily skills.
maintainer: tavily-ai
tier: community
category: web
requires_duckwork: ">=0.22.2"
docs_url: https://github.com/DuckMind/duckwork
version: "1.0.0"
platforms: []
capabilities:
  provides_tools: []
  provides_hooks: []
  provides_middleware: []
  requires_env: [TAVILY_API_KEY]
```

For the catalog card, set the optional `image` field to the GitHub-hosted HTTPS
URL for `assets/tavily-catalog-card.svg` at the **same full commit SHA** as the
entry. This 1200×600 (2:1) SVG centers the official Tavily by Nebius logo on a
white background, preserving its proportions and keeping it readable in either
theme. It contains no added branding or text. The supplied originals are
preserved unchanged in `assets/tavilybynebius-logo-black.svg` (wordmark) and
`assets/tavily-logo.svg` (square mark). No PNG conversion is required.

The tool, hook, and middleware lists are empty because the package does not
register native Python capabilities. The default MCP connection requires
`TAVILY_API_KEY`, so declare it in `requires_env`. Disclose the remotely
discovered tools and the recommended native OAuth setup explicitly. OAuth users
do not need an API key; the declaration describes the packaged fallback. Do not put
remote MCP tool names in the native `provides_tools` list.

## Disclosures for the PR

- Tavily-maintained portable package adapting Tavily skills from `tavily-ai/skills`;
  no fork of a Duckwork bundled provider.
- HTTPS requests to `mcp.tavily.com`; Tavily processes queries, URLs, and research
  instructions, using account credits.
- Fixed attribution: `X-Client-Name: duckwork plugin`.
- Recommended interactive setup uses Duckwork-managed OAuth. The portable package
  supplies API-key authentication when no native connection overrides it; the
  README and examples explicitly separate the two methods.
- No runtime dependencies, local executables, shell commands, background
  workers, credential-file reads, core overrides, or self-updater.
- Five remotely discovered tools and bundled Tavily skills; no Desktop renderer code.
- All bundled skills and the Best Practices references use the hosted MCP tools.
  There are no Tavily CLI or SDK installation commands or client programs.
- Research may take minutes; stable Duckwork needs the documented native timeout
  override for longer calls. The hosted service updates separately from this pin.
- Link capability coverage and identify the live calls, auth modes, and
  attribution checks that were actually tested.

Updates require a new SHA-bump PR and review of the commit range. Keep the
manifest version and catalog label aligned and the SemVer floor truthful.

See the authoritative [catalog policy](https://duckwork-agent.fordex.com/docs/developer-guide/plugins/catalog-submission).
