---
name: lights
description: Use when discovering or controlling Govee lights.
---
<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->

# Govee lights

Use `govee_lights` in the `govee` toolset. Find it with tool_search if hidden.

- `list`: discover lights, names, exact IDs and supported capabilities.
- `state`, `scenes`: pass `device` as an exact ID or unambiguous name.
- `power`: boolean `value`.
- `brightness`: integer percent in the device's advertised range.
- `color`: `#RRGGBB` string.
- `temperature`: integer Kelvin in the device's advertised range.
- `scene`: exact scene name returned by `scenes`; static and dynamic scenes are combined.

Only change the lights requested. Do not guess targets from substrings or silently apply a change to every light. A clear request authorizes its bounded change without another approval. No unsolicited schedules or test flashes.

Capabilities and ranges differ by model; never hardcode them. Scene values can be integers or structured objects with `id` and `paramId`; the tool preserves the returned value exactly.

Commands perform a state read-back automatically. `accepted: true` means Govee accepted the command. Say it changed only if `verified: true`. Cloud state may lag or omit the scene; state read-back is not visual proof. When verification fails, report that honestly and do not blindly repeat the command. State and scene limits are 30 requests/minute/device. Do not run rapid polling or effects through the cloud API. On a rate limit, stop and wait rather than retrying.

`GOVEE_API_KEY` resolves through Duckwork' secret lookup. Never ask for the key in chat, print it, or put it in tool arguments. If it is missing or rejected, ask the user to save a new key through Duckwork' secure secret entry (a secure input prompt where the client offers one, or `duckwork config set GOVEE_API_KEY` on the host).
