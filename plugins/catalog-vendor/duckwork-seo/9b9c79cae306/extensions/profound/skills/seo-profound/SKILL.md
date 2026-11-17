---
name: seo-profound
description: Profound LLM citation tracker (extension). Time-series brand citation rates across ChatGPT, Perplexity, and other LLMs. Pairs with seo-seranking for triangulated AI visibility coverage.
metadata:
  version: "2.4.2"
compatibility: "Requires a Profound API key (set PROFOUND_API_KEY by running Duckwork plugin/provider setup)."
---

# seo-profound

Profound is purpose-built for LLM brand-mention tracking. While
SE Ranking samples prompts on demand, Profound continuously polls and
publishes time-series so trend deltas (week-over-week, month-over-month)
are first-class.

## Prerequisites

- Profound API key, stored in Duckwork-managed environment/secrets.
- This extension file is an optional companion reference, not a registered skill.

## Routing

Ask the registered `duckwork-seo:seo-geo` workflow to assess citation trends using a compatible Profound MCP configured in Duckwork. There is no provider-specific `duckwork-seo:seo profound` CLI command.

## Output conventions

- Cite Profound on every metric: "Profound (live, confidence 0.90)".
- Profound covers ChatGPT + Perplexity natively; for Gemini / AI
  Overviews / AI Mode coverage, defer to `seo-seranking`.
- For Google AI Overviews citation rate, also cross-reference
  `seo-dataforseo` AI visibility tools when available.

## Cross-skill delegation

- For end-to-end AI search audit (passage citability + brand mentions + platform-specific tuning), hand back to `seo-geo`.
- For prompt-set design + AI Cleanup pattern detection in cited content, fall back to `seo-content`.
