<p align="center"><img src="../assets/agent-importers.jpg" alt="Agent Importers: official Duckwork Agent plugin" width="100%"></p>

# Agent Importers for Duckwork Agent

> Part of the [Duckwork Official Plugins](../README.md), Fordex's official plugins for Duckwork Agent. Formerly built into Duckwork Agent core (`duckwork_cli/agent_import.py`, and for OpenClaw `duckwork_cli/claw.py` with the `openclaw-migration` optional skill).

`duckwork import-agent` brings an existing **OpenClaw** (`~/.openclaw`), **Claude Code** (`~/.claude`), **OpenAI Codex CLI** (`~/.codex`) or **Cursor** (`~/.cursor`) setup into Duckwork with one command. Every run shows a per-item preview first and `--dry-run` never touches disk. API keys and credentials are never imported, with one opt-in exception: OpenClaw's allowlisted secrets when you pass `--migrate-secrets`.

| Agent | Command | Default source |
|---|---|---|
| OpenClaw (also legacy Clawdbot / Moltbot) | `duckwork import-agent openclaw` (old spelling: `duckwork claw migrate`) | `~/.openclaw`, `~/.clawdbot`, `~/.moltbot` |
| Claude Code | `duckwork import-agent claude-code` | `~/.claude` |
| Codex CLI | `duckwork import-agent codex` | `~/.codex` |
| Cursor | `duckwork import-agent cursor` | `~/.cursor` |

## Install

```bash
duckwork plugins install agent-importers
# or straight from this repo:
duckwork plugins install Fordex/duckwork-official-plugins#agent-importers
```

Upgrading from a Duckwork version that had `import-agent` built in: the command, its flags and your
sync manifest (`import-sync.json` in the profile) are unchanged. Profiles that registered a sync
source get the plugin automatically on update; everyone else sees the install line when they run
`duckwork import-agent`.

## Usage

```bash
duckwork import-agent                    # auto-detect ~/.openclaw, ~/.claude, ~/.codex or ~/.cursor
duckwork import-agent openclaw           # import from ~/.openclaw (see "OpenClaw" below)
duckwork import-agent claude-code        # import from ~/.claude
duckwork import-agent codex              # import from ~/.codex
duckwork import-agent cursor             # import from ~/.cursor
duckwork import-agent claude-code --dry-run          # preview only
duckwork import-agent codex --source /path/to/.codex # custom location
duckwork import-agent claude-code --overwrite --yes  # replace conflicts, skip prompts
duckwork import-agent --sync             # re-import every registered source that changed
duckwork import-agent --sync --dry-run   # preview what a sync would do
```

It imports into the active profile (`duckwork -p <name> import-agent ...` for another one).

## OpenClaw

`duckwork import-agent openclaw` is the former `duckwork claw migrate`, with the same flags and defaults. `duckwork claw migrate ...` keeps working and runs the same code.

```bash
duckwork import-agent openclaw                       # preview, confirm, back up, migrate
duckwork import-agent openclaw --dry-run             # preview only
duckwork import-agent openclaw --preset user-data    # user data and compatible config only
duckwork import-agent openclaw --preset full --migrate-secrets --yes   # include allowlisted secrets
duckwork claw cleanup --dry-run                      # what cleanup would archive
duckwork claw cleanup                                # rename ~/.openclaw to ~/.openclaw.pre-migration
```

| Flag | Meaning |
|---|---|
| `--source <path>` | OpenClaw directory (default: the first of `~/.openclaw`, `~/.clawdbot`, `~/.moltbot` that exists) |
| `--dry-run` | Preview only |
| `--preset {user-data,full}` | `full` (default) is `user-data` plus the secret categories (bot tokens, provider API keys), which still import only with `--migrate-secrets`; `user-data` leaves them out entirely |
| `--overwrite` | Replace existing Duckwork targets; without it a plan with conflicts is refused before anything is written |
| `--migrate-secrets` | Import allowlisted secrets (`TELEGRAM_BOT_TOKEN`, provider API keys, ...). Required even under `--preset full` |
| `--no-backup` | Skip the pre-migration snapshot |
| `--workspace-target <path>` | Absolute path to copy OpenClaw's `AGENTS.md` workspace instructions into |
| `--skill-conflict {skip,overwrite,rename}` | Imported skill name clashes: keep the existing one (default), replace it, or import as `<name>-imported` |
| `-y`, `--yes` | Skip the confirmation prompt |

These flags only apply to OpenClaw; passing them with another agent prints an error and imports nothing. OpenClaw is not part of `--sync`.

**Secrets.** Secrets migration is a separate, explicit step: a run without `--migrate-secrets` reports detected API keys and bot tokens as skipped and tells you how to add them. Even with it, only secrets with a clean Duckwork destination are imported; other auth blobs are reported as skipped.

**Before it writes.** It warns when OpenClaw is still running, or when this profile's Duckwork gateway is connected to messaging platforms (Telegram, Discord and Slack allow one session per bot token). Non-interactive runs stop after the preview unless you pass `--yes`. Before applying, it writes one restore-point zip of the Duckwork home to its `backups/` directory (`pre-migration-<timestamp>.zip`, the last 5 kept); restore it with `duckwork import <archive>`. The OpenClaw directory itself is never modified.

**Cleanup.** `duckwork claw cleanup` (alias `clean`; `--source`, `--dry-run`, `-y`) lists each OpenClaw directory's workspaces and state files and renames the directory to `<name>.pre-migration` (date-stamped if that exists). Nothing is deleted; rename it back to undo. While OpenClaw is still running it asks before archiving (a non-interactive session without `--yes` aborts), since the running service would recreate an empty directory.

**What maps where, in short:** `SOUL.md` → the profile's `SOUL.md`; `MEMORY.md`, `USER.md` and daily memory files → memory entries; command approvals → `command_allowlist`; skills from the workspace, `~/.openclaw/skills`, `~/.agents/skills` → `skills/openclaw-imports/`; default model, custom providers, agent behaviour, MCP servers, TTS and messaging settings → `config.yaml` / `.env` (OpenClaw's workspace folder becomes `terminal.cwd`, unless it is inside the OpenClaw directory); docs with no Duckwork equivalent are archived in the migration report directory. The full mapping is in the [Migrate from OpenClaw guide](https://duckwork-agent.fordex.com/docs/guides/migrate-from-openclaw).

**The skill.** The plugin ships the `openclaw-migration` skill (`agent-importers:openclaw-migration`): ask Duckwork to migrate from OpenClaw and it runs a guided dry run, asks about conflicts, workspace instructions and secrets, then executes the same migration script (`skills/openclaw-migration/scripts/openclaw_to_duckwork.py`).

## What maps where (Claude Code, Codex CLI, Cursor)

### Claude Code (`~/.claude`)

| Claude Code | Duckwork |
|---|---|
| `CLAUDE.md` | Memory entries in `memories/MEMORY.md` |
| `settings.json` `permissions.allow` (`Bash(...)` rules) | `command_allowlist` in `config.yaml` |
| `settings.json` `permissions.deny` (`Bash(...)` rules) | `approvals.deny` in `config.yaml` |
| `~/.claude.json` / `settings.json` `mcpServers` | `mcp_servers` in `config.yaml` |
| `skills/<name>/` (dirs with `SKILL.md`) | `skills/claude-code-imports/<name>/` |
| `commands/*.md` | Reported as skipped (no direct equivalent) |

Claude's `Bash(npm run test:*)` prefix rules become `npm run test*` globs. Non-`Bash` rules and bare `Bash` are reported as not mapped.

### Codex CLI (`~/.codex`)

| Codex | Duckwork |
|---|---|
| `AGENTS.md` | Memory entries in `memories/MEMORY.md` |
| `config.toml` `[mcp_servers.*]` | `mcp_servers` in `config.yaml` |
| `memories/*.md` | Memory entries in `memories/MEMORY.md` |
| `skills/<name>/` (dirs with `SKILL.md`) | `skills/codex-imports/<name>/` |

### Cursor (`~/.cursor`)

| Cursor | Duckwork |
|---|---|
| `AGENTS.md` | Memory entries in `memories/MEMORY.md` |
| `rules/**/*.md`, `rules/**/*.mdc` (User Rules) | Memory entries in `memories/MEMORY.md` |
| `mcp.json` `mcpServers` | `mcp_servers` in `config.yaml` |
| `skills/**/<name>/` (dirs with `SKILL.md`, category folders allowed) | `skills/cursor-imports/<name>/` |

`.mdc` frontmatter (`description`, `globs`, `alwaysApply`) is Cursor routing metadata and is stripped; only the rule body is imported. A skill is the folder holding `SKILL.md`, so `skills/shipping/land-it/` imports as `cursor-imports/land-it/`; two skills with the same name in different folders are reported as a conflict.

## What is never imported

Credential files (`~/.claude/.credentials.json`, `~/.codex/auth.json`, `~/.cursor/cli-config.json`) are never read, and MCP server environment variables or headers with secret-looking names (`*_TOKEN`, `*_API_KEY`, `Authorization`, ...) are stripped and listed in the report so you can re-add them deliberately. Run `duckwork setup` for providers, or put secrets in the profile's `.env`.

## Behaviour

- Existing MCP servers and skills with the same name are conflicts and skipped unless `--overwrite`.
- Memory entries are merged and deduplicated into the existing store; the previous `MEMORY.md` is backed up as `MEMORY.md.bak.<timestamp>` first.
- A `config.yaml` that cannot be read or parsed is never rewritten: the import records an error and leaves the file byte-identical. Writes keep your comments.
- Non-interactive runs (no TTY) stop after the preview unless you pass `--yes`.

## Sync

Every successful import registers its source in the profile's `import-sync.json`. `duckwork import-agent --sync` re-imports any registered source whose files changed, without prompts, so it fits a cron job:

- The change check is a digest over exactly the files the importer reads; credential files never trigger a sync.
- Skills previously imported are refreshed in place when the source copy changes, unless you edited the imported copy (then it is a conflict and left alone).
- A run with errors keeps the old digest, so the next sync retries.

`duckwork profile create <name> --clone --sync-imports` carries the manifest into a new profile, so `duckwork -p <name> import-agent --sync` keeps pulling from the same trees.

## Compatibility

On a Duckwork version that still has `import-agent` built in, this plugin's `import-agent` stays inert and the built-in command runs. Likewise, on a version that still has `duckwork claw` built in, the plugin registers neither `claw` nor its copy of the `openclaw-migration` skill; the built-in ones run.

## License

MIT
