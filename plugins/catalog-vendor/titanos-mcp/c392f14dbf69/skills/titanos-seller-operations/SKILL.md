---
name: titanos-seller-operations
description: Use when analyzing Amazon Seller Central inventory, orders, listings, reports, fees, pricing, finances, or account health through Titanos.
license: MIT
compatibility: Duckwork Agent Plugin v1 with Titanos MCP enabled.
---

# Titanos Seller Operations

Use live Titanos Selling Partner data for account-specific Amazon work. Keep every query scoped to one organization, connection, account, and marketplace.

## Workflow

1. Search once with the exact goal, `domain="amazon-seller"`, and the expected access type.
2. Execute `recommended_tool` directly with the schema returned by search; describe only another alternative.
3. Identify the Selling Partner integration and account only when the task does not already provide them.
4. Confirm marketplace; never silently merge BR, US, MX, or other accounts.
5. Reuse discovered tool schemas for follow-up calls in the same conversation.

## Read operations

- Inventory, inbound, reserved, and days of supply.
- Orders, sales trends, Buy Box, fees, finances, and reimbursements.
- Listings, pricing, catalog details, reports, and account health.
- Reorder analysis using user-provided lead time and safety stock.

## Write operations

Listing, price, inventory, fulfillment, or other account changes require the exact target and explicit user approval. Show the proposed payload and expected impact before calling a write tool.

## Pitfalls

- Account UUID is not the Amazon marketplace ID.
- FBA fulfillable stock alone may omit inbound and reserved units.
- Report data can lag; do not present incomplete periods as final.
- Reorder quantity is invalid without lead time and a safety-stock rule.
