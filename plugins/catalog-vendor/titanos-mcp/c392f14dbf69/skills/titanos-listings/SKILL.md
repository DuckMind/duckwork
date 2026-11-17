---
name: titanos-listings
description: Use when generating, auditing, diagnosing, or updating Amazon listings and marketplace product content with Titanos.
license: MIT
compatibility: Duckwork Agent Plugin v1 with Titanos MCP enabled.
---

# Titanos Listings

Use Titanos for listing generation and live catalog diagnostics. Base recommendations on the actual listing, marketplace, product facts, and policy constraints.

## Choose the path

- Generate content: discover tools in `domain="titanos-ai"`.
- Audit Amazon catalog/listings: discover tools in `domain="amazon-seller"` or `domain="amazon-content"`.
- Investigate a conversion drop: inspect price, stock, Buy Box, catalog changes, and listing quality before blaming Ads.

## Workflow

1. Search once in the matching domain (`titanos-ai`, `amazon-seller`, or `amazon-content`) with the exact user goal.
2. Execute `recommended_tool` directly using the returned schema. Describe only a different alternative that lacks a schema.
3. Fetch the current listing when auditing or rewriting.
4. Preserve verified product facts; never invent claims, certifications, materials, dimensions, or compatibility.
5. For generated jobs, poll the returned result through the MCP rather than guessing completion.

## Safe output

For proposed edits, show current text, replacement text, reason, and affected SKU/ASIN. Do not apply listing updates without explicit approval for the exact changes.

## Common risks

- Prohibited or unsupported claims.
- Hijacked or unexpectedly changed content.
- Missing required attributes or variation errors.
- Weak titles/bullets that omit fit, differentiation, or use cases.
- Ad spend directed to unavailable or unhealthy listings.
