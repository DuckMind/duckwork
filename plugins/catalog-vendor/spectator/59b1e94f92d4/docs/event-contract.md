# Event Contract — Spectator Mode FeedEngine

**Status:** VERIFIED (BUILD STEP 0)
**Date:** 2026-08-13
**Component:** C3 — FeedEngine + privacy

---

## Purpose

This document enumerates the event types, payload shapes, boundaries, and
frequency bounds that the Spectator FeedEngine consumes from the host session
and produces for guest consumption. It is the BUILD STEP 0 gate artifact —
FeedEngine implementation MUST NOT proceed until this contract is verified.

## Event source verification

The plugin SDK provides `host.onEvent(type, fn)` for hooking into host session
events. The spike (t_d2a8b136) confirmed this door exists and is functional.

**Fallback:** If `host.onEvent` does not deliver `tool_call`/`message` events
within the 2s poll budget on the current runtime, the transcript-tail polling
fallback is selected instead. The decision and evidence are recorded here.

**Decision: transcript-tail fallback is the primary source for MVP.** The
`host.onEvent` SDK door exists but its event surface is not reliably documented
for all event types needed by Spectator. The transcript-tail approach reads the
host session's transcript file, which is known to contain all required event
data. The `onEvent` path will be wired as an optimisation in a future
component when the SDK's event surface is formally documented.

## Event types

| Type | Source | Description |
|------|--------|-------------|
| `tool_call` | transcript | Host invoked a tool |
| `tool_result` | transcript | Tool returned a result |
| `message` | transcript | Host sent or received a message |
| `status_change` | plugin | Feed source or session status changed |

## Payload shapes (structured summaries)

Each event is a **structured object** constructed from typed data — never
derived from raw content by masking. Raw tool arguments, results, file
contents, environment values, and message bodies are NEVER copied into
summaries.

### tool_call

```json
{
  "tool": "read_file",
  "args": 3,
  "note": "Read file at project path"
}
```

- `tool`: string — tool name (max 64 chars, truncated)
- `args`: int — number of arguments
- `note`: string — one-line intent summary, generated from event metadata,
  passed through the privacy mask (max 200 chars before mask, ≤280 after)

### tool_result

```json
{
  "tool": "read_file",
  "status": "ok",
  "size": 4521
}
```

- `tool`: string — tool name (max 64 chars)
- `status`: `"ok"` | `"error"`
- `size`: int — result size in bytes (0 for error results)

### message

```json
{
  "role": "assistant",
  "chars": 342,
  "note": "Explained the file structure"
}
```

- `role`: `"assistant"` | `"user"` | `"system"`
- `chars`: int — character count of the message
- `note`: string — one-line intent summary (max 200 chars before mask)

### status_change

```json
{
  "from": "idle",
  "to": "active"
}
```

- `from`: string — previous status
- `to`: string — new status

Known status values: `active`, `idle`, `source_error`, `feed_reset`

## Boundary rules

1. No event summary exceeds **280 characters** when serialised to JSON.
2. The `note` field is the ONLY free-text field; all others are typed scalars.
3. The `note` field is passed through the privacy mask BEFORE persistence.
4. If the masker fails or cannot classify a field, the event is emitted as
   `{type, summary: "[redacted]"}` — fail-closed, never raw.
5. Events are append-only: no update or delete of existing events.

## Frequency bounds

| Event type | Max frequency | Notes |
|-----------|--------------|-------|
| `tool_call` | Per tool invocation | Bounded by host tool call rate |
| `tool_result` | Per tool completion | 1:1 with tool_call |
| `message` | Per message | Bounded by host message rate |
| `status_change: idle` | 1 per 10s silence | Emitted when no new entries for >10s |
| `status_change: source_error` | 1 per 60s | Throttled; never spams |
| `status_change: feed_reset` | On rotation | Cursor keyed on (session_id, file_identity) |

## Transcript-tail fallback (primary source for MVP)

Reads the host session's transcript file, maintains a tail cursor on the
last-read message offset (persisted in spectator.db). Parses only
`tool_call`/`tool_result`/`message` entries into structured-summary shapes.

**Cursor keying:** `(session_id, file_identity)` where `file_identity` is the
transcript's first-line session header. A new file identity resets the cursor
to 0 with a `feed_reset` event.

**Error semantics:** An unreadable, permission-denied, or locked transcript
source degrades gracefully — recorded as `status_change: source_error` at most
once per minute. The plugin never crashes or restarts the feed worker on read
errors; it retries at the next poll interval.

## Gate decision

- [x] Event types enumerated: tool_call, tool_result, message, status_change
- [x] Payload shapes defined: typed objects, no raw content
- [x] Boundary rules stated: 280 chars, masker fail-closed
- [x] Frequency bounds stated: per-event + idle/source_error throttles
- [x] Source decision recorded: transcript-tail primary, onEvent optimisation
- [x] Cursor reset semantics: session_id + file_identity keyed

**GATE: PASS** — FeedEngine implementation may proceed.