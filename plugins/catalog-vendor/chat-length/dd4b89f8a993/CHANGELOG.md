# Changelog

## v1.1.0 (2026-10-21)

- No private Duckwork imports any more (plugin catalog rule 9): the compaction point is computed from the documented `compression` settings. Checked against Duckwork' own calculation in 780 combinations of window size, threshold and per-model overrides, 0 differences.
- Without a provider measurement (first turn after a restart) the plugin now waits one turn instead of guessing the context window, unless `model.context_length` is set explicitly.
- Declares `requires_duckwork: ">=0.21.5"`.

## v1.0.0 (2026-10-20)

- First release: notice at 70 % and 90 % (configurable), each level once per chat, re-armed after compaction.
- Fill level from real provider numbers (`post_api_request`); rough estimate only without a measurement.
- Measured against Duckwork' compaction point by default, optionally against the full context window.
- Opener with chat title, session id, 2 to 3 status bullets and open items; the new chat pulls context via `session_search`.
- Notice language: `auto` (conversation language), `en` or `de`.
- No notices in background jobs (cron, subagents, Kanban, batch, webhooks).
- Prompt caching verified: the following turn replays every earlier message byte-identical.
