---
name: seo-seranking
description: SE Ranking AI visibility analyst (extension). Tracks AI Share-of-Voice across ChatGPT, Gemini, Perplexity, AI Overviews, and AI Mode in a single query.
metadata:
  version: "2.4.2"
compatibility: "Requires an SE Ranking API key (set SERANKING_API_KEY by running Duckwork plugin/provider setup)."
---

# seo-seranking

Live AI visibility tracking via the SE Ranking REST API.

## Prerequisites

- An SE Ranking API key (https://seranking.com/api.html), stored in Duckwork-managed environment/secrets.
- This extension file is an optional companion reference, not a registered skill.

## Routing

Ask the registered `duckwork-seo:seo-geo` workflow to assess AI visibility using a compatible SE Ranking MCP configured in Duckwork. Use the registered `duckwork-seo:seo-dataforseo` workflow for SERP/backlink/competitor research when its provider tools are available. No `duckwork-seo:seo seranking` CLI command is provided.

## AI Share-of-Voice scoring

SE Ranking samples each AI platform's responses for brand mentions
across a configurable prompt set. The scorer is the same logic used
by Profound / Peec AI but bundled into one MCP/API. Output fields:

- `chatgpt_sov`: % of sampled prompts where the brand appears in the response.
- `gemini_sov`: same, against Google Gemini.
- `perplexity_sov`: same, against Perplexity.
- `ai_overviews_sov`: brand citation rate inside Google AI Overviews.
- `ai_mode_sov`: brand citation rate inside Google AI Mode (US English first).

Report each as a percentage with a confidence note based on sample size.

## Cost guardrails

SE Ranking API uses unit accounting. Single AI visibility query is
~5 units (1 per platform). Use `duckwork seo run dataforseo_costs.py` to log
spend across vendors.

## Cross-skill delegation

- For traditional backlinks + content audit, fall back to `seo-backlinks` / `seo-content`.
- For platform-specific deep-dives (ChatGPT only, Perplexity only), prefer the dedicated `seo-geo` skill which has Brand Mention Correlation guidance.
