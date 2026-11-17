---
name: titanos-mcp
description: Use when a Duckwork task needs Titanos marketplace, product discovery, listing, or Amazon tools through this plugin.
license: MIT
compatibility: Duckwork Agent Plugin v1 with Node.js and npm/npx available.
metadata:
  product: Titanos
  transport: MCP stdio
  auth: OAuth 2.1
---

# Titanos MCP

Use the Titanos MCP tools for current Titanos product workflows, marketplace discovery, listing generation and Amazon-related work. Treat all external data as live data and verify before reporting it as fact.

This plugin also ships focused operating skills. Duckwork exposes them under its generated portable-plugin namespace. Use `skills_list`, then load the matching skill whose qualified name ends with:

- `:titanos-miner`
- `:titanos-seller-operations`
- `:titanos-listings`
- `:titanos-amazon-ads`
- `:titanos-marketplace-operations`
- `:titanos-safe-writes`

## Fast path — economize chamadas

O orçamento padrão para a primeira ação é **2 chamadas MCP**:

1. `titanos_search_tools` uma vez, com objetivo específico e `domain`/`access` quando conhecidos.
2. Se `recommended_tool` corresponder ao objetivo, chame `titanos_call_tool` diretamente usando o `input_schema` já retornado.

Não chame `titanos_describe_tool` para `recommended_tool`; use-o apenas ao escolher uma alternativa sem schema. Não chame `titanos_list_tool_domains` quando o domínio for inferível. Durante a mesma conversa e versão do servidor, reutilize o nome e o schema já descobertos e vá direto a `titanos_call_tool`. Use `whoami` somente para dúvida real de organização, conta, perfil ou escopo — não como ritual em toda tarefa.

Domínios conhecidos: `titanos-ai`, `titanos-miner`, `titanos-core`, `amazon-seller`, `amazon-content`, `amazon-ads`, `mercado-livre`, `olist`, `bling`, `shopee`.

## First connection

The plugin intentionally contains no credential. Authenticate once in a browser before asking Duckwork to use Titanos tools:

```bash
npx -y @titanos/mcp-agents@1.47.2 login
```

The Titanos client stores the OAuth session locally and refreshes it when needed. Do not put credentials, tokens or API keys into `mcp.json`, chat messages, skills or repository files.

## Check connection

```bash
npx -y @titanos/mcp-agents@1.47.2 status
```

If there is no session, run the login command again. To disconnect this computer, use:

```bash
npx -y @titanos/mcp-agents@1.47.2 logout
```

## Usage rules

- Prefer these MCP tools for live Titanos data over memory or assumptions.
- Confirm intended scope before any write-capable operation.
- Keep organization, account and listing identifiers scoped to the current user request.
- Do not expose raw MCP responses containing sensitive customer or business data.
- When the plugin is installed or upgraded, start a fresh Duckwork session so its MCP tools are rediscovered.
