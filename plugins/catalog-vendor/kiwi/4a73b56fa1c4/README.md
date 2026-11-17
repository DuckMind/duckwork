<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# duckwork-plugin-kiwi

Source suppliers and negotiate purchases from Duckwork Agent through
[Kiwi](https://github.com/harrylabsj/kiwi)'s buyer MCP server — an open-source
A2A commerce runtime for supplier discovery, RFQ fan-out, negotiation,
non-binding agreements and trade handoff. Kiwi never handles payments and
never places orders.

Sourcing searches are **dual-source**: Kiwi Network results come from
`kiwi_search`, and — when the session has web search / page-reading tools
enabled — the skill also reports internet e-commerce listings as a separate,
labelled section. The internet path is a host capability, not a guarantee of
this plugin: when those tools are unavailable the skill says the internet side
was not searched instead of implying it was.

This is a portable [Agent Plugins v1](https://agent-plugins.org) package. One
install ships:

- `mcp.json` — the Kiwi Buyer MCP server entry (`kb`), registered for every
  new session while the plugin is enabled. No `mcp_servers` edits in
  config.yaml.
- `skills/kiwi-buyer/` — the sourcing workflow skill: when to use which tool,
  the search → RFQ → negotiate → agreement → handoff loop, dual-source rules
  (source separation, `network_search` query status, price kinds, the ban on
  sending internet listings into an RFQ), CommerceIntent rules, and the
  authorization/error-handling contract. English is the default and
  authoritative version ([SKILL.md](skills/kiwi-buyer/SKILL.md)); a Chinese
  translation ships as [SKILL.zh-CN.md](skills/kiwi-buyer/SKILL.zh-CN.md).

## Install

```bash
duckwork plugins install kiwi       # from the Fordex plugin catalog
duckwork plugins enable kiwi
```

Alternatively, install straight from this repo:

```bash
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable kiwi
```

Then start a new Duckwork session. The skill is available via `skill_view`
(`skills_list` shows the exact `agent-plugin-kiwi-…` name). Node.js/npm must
be on `PATH` (the server is launched with `npx -y @harrylabsj/kiwi@0.12.5 mcp
serve`). The first launch downloads the pinned package.

Health check without Duckwork:

```bash
npx -y @harrylabsj/kiwi@0.12.5 mcp serve <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}
EOF
```

## What you get

The pinned runtime (`@harrylabsj/kiwi@0.12.5`) exposes 13 tools: `kiwi_search`
(supplier discovery, Kiwi Network only), `kiwi_request_quotes` (RFQ),
`kiwi_get_task`, `kiwi_negotiate`, `kiwi_accept_agreement`, `kiwi_get_agreement`,
`kiwi_handoff`, the `kiwi_approve` / `kiwi_reject` approval gates, and the
merchant pull-subscription tools (`kiwi_follow_merchant` /
`kiwi_unfollow_merchant` / `kiwi_list_follows` / `kiwi_get_follow_updates`).
The tool set always follows the pinned version, not this README.

Duckwork exposes them as `mcp__kb__<tool>` (the server key is `kb`; Duckwork does
not namespace MCP tools by plugin).

## How it works

- The buyer discovers merchants through the public Kiwi catalog
  (`https://catalog.kiwi.harrylabsj.com`, built-in default) and then talks to
  merchants directly over A2A. No local marketplace daemon required.
- `kiwi_accept_agreement` and `kiwi_handoff` default to **ask** — the agent
  must show you candidate, terms and amount, and only proceeds after your
  explicit confirmation (`kiwi_approve`). The built-in policy sets payment to
  **never**; Kiwi produces a handoff entry (checkout/PO/contact), it does not
  pay or order.
- State lives in a local SQLite store (default `~/.kiwi/mcp/dsh.sqlite`, HOME
  based). Override with `KIWI_MCP_DB`, `KIWI_PRINCIPAL`, `KIWI_BUYER_AGENT`
  environment variables if needed. No credentials are required at install
  time.

## Version pinning

`mcp.json` pins `@harrylabsj/kiwi@0.12.5`. Bumping the pin is a commit to this
repo followed by a reviewed SHA bump in the
[duckwork-agent plugin catalog](https://github.com/DuckMind/duckwork).
`@latest` is deliberately not used.

## Attribution

Kiwi and the Kiwi Buyer MCP server are part of the open-source
[harrylabsj/kiwi](https://github.com/harrylabsj/kiwi) project (Apache-2.0).
This packaging plugin is Apache-2.0 as well.
