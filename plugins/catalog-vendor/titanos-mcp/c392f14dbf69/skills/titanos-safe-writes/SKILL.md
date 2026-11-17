---
name: titanos-safe-writes
description: Use when a Titanos MCP request can create, update, pause, delete, submit, publish, spend, refund, or otherwise change external state.
license: MIT
compatibility: Duckwork Agent Plugin v1 with Titanos MCP enabled.
---

# Titanos Safe Writes

A Titanos write is an external side effect. Keep one active owner, make the proposed change reviewable, and verify the resulting state.

## Required sequence

1. Read the current target and capture stable identifiers.
2. Describe the exact mutation: organization/account, resource, fields, old values, and new values.
3. Explain material impact: spend, visibility, inventory, customer, billing, or reversibility.
4. Obtain explicit approval for that exact payload.
5. Execute once, then read the exact target back before claiming success.

## Approval boundary

A request to analyze, audit, recommend, draft, or preview is not permission to write. If the tool supports `dry_run`, use it before approval when it does not itself create state.

## Safety rules

- Do not retry a possibly successful non-idempotent write blindly.
- Use idempotency keys when the tool supports them.
- Prefer small, reversible batches over account-wide changes.
- Never run production database migrations or `db:push` through this workflow.
- Stop on tenant/account ambiguity, stale state, unexpected schema, or mismatched totals.
- For destructive or financial changes, include a rollback or containment plan.

## Completion evidence

Report the tool result plus the read-back state. If read-back is unavailable, say the write was accepted but not independently verified.
