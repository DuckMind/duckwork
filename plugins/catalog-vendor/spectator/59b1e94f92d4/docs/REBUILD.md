# Spectator Mode harness-neutral rebuild

Status: Core rebuild and production UI/UX redesign complete. The corrected core candidate passed its second independent review; the redesigned frontend passed full regression and browser QA.

## Product outcome

Spectator Mode exposes three guest-facing capabilities for a shared session:

1. A live, privacy-safe event stream.
2. Continuously updated, human-readable summary entries.
3. Read-only search of the exact committed branch snapshot used by the shared session.

The core is harness-neutral. Claude Code, Codex, Duckwork, Pi, OpenCode, Command Code and future environments connect through one bridge contract or a small native adapter. Unsupported capabilities fail clearly. No adapter may report successful delivery it did not perform.

The production interface uses a broadcast-studio design system with responsive light and dark themes while preserving every privacy, authentication and harness-neutral contract.

## Architecture boundaries

- `spectator.core`: contracts, registry, summary projection and orchestration. No harness imports.
- `spectator.adapters`: native or portable harness integrations.
- `spectator.bridge`: privacy-safe lifecycle-hook mapping and transport.
- `spectator.code`: read-only branch snapshot querying.
- `dashboard/plugin_api.py`: authenticated HTTP/WebSocket transport only.
- `dashboard/static/guest.html`: production guest interface and its self-contained design system.

## Execution checklist

### Phase 0 — baseline

- [x] Confirm baseline and create `rebuild/harness-neutral-core`.
- [x] Map the existing DB, poller, API, guest client and tests.
- [x] Write API-level behavioural gates first.
- [x] Witness RED: portable registration endpoint returned 404.

### Phase 1 — neutral core

- [x] Add runtime-checkable adapter contracts and value types.
- [x] Add a per-session adapter registry.
- [x] Add idempotent neutral event ingestion.
- [x] Add deterministic summary projection.
- [x] Add safe exact-commit branch queries.
- [x] Reach focused GREEN.

### Phase 2 — API and frontend shell

- [x] Add bridge registration, listing, removal and event-ingest endpoints.
- [x] Add stream, summary-entry and code-query endpoints.
- [x] Extend live WebSocket updates without duplicate cursor delivery.
- [x] Replace the old guest page with the three-view functional shell.
- [x] Preserve invite authentication, revocation and privacy masking.

### Phase 3 — adapters and compatibility

- [x] Add the Duckwork native metadata/source adapter.
- [x] Add portable profiles for Claude Code, Codex, Pi, OpenCode and Command Code.
- [x] Run the neutral conformance suite against every named harness profile.
- [x] Document capability detection and honest view-only behaviour.

### Phase 4 — verification

- [x] Collect and run the full suite: 295 tests passed with one recorded upstream Starlette deprecation warning.
- [x] Run Ruff, mypy, Bandit, Semgrep and detect-secrets against the exact source candidate.
- [x] Harden POSIX runtime state: private directories, `0600` database, unsafe-parent rejection and actionable degraded responses.
- [x] Separate runtime state from directory-installed source and bind defaults to the active `DUCKWORK_HOME`.
- [x] Lock the 0.2.0 state policy to fresh profile-local state; no automatic legacy migration.
- [x] Add a repo-local Duckwork verification recipe for `spectator.serve:app` and its public readiness page.
- [x] Build, install, dependency-audit and live-probe the corrected wheel (`ea57e92a73f4db4d7d971a52c4c81d8c3d03bbed9f6e24ea7b88fd5027f562b0`).
- [x] Verify exact-commit branch queries cannot expose untracked or credential files.
- [x] Verify both directory-style and exact final wheel-entry-point Duckwork loading.
- [x] Complete controller-run inline adversarial review with Markdown and JSON records.
- [x] Obtain an independent engineering review of the first frozen candidate: READY with no blockers.
- [x] Obtain a fresh independent review of the corrected frozen candidate: READY.
- [x] Classify the final Git diff and complete the separately approved commit, push and installation gates.

## Real harness evidence

- Duckwork: real `PluginManager` loaded both directory and wheel-entry-point forms without error.
- Codex CLI 0.149.1: authenticated model turn completed; lifecycle hooks reached Spectator and the synchronous `SessionEnd` warning was removed.
- OpenCode 1.18.23: the real local TypeScript plugin registered a session and emitted one privacy-safe user summary plus one idle transition. The configured model provider was unavailable, so no assistant response was generated.
- Pi 0.84.3: the real extension emitted start, user-input and shutdown events. No Pi provider credential was configured, so no assistant response was generated.
- Claude Code 2.1.201: the real project hook emitted session shutdown. Claude Code was not logged in, so no assistant response was generated.
- Command Code 1.32.2: the CLI and settings location were verified, but it refuses to start a session before authentication. Live hook execution remains blocked until a Command Code account is configured.

## Current release conditions

1. A fresh independent review must pass against the corrected frozen candidate.
2. The reviewer must reproduce the corrected wheel's build/install, dependency audit, HTTP/WebSocket probe and real Duckwork loader proof.
3. Deployment uses fresh profile-local state. Any future legacy migration is a separate reviewed change.
4. Command Code live execution remains an explicitly documented optional-integration gap unless authentication is supplied.
5. Build, commit, push, publication, live installation and deployment are separate approval gates.

### Phase 5 — production UI/UX redesign

- [x] Audit the functional shell and establish a distinctive broadcast-studio direction.
- [x] Build the production interface without changing the framework or functional contracts.
- [x] Add responsive light and dark themes, keyboard focus, reduced-motion and readable state styling.
- [x] Run browser, responsive, accessibility and full regression QA.
