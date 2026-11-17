---
name: titanos-miner
description: Use when researching products, markets, keywords, reviews, competitors, CNPJ, NCM, or INPI with live Titanos data.
license: MIT
compatibility: Duckwork Agent Plugin v1 with Titanos MCP enabled.
---

# Titanos Miner

Use Titanos MCP as the source of truth for current marketplace research. Never invent demand, competition, keyword, tax, company, or trademark data.

## Workflow

1. Call `titanos_search_tools` once with the user goal, `domain="titanos-miner"`, a narrow `limit`, and `access="read"` when applicable.
2. If `recommended_tool` matches the goal, execute it directly with `titanos_call_tool`; its schema is already in the search result.
3. Use `titanos_describe_tool` only for a non-recommended alternative without a schema.
4. Reuse the selected tool name and schema for repeated queries in the same conversation.
5. Separate facts returned by Titanos from interpretation and recommendations.

## Common jobs

- Product and category discovery: demand, competition, price bands, top sellers.
- Keyword research: expansion, ranking, reverse ASIN, SERP.
- Review mining: recurring praise, complaints, objections, and opportunities.
- Brazilian due diligence: CNPJ, NCM/tax, and INPI brand searches.
- Private-label assessment: entry signals, differentiation, and margin risks.

## Guardrails

- Do not claim profitability without costs, fees, taxes, and logistics inputs.
- Do not treat estimated marketplace signals as audited sales.
- Ask for the target marketplace when it changes the query.
- Prefer generic, importable, non-regulated opportunities unless the user asks otherwise.
- For an unavailable typed tool, use Titanos discovery tools; do not substitute stale memory.
