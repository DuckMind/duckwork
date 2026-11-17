<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Changelog

All notable changes to lumberroom-duckwork. The format follows Keep a Changelog, and versions follow
semantic versioning.

## [Unreleased]

## [1.0.2] - 2026-09-26

### Fixed

- **`duckwork lumberroom login` prints the sign-in URL at once when stdout is a pipe or a file.**
  Duckwork v2026.9.21 leaves a piped stdout block-buffered, so the URL sat in the buffer while login
  waited for the browser or a paste, and a script driving the login never saw it. A terminal was
  never affected. Every sign-in line now flushes. Later Duckwork releases line-buffer a piped stdout
  themselves.
- **The end-to-end gate runs against Duckwork v2026.9.21 as well as main.** The driver passed
  `profile_home` to `set_secret_scope`, which v2026.9.21 does not take; it now checks the signature
  first. The missing `context_bootstrap` row in that failing run came from the same crash: recall
  never ran. The digest reaches the engine on both releases.

## [1.0.1] - 2026-09-26

### Fixed

- **A token refresh answered with a 5xx no longer keeps the refresh token.** The engine spends the
  refresh token before the steps that can still fail with a 500, and a proxy can answer 5xx after
  the engine answered, so presenting the token again could trip the engine's replay check and
  revoke the whole sign-in on every machine. The plugin now drops it; the live access token serves
  until it expires, then `duckwork lumberroom login` signs in again. A refresh that never connected
  still keeps the token.

## [1.0.0] - 2026-09-25

### Added

- **The lumberroom memory provider for Duckwork Agent.** Recall through Duckwork's `prefetch` hook on
  every turn, the digest on the first, and the engine's own `memory_search`, `memory_write`,
  `registry_get` and `memory_forget` from the live `tools/list`, over `/mcp` through the official
  `mcp` SDK. lumberroom.cloud with browser sign-in is the default; `base_url` points it at a
  self-hosted engine, which runs the same code with a static token or OAuth.
- Setup turns off Duckwork's `MEMORY.md` and `USER.md`; `duckwork lumberroom import-builtin` sends
  their entries to the engine's proposal queue.
- Gateway chats admit only listed owners, turn by turn; cron counts as the owner.
- `dreaming_review`, off by default: Duckwork may list and act on lumberroom.cloud dreaming proposals
  through `review_queue` and `review_decide` when the host is lumberroom.cloud and the server offers
  them.
- A cross-process refresh fence: two Duckwork processes on one profile never present the same
  refresh token twice.
- `scripts/duckwork-plugin-test.sh`, the end-to-end gate, in token and OAuth mode against an engine
  checkout.

Moved from `client/duckwork/` in the engine repository on 25 September 2026, with its history.
