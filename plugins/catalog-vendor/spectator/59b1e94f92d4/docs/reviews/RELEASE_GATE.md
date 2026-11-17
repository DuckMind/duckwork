# Release Gate — Spectator 0.2.0 harness-neutral core

Date: 25/08/2026
Verdict: CONDITIONAL

This is not a soft pass. The source and exact wheel have direct evidence, but independent approval and deployment decisions remain blocked.

## Scope

Built:

- Harness-neutral session contracts, adapter registry and portable bridge.
- Live event stream.
- Continuously updated summary entries.
- Exact-commit branch-code query.
- Functional three-view guest frontend.
- Duckwork, Claude Code, Codex, OpenCode, Pi, Command Code and generic integration templates/adapters.
- Private, profile-local runtime state with actionable degraded behaviour.

Out of scope:

- Complete visual/UI redesign.
- Publishing, live installation, gateway restart and production deployment.
- Moving or deleting legacy runtime state.

## Exact source evidence

- Base commit: `a802c7b58fb37450c629720c2466ab4c45cf5fb7`.
- Branch: `rebuild/harness-neutral-core`.
- Candidate: fully classified dirty worktree; no unexplained test/build residue.
- Canonical test runtime: `/home/kensei/repos/KenseiAgent/.venv/bin/python`.
- Python: 3.11.15.
- Pytest: 9.1.1.
- Collection: 291 tests collected.
- Execution: 291 passed in 25.94 seconds.
- Ruff: passed.
- mypy: no issues in 30 source files.
- Bandit: no medium/high findings.
- Semgrep security audit: passed.
- detect-secrets: no findings.
- `git diff --check`: passed.

## Exact release artefact

Wheel:

`/tmp/spectator-final-rc.jNALSU/duckwork_spectator-0.2.0-py3-none-any.whl`

SHA-256:

`809d0a49aab0fddea4cbbb4d6f2b6a13b49d2bfecd35a38d93b1fbc60a42773f`

Artefact checks:

- 43 wheel entries.
- Required adapters, API and frontend present.
- No tests, `.env`, auth file or host secret included.
- Duckwork entry point is module-valued: `spectator.duckwork_plugin`.
- Console scripts present: `spectator-hook`, `spectator-integrations`, `spectator-serve`.
- WebSocket runtime dependency present.
- Profile-local state location appears in package metadata.

Disposable install:

- Python 3.13.14.
- Spectator 0.2.0.
- WebSockets 17.0.1.
- Plugin module loaded and exposed `register`.
- All three console scripts present.
- Integration catalogue listed all five external templates.

Dependency audit:

- No known dependency vulnerabilities found.
- `duckwork-spectator` itself was skipped because version 0.2.0 is not published on PyPI.

## Runtime evidence against the exact wheel

Installed-wheel probe passed:

- HTTP authentication and invite flow.
- Session registration and lifecycle.
- Event ingestion and summary projection.
- Exact-commit branch query.
- Authenticated WebSocket delivery.
- Default `$DUCKWORK_HOME/data/spectator` placement.
- Runtime parent/data directories: `0700`.
- `spectator.db`: `0600`.
- `host_secret`: `0600`.

Real Duckwork `PluginManager` loaded the exact wheel as:

- name: `spectator`
- version: `0.2.0`
- source: `entrypoint`
- enabled: true
- loader error: none

The disposable server was stopped after the probe.

## Review evidence

Controller-run adversarial review records:

- `docs/reviews/HERMAGUARD_REBUILD.md`
- `docs/reviews/HERMAGUARD_REBUILD.json`

No open CRITICAL, HIGH or MEDIUM source findings remained after fixes.

Formal Hermaguard status is PARTIAL because its companion coverage/verification commands are not installed and the implementer cannot independently approve its own work.

## Harness evidence

- Duckwork: real directory and exact-wheel loading proven.
- Codex: authenticated successful model turn proven.
- OpenCode: real adapter lifecycle proven; successful assistant turn blocked by unavailable provider configuration.
- Pi: real extension lifecycle proven; successful assistant turn blocked by absent provider credentials.
- Claude Code: real hook lifecycle proven; successful assistant turn blocked by login state.
- Command Code: CLI/settings contract proven; hook execution blocked before session start by account authentication.

## Defects fixed during final review

1. Runtime directory could be `0755` and database `0644`.
2. Group/world-writable non-sticky storage parents were accepted.
3. Unsafe storage generated an internal HTTP 500 instead of actionable degraded state.
4. Default state ignored `DUCKWORK_HOME`.
5. Runtime state shared the directory-install plugin source namespace.

All five now have direct regression evidence.

## Regression and tech-debt risk

- No database schema migration was introduced.
- The runtime state path changed intentionally from the legacy plugin directory to profile-local data storage.
- No automatic state migration occurs.
- Fresh 0.2.0 startup creates a new host secret and invalidates old invites.
- Preserving old state requires an explicit override or separately approved migration.
- UI redesign remains openly deferred, not hidden as finished work.

## Conditions

Before merge, publication, installation or deployment:

1. Obtain an independent reviewer verdict. Self-approval is forbidden.
2. Choose one state policy:
   - start fresh in `$DUCKWORK_HOME/data/spectator`; or
   - approve and verify a legacy-state migration/override.
3. Either provide credentials for the blocked real harness turns or explicitly accept those integrations with conformance/lifecycle evidence only.

Enforcement action: keep merge, publish, install and deploy blocked until these conditions are recorded as approved or completed.

## Release state

- Built: yes.
- Exact wheel verified: yes.
- Committed: no.
- Pushed: no.
- Published: no.
- Installed live: no.
- Deployed: no.
- Legacy state moved: no.
- Live permissions changed: no.
- UI/UX redesign: deferred.
