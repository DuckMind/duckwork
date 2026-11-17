# Inline Hermaguard Review — Spectator 0.2.0 rebuild

Date: 25/08/2026 23:51 BST
Scope: 33 production code/frontend files in a 55-file dirty candidate
Base: `a802c7b58fb37450c629720c2466ab4c45cf5fb7`
Branch: `rebuild/harness-neutral-core`
Review mode: controller-run inline adversarial review; no delegation, by user constraint

## Evidence

Deterministic checks against the final source candidate:

- Pytest collection: 291 tests collected.
- Pytest execution: 291 passed in 25.94 seconds.
- Ruff: passed.
- mypy: no issues in 30 source files.
- Bandit: no medium/high findings.
- Semgrep `p/security-audit`: passed.
- detect-secrets: no findings.
- `git diff --check`: passed.
- Manual searches: no unsafe HTML sinks, shell execution, dynamic SQL construction, machine-specific production paths, `eval`, `exec`, unsafe YAML loading or pickle deserialisation.

The Hermaguard companion commands (`hermaguard-prescan`, coverage, locate, role-patterns, sanitize, verify and grader) are not installed. Their absence is recorded rather than hidden. This report therefore does not claim machine-validated full Hermaguard coverage.

## Current findings

No open CRITICAL, HIGH or MEDIUM source finding survived verification.

### Deployment disclosure — legacy state is not auto-migrated

Version 0.2.0 now stores state in `$DUCKWORK_HOME/data/spectator`, separate from directory-installed plugin source. Older builds used `$DUCKWORK_HOME/plugins/spectator`.

This is intentional and documented. A default 0.2.0 start creates a fresh host secret and invalidates old invites. Preserving legacy state requires an explicit `SPECTATOR_DATA_DIR` override or a separately approved migration. No live state was moved by this review.

## Defects found and fixed during the review

### Resolved: local disclosure and replacement of runtime state

Previous behaviour created the runtime directory as `0755`, left `spectator.db` as `0644`, and accepted a group/world-writable non-sticky parent. The database can contain event summaries, audit records and guest suggestion content.

Fix:

- `src/spectator/db/db.py:118-198` creates private directories, rejects unsafe or unowned paths, refuses symlinks, sets the runtime directory to `0700` and the database to `0600`.
- `tests/test_c01_scaffold.py:117-138` witnessed RED before the fix and now passes.

### Resolved: unsafe storage raised an internal HTTP 500

Fix:

- `dashboard/plugin_api.py:130-146` converts storage failures into fail-closed degraded state.
- `dashboard/plugin_api.py:545-576` returns an actionable `runtime_storage_unavailable` HTTP 503 response.
- `tests/test_c01_scaffold.py:686-707` witnessed 500 before the fix and now passes with 503.

### Resolved: profile state ignored `DUCKWORK_HOME` and shared plugin source space

Fix:

- `src/spectator/config.py:48-70` derives state from the active profile and uses `$DUCKWORK_HOME/data/spectator`.
- `tests/test_c01_scaffold.py:160-186` witnessed the old root-profile/plugin path and now proves profile-local isolation.

## Coverage ledger

This is the controller's manual ledger, not a substitute for the missing `hermaguard-coverage` validator.

| Class | Status | Evidence |
|---|---|---|
| CWE-22 path traversal | Clean | Exact repository root/commit validation; credential and untracked paths excluded |
| CWE-78 command injection | Clean | Subprocess calls use argument arrays; no shell execution |
| CWE-79 XSS | Clean | No `innerHTML`, `document.write`, `eval` or dynamic HTML sinks in guest client |
| CWE-89 SQL injection | Clean | Parameterised SQLite queries; no dynamic SQL construction found |
| CWE-287 authentication | Clean | Host bearer and guest HMAC flows have positive/negative tests |
| CWE-306 missing authentication | Clean | Bridge mutation routes are host-only; guest routes are token scoped |
| CWE-311 sensitive-data exposure | Clean | Privacy corpus, exact-commit query masking and private runtime permissions |
| CWE-362 race conditions | Clean | Single-writer DB lock and concurrent approval/cross-thread tests pass |
| CWE-400 resource exhaustion | Clean | Request, query, cursor, event and suggestion limits enforced |
| CWE-502 unsafe deserialisation | Not applicable | JSON and safe YAML only; no pickle/object deserialisation |
| CWE-798 hard-coded credentials | Clean | detect-secrets clean; generated secret is file-backed and `0600` |
| CWE-862 missing authorisation | Clean | Role-enforcement and cross-guest isolation tests pass |
| CWE-918 SSRF | Clean | Hook transport rejects non-HTTP schemes; endpoint is host configured |
| HG-ASYNC | Clean | Codex session-end and OpenCode forwarding regressions covered |
| HG-PARTIAL-WRITE | Clean | SQLite transactions and suggestion recovery tests cover partial states |
| HG-STATE-TRANSITION | Clean | Invite, suggestion, revocation and lifecycle transition tests pass |
| Memory-unsafe classes | Not applicable | Python/TypeScript implementation without native unsafe blocks |

## Blast radius

- Storage hardening affects database startup, standalone service startup, host-mounted lazy initialisation and test fixtures.
- Path isolation affects default config, state DB discovery, standalone service documentation and profile behaviour.
- No schema migration was introduced.
- Revert is mechanically simple but not operationally safe after 0.2.0 state is created, because reverting changes the default state location and secret identity.

## Verdict

Code risk: LOW based on direct deterministic and runtime evidence.
Formal Gate 0 state: PARTIAL.

Reason: the implementer/controller cannot independently approve its own work, and the required Hermaguard companion coverage validator was unavailable. Independent review remains mandatory before merge, publication, installation or deployment.

No live permission, state, configuration, service or deployment change was made by this review.
