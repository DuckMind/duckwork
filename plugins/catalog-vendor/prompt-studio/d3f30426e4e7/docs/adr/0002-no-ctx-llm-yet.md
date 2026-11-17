# 0002. Model calls go through the auxiliary client, not `ctx.llm`, for now

Status: Accepted (2026-10-02)

## Context

The backend needs a model call with a reasoning effort, with the model the user picked in Settings for this call, and
with credentials resolved by Duckwork. In Duckwork 0.21.5 the public `ctx.llm.complete()` has no reasoning-effort option and
denies a per-call `model=` unless the operator sets `plugins.entries.prompt-studio.llm.allow_model_override`. Duckwork's
auxiliary client takes those and resolves provider and credentials.

## Decision

The backend delegates provider calls and credential resolution to Duckwork's auxiliary client, routed by the plugin's own
auxiliary task `prompt_studio` (config block `auxiliary.prompt_studio`; with no provider or model pinned it follows the
main model). It does not use `ctx.llm`. The plugin asks for no API keys and stores none.

## Consequences

- The questions model and the context model chosen in Settings work on a default install, with no operator switch.
- The backend depends on Duckwork-internal signatures. They are imported in one host module that checks them, which
  answers `host_incompatible` when Duckwork changed; a contract test runs against the installed Duckwork
  (`tests/test_duckwork_host_contract.py`) after every Duckwork update.
- The public API is not used for model calls; this is a known deviation, kept until the gap above closes.

Revisit with every Duckwork release: switch when `ctx.llm` gains a reasoning-effort option and accepts a per-call model
without an operator opt-in.
