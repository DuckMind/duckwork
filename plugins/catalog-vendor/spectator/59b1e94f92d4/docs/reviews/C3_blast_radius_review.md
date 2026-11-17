# C3 FeedEngine — Blast Radius & Integration Review

Scope: workspace `t_169a8919/duckwork-spectator` @ `c96a26f` (main). Reviewed commits: `39610e5` (C1–C3 feature) and `6ffab1a` (index + LOW fixes).
Note: live plugin DB (`~/.duckwork/plugins/spectator/spectator.db`) inspection was **denied by user**; live-state findings are code-based only.

## Callers table

| file:line | changed symbol | risk | notes |
|---|---|---|---|
| dashboard/plugin_api.py:48 | `FeedEngine` (import) | LOW | Module-level import; if engine removed without touching dashboard → ImportError kills whole router, not just /feed. Revert engine+dashboard together. |
| dashboard/plugin_api.py:66, 124 | `FeedEngine` (state + lazy init) | LOW | Constructed with `(db, session_id)`; matches `__init__` exactly. Empty `DUCKWORK_SESSION_ID` → all events keyed to `""` (consistent, but worth a startup log). |
| dashboard/plugin_api.py:245 | `FeedEngine` (re-init in `init_plugin`) | LOW | Re-instantiated on session reset with new session_id — correct isolation. |
| dashboard/plugin_api.py:732-733 | `sweep_expired(retention_days=…)` | **MEDIUM** | Runs on the GET /feed poll hot path. Every guest poll acquires the module write lock + BEGIN IMMEDIATE, even when nothing is expired (2s poll interval × N guests). Fine at current scale; C4's `test_sqlite_write_latency` (50 concurrent appends + approvals, p95 ≤ 250ms) is the load gate — sweep-on-poll adds a write-lock hop to every poll, so verify against that test when C4 lands. |
| dashboard/plugin_api.py:750 | `query(since, limit, event_types)` | LOW | Signature/return shape (`events/reset/oldest_seq`) exactly matches `FeedResponse` model and `FeedEventResponse` fields (seq/type/summary/timestamp). Endpoint validates `types` before calling; engine's placeholder construction is `?`-only (no injection). Double limit clamp (endpoint + engine) is redundant but harmless. `since` not validated for negatives — negative cursor returns from-beginning, `reset:False`; benign. |
| tests/test_c03_feedengine.py (throughout) | `FeedEngine.append/query/sweep_expired`, `privacy_mask`, `mask_summary` | LOW | 187/187 green per commit msg; covers append/query/cursor-reset/retention/endpoint integration + ≥50-case mask corpus (100% redaction, ≤5% FP). One fragile test pattern: `test_mask_failure_counter_increments` depends on `sys.modules` purge ordering from C1 tests (documented in-test) — keep tests in the same file/module identity. |
| src/spectator/feed/__init__.py:4-21 | re-exports | LOW | Public surface confirmed: `FeedEngine, privacy_mask, mask_summary, MAX_SUMMARY_CHARS` + all four summary dataclasses (`ToolCallSummary`, `ToolResultSummary`, `MessageSummary`, `StatusChangeSummary`), all in `__all__`. C3b producers can import cleanly from `spectator.feed`. |
| **No production caller of `append` exists yet** | `append(event_type, summary)` | **MEDIUM (gap)** | The producer side is unbuilt: nothing in `src/` or `dashboard/` calls `append` (only tests). C3b (transcript-tail poller / onEvent hook) is the intended first production caller. Engine contract is therefore unexercised in prod for: (a) summary-shape discipline, (b) timestamp format (see below). |
| docs/event-contract.md:14,149 | contract gate | LOW | Declares BUILD STEP 0 gate PASS; types/payload/boundary/frequency/reset all enumerated and test-asserted. |

## Downstream dependencies

- **C3b — transcript-tail poller (not yet built).** Two contract risks it will hit:
  1. **Summary shape is enforced only by convention.** `append` validates `event_type` but accepts an arbitrary `dict`; `mask_summary` masks **only** the `note` field. A producer passing a dict with a free-text key that isn't `note` (e.g. `{"content": "<raw host text>"}`) would persist raw content unmasked — violating the "raw content NEVER copied" invariant while the AC-shaped tests still pass. Recommend: engine-side schema check (reject unknown keys / non-`note` strings) or force producers through the four dataclasses' `to_dict()`, before C3b builds against it.
  2. **Timestamp format fragility in `sweep_expired`.** Sweep does lexicographic string compare `timestamp < cutoff` on ISO-8601 text. `datetime.isoformat()` omits the microseconds field when it's exactly zero, and `'.'(0x2E) < '+'(0x2B)`, so mixed `…00+00:00` / `…00.123456+00:00` strings sort up to <1s wrong — negligible for a 7-day window but a latent mixed-format bug. Transcript-file timestamps from C3b (arbitrary precision/offset) would break the comparison outright. **C3b must write timestamps via `utcnow()`/engine format only**; consider normalizing to a fixed format now (LOW, one-line).
- **C4 — SuggestionGate.** Spec (line 135, 646) shows SuggestionGate uses `suggestions`/`audit_log`, not `events`; the only shared surface is `SpectatorDB.write_txn()` and the write-lock. C4's concurrency test is the only place FeedEngine write throughput is stress-tested — gate on it. No API coupling to `FeedEngine` methods.
- **Host/dashboard UI (C5).** GET /feed response contract (`reset`, `oldest_seq`) is the client-facing contract; stable since C3, tests pin it. C5 guest.html currently only has a placeholder `#feed` div.
- **Sibling workspaces** `t_71f67293/duckwork-spectator`, `t_c707c9f2/duckwork-spectator` contain older copies (no `src/spectator/feed/` in the former). No code-level conflict now, but if those tasks merge/rebase against this workspace expect C3 divergence; confirm which workspace is canonical before converging.

## Configuration & contracts

- `SpectatorConfig.event_retention_days` (default 7, `ge=1`) → `/feed` hot path. `feed_source` (`auto|onEvent|transcript`) validated; C3b selects the actual source. `mask_overrides` exists in config but engine has no hook — dead config key until a consumer lands (flag, don't block).
- Events table: `seq INTEGER PK AUTOINCREMENT, session_id, type, summary, timestamp` — no schema versioning (`PRAGMA user_version` absent); migrations = idempotent `SCHEMA_SQL` re-run at lazy init. Fine at this size, LOW risk.
- 280-char bound: `MAX_SUMMARY_CHARS` module constant; `mask_summary` truncates `note` to fit; fallback `{"type":…,"summary":"[redacted]"}` is well under. Enforced by tests.
- Valid event types set duplicated in `engine.append` and `plugin_api.get_feed` (drift risk when a 5th type lands — single source it).

## Index migration safety — `idx_events_session_timestamp (session_id, timestamp)`

- **Safe.** `CREATE INDEX IF NOT EXISTS` inside `init_schema()` (idempotent, runs at lazy init on every startup). On an existing DB it's a one-time build inside the schema write transaction; with 7-day retention the `events` table is bounded/small, so build cost is trivial. `IF NOT EXISTS` cannot mismatch (index name is new, never existed in prior schema).
- **Downsides (all LOW):** (1) write amplification — every append/sweep maintains one extra 2-col index; trivial at poll-event rates. (2) Redundant with `idx_events_session_seq` for `query()` (which filters `session_id` + `seq`), but it's exactly the shape `sweep_expired` needs (`session_id` + `timestamp < cutoff`), so it's justified. (3) `executescript` failure (disk full) on index creation would abort init → plugin fails closed; acceptable, no partial state (executescript is transactional). (4) If the index is ever reverted/renamed, an already-created index **persists in the live DB** until `DROP INDEX` — leftover is harmless but stays.
- Live-DB verification not performed (command denied); schema state at `~/.duckwork/plugins/spectator/` is unconfirmed — worth one read-only check during deployment.

## Revert safety

- **`git revert 6ffab1a` (index + LOW fixes) — SAFE.** Purely additive DDL + internal import cleanup. Reverting leaves the index in existing DBs (harmless residue; optionally `DROP INDEX IF EXISTS idx_events_session_timestamp`).
- **Reverting engine while keeping dashboard — BREAKS.** `plugin_api.py:48` imports `FeedEngine` at module level; removing `src/spectator/feed/` kills the entire router mount, not just /feed. C3 engine + dashboard section (`_AppState.feed_engine`, /feed route, import) must be reverted together, or a stub kept.
- **Data:** no destructive migration exists. `events` rows are forward-compatible (no consumer of the table outside C3); reverting C3 leaves orphan rows that C3b would re-use on re-land. `suggestions`/`invites`/`audit_log` untouched by this change.
- History is clean (3 commits, `main` only, no tags) — single-commit revert is mechanical. No rollback ordering hazard beyond the import coupling above.

## Bottom line

C3 engine API fully satisfies its **only** production consumer (GET /feed: `sweep_expired` + `query` shapes verified line-by-line) and its test suite. Real risks are forward-looking, not current: (1) `append` has no production caller — summary-shape discipline is unenforced (dict-in, only `note` masked) and timestamp-format assumptions are undocumented for C3b; (2) sweep-on-poll takes the write lock on every guest poll (gate on C4's concurrency test); (3) index migration is safe/idempotent with trivial write amplification. No blockers; two recommended hardening notes for C3b handoff.
