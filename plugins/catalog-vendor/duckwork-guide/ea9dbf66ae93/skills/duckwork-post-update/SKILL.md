---
name: duckwork-post-update
description: Verify and clean up after a Duckwork update — confirm the gateway restarted on new code, check plugin migrations, review config changes, run health checks, and surface cleanup opportunities.
version: 1.0.1
metadata:
  duckwork:
    tags: [duckwork, update, verification, maintenance]
    related_skills: [installing-duckwork, diagnosing-gateway, diagnosing-plugins, diagnosing-skills, diagnosing-memory, diagnosing-path]
---

# Duckwork Post-Update

Run after `duckwork update` to verify the update landed correctly, catch silent
migrations, and surface cleanup opportunities. The updater handles code and
dependencies and attempts a gateway-fleet restart, but it does not review config
changes or report what moved. This skill verifies the automatic restart result
and handles any restart still owed.

## When to use

- After any `duckwork update` (manual or automatic)
- After a desktop app update
- When the gateway seems stale or unresponsive after an update
- As periodic maintenance (weekly)

## Workflow

### 1. Confirm the update landed

```bash
duckwork --version
```

Check the version string. If it still shows the old version, the update may not
have completed — check `$DUCKWORK_HOME/logs/update.log` for errors (resolve
`$DUCKWORK_HOME` via `duckwork config path`).

### 2. Verify the gateway restarted on new code

```bash
duckwork gateway status
```

Note the reported PID before restarting. If the output contains:

> ⚠ A previous `duckwork update` pulled new code but did not restart running gateways.

Run:

```bash
duckwork gateway restart
```

Then confirm the new PID:

```bash
duckwork gateway status
```

The PID should differ from the pre-restart value you noted (a changed PID alone
is not proof — PIDs recycle — so the warning line above is the authoritative
signal). If the gateway process is still running old code, a restart is
required. To check the process directly, on Windows run
`Get-CimInstance Win32_Process -Filter "Name LIKE '%duckwork%'" | Select-Object ProcessId,CommandLine`,
on POSIX run `pgrep -af duckwork` (or `ps aux | grep '[h]ermes'`).

### 3. Check for plugin migrations

Recent updates have moved functionality out of core into plugins:

| Plugin | What it replaces | Install command |
|---|---|---|
| `honcho` | Memory provider (built into core pre-0.21.5) | `duckwork plugins install honcho` |
| `homeassistant` | Home Assistant integration (built into core pre-0.21.5) | `duckwork plugins install homeassistant` |
| `duckwork-session-reset-policy` | `session_reset.mode: both` behavior | `duckwork plugins install duckwork-session-reset-policy` |

Check which are installed:

```bash
duckwork plugins list
```

If a plugin is listed as `not enabled` but was previously active, enable it:

```bash
duckwork plugins enable <name>
```

### 4. Review config format changes

Updates may bump the config schema version. Check for per-profile changes:

```bash
duckwork config path
```

If the update log shows `config format updated (v46 → v50)` or similar, review
the new schema:

```bash
duckwork config migrate
```

(`migrate` takes no preview flag — read its output before confirming anything
it proposes to change.)

### 5. Review skills sync

The updater syncs bundled skills but preserves user-modified copies. Check what
was updated vs. kept:

```bash
duckwork skills list-modified
```

For each user-modified skill, decide:
- **Keep** — your local changes are intentional
- **Reset** — discard local changes and accept the upstream version. Back up
  your copy first (a plain `reset` only clears the sync-manifest entry and keeps
  your copy — pass `--restore` to also replace it with the bundled version):

```bash
duckwork skills reset <skill-name> --restore
```

### 6. Run health check

```bash
duckwork doctor
```

Categorize the output:

| Category | Action |
|---|---|
| Auto-fixable | Run `duckwork doctor --fix`, but only for items the report marks auto-fixable — it mutates config/state |
| Manual (API keys, tokens) | User must provide credentials |
| Informational | No action needed |

### 7. Cleanup opportunities

#### Stale autoshash entries

The updater stashes local changes before pulling. Old entries accumulate.
Resolve `$DUCKWORK_HOME` via `duckwork config path` (POSIX: `%LOCALAPPDATA%\duckwork`
equivalent on native Windows is `Split-Path (duckwork config path) -Parent`):

POSIX:

```bash
DUCKWORK_HOME=$(dirname "$(duckwork config path)")
git -C "$DUCKWORK_HOME/duckwork-agent" stash list
```

PowerShell:

```powershell
$cfg = duckwork config path
$DUCKWORK_HOME = Split-Path $cfg -Parent
git -C "$DUCKWORK_HOME/duckwork-agent" stash list
```

Entries with `duckwork-update-autostash-` prefix may contain local changes that
were never restored. Inspect each entry before dropping:

```bash
git -C "$DUCKWORK_HOME/duckwork-agent" stash show -p stash@{N}
```

> [!CAUTION]
> Only drop entries whose changes are confirmed unneeded, and export them first
> (`stash show -p` saved to a file) — a drop cannot be undone. Note that
> `stash@{N}` indices renumber after each drop, so re-list before each one:

```bash
git -C "$DUCKWORK_HOME/duckwork-agent" stash drop stash@{N}
```

#### Large WAL file

If `duckwork doctor` reports a large WAL file (above 50 MB — missed checkpoints),
stop the profile's gateway, then checkpoint:

```bash
duckwork doctor --fix
```

For the general database-care procedure (compaction canary, integrity queries,
prune/archive/optimize), load the `diagnosing-memory` skill and follow its
session-database reference therein.

#### Oversized state database

If `duckwork doctor` reports an oversized `state.db` (full-text index on the old
layout), compact it offline with the gateway stopped:

```bash
duckwork sessions optimize-storage
```

This rebuilds the search index in the compact layout, reclaiming a large
fraction of `state.db` on big databases. It prompts for disk-space
confirmation, is safe to interrupt and re-run (it resumes), and must not be
forced under a live writer (no `--force` while a gateway holds `state.db`).

#### Disk headroom

POSIX:

```bash
DUCKWORK_HOME=$(dirname "$(duckwork config path)")
df -h "$DUCKWORK_HOME"
```

PowerShell:

```powershell
$cfg = duckwork config path
$DUCKWORK_HOME = Split-Path $cfg -Parent
(Get-Item $DUCKWORK_HOME).PSDrive | Select-Object Name, Used, Free
```

If free space is low (as a rule of thumb, below 10 GB), investigate large
directories before the next update (the updater needs several GB for
dependencies and backups).

### 8. Report

Present findings in the standard format (numbers below are an example from one
host, not thresholds — use the actual command output as evidence):

#### Summary
Update to v0.21.5+9802 completed. Gateway restarted (PID 29780). Two plugin
migrations applied (honcho, homeassistant). Three items need attention.

#### Findings

| Severity | What | Evidence |
|---|---|---|
| MEDIUM | `session_reset.mode: both` deprecated | Gateway log: "no longer applied" — install `duckwork-session-reset-policy` |
| LOW | 3 stale autoshash entries | `git stash list` shows entries from 2026-09-03 |
| INFO | 4 skills updated, 15 user-modified kept | `duckwork skills list-modified` |

#### Recommended Actions
1. Install `duckwork-session-reset-policy` to restore old reset behavior
2. Review user-modified skills: `duckwork skills list-modified`
3. Drop stale autoshash entries (optional, cosmetic)

#### References
- `$DUCKWORK_HOME/logs/update.log` — full update output
- `$DUCKWORK_HOME/logs/gateway.log` — gateway restart confirmation
- `duckwork doctor` — health check results

---

*Facts re-verified 2026-10-13 against upstream source at commit `a082d1e180be1e603a6a307fce4d098e30f54eb7`: `duckwork_cli/update_cmd_fleet.py::_warn_pending_fleet_restart` (gateway restart warning), `duckwork_cli/update_cmd_stash.py::_AUTOSTASH_NAME_PREFIX` (autostash prefix), `duckwork_cli/update_cmd_config.py` (config format message), `duckwork_cli/config.py::_cmd_config_migrate` (migrate takes no preview flag), `duckwork_cli/skills_hub.py::do_reset` (`restore` flag), `duckwork_cli/doctor_state.py::_state_db_wal` (WAL finding and optimize-storage trigger), `duckwork_cli/session_reset_retirement.py` (reset-mode retirement notice; file postdates the repo baseline so it stays a bare path, not a machine-checked anchor); CLI behavior cross-checked against the local install (v0.21.6). Re-verify before reuse.*
