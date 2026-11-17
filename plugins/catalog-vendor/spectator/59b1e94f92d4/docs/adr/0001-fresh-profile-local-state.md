# ADR 0001: Fresh profile-local runtime state

- Status: Accepted
- Date: 2026-08-26
- Applies to: Spectator 0.2.0

## Context

Older builds stored runtime data beside plugin source at `~/.duckwork/plugins/spectator/`. That mixes executable files with secrets and mutable state. It also makes profile isolation and private permissions harder to enforce.

## Decision

Spectator 0.2.0 starts with fresh state at `$DUCKWORK_HOME/data/spectator/`.

- No legacy file is read, copied, moved or changed automatically.
- A new host secret is created, so old invites stop working.
- Legacy preservation requires a separate reviewed migration.
- The new runtime must not be pointed at the legacy plugin-source directory.

## Consequences

Positive:

- Source and runtime data are separated.
- Each Duckwork profile owns its own state.
- Private `0700`/`0600` permissions can be enforced consistently.
- A rollback does not destroy legacy data.

Negative:

- Existing guests must receive new invites.
- Legacy history is not visible unless a migration is designed and approved later.
- Operators who expected automatic carry-over must change their setup.

## Quality driver

When 0.2.0 starts with legacy files still present, it must create and use only profile-local state, leave every legacy file unchanged, and issue a new host identity. Automated path and permission tests must verify that boundary.
