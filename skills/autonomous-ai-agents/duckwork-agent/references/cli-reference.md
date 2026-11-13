# Duckwork CLI Reference

Live sources when anything looks stale: `duckwork --help`, `duckwork <command> --help`,
https://duckwork.fordex.ai/docs/reference/cli-commands

### Global Flags

```
duckwork [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
duckwork chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
duckwork setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
duckwork model                Interactive model/provider picker
duckwork fallback [add|remove|list]  Fallback provider chain
duckwork config [show|edit|get|set|unset|path|env-path|check|migrate]
duckwork login / logout       OAuth sign-in / clear stored auth
duckwork doctor [--fix]       Check dependencies and config
duckwork status [--full]      Component summary (--full: every section)
```

### Tools & Skills

```
duckwork tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

duckwork skills list|browse|search QUERY|inspect ID
duckwork skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
duckwork skills config        Enable/disable skills per platform
duckwork skills check|update|uninstall|publish PATH
duckwork skills tap add REPO  Add a GitHub repo as a skill source
duckwork bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
duckwork mcp add NAME (--url or --command) | remove | list | test NAME
duckwork mcp catalog | install NAME     Curated catalog install
duckwork mcp configure NAME             Toggle tool selection
duckwork mcp-serve                      Run Duckwork as an MCP server (mcp-serve plugin)
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
duckwork gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `duckwork photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://duckwork.fordex.ai/docs/user-guide/messaging/

### Sessions

```
duckwork sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
duckwork cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
duckwork webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
duckwork profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
duckwork profile rename A B | alias NAME | export NAME | import FILE
duckwork profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
duckwork auth                 Interactive credential manager
duckwork auth add [PROVIDER]  Add OAuth or API-key credential (fordex, openai-codex, qwen-oauth, …)
duckwork auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
duckwork desktop / gui        Native desktop app
duckwork dashboard            Web admin panel + embedded chat (--stop / --status)
duckwork proxy                OpenAI-compatible local proxy backed by an OAuth provider
duckwork portal               Quick setup / sign in via Fordex Portal
duckwork kanban <verb>        Multi-agent work-queue board
duckwork project              Named multi-folder workspaces
duckwork skin list|use|set    Switch/tweak skins (see references/themes.md)
duckwork pets <verb>          Pet mascots (see references/petdex.md)
duckwork memory setup|status|off|reset   Memory provider
duckwork secrets bitwarden|onepassword   External secret stores
duckwork moa                  Mixture-of-Agents slots
duckwork hooks / security / backup / import / checkpoints / console
duckwork logs [-f] [errors]   View agent/error logs
duckwork send                 One-off message through a gateway platform
duckwork pairing / plugins / insights / journey / computer-use
duckwork acp                  ACP server (IDE integration)
duckwork completion bash|zsh|fish
duckwork update / uninstall
```

Plugin- and provider-supplied subcommands (e.g. `duckwork photon setup`) only appear once their plugin is installed/active. Importing from OpenClaw, Claude Code, Codex CLI or Cursor (`duckwork import-agent <agent>`, plus the older `duckwork claw migrate|cleanup`) comes from the `agent-importers` plugin; a fresh `duckwork setup` that finds one of those agents offers to install it.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `duckwork config edit` · [Configuration docs](https://duckwork.fordex.ai/docs/user-guide/configuration) |
| Tools / toolsets | `duckwork tools list` · [Tools reference](https://duckwork.fordex.ai/docs/reference/tools-reference) |
| Skills catalog | `duckwork skills browse` · [Skills catalog](https://duckwork.fordex.ai/docs/reference/skills-catalog) |
| Provider setup | `duckwork model` · [Providers guide](https://duckwork.fordex.ai/docs/integrations/providers) |
| Env variables | `duckwork config env-path` · [Env vars reference](https://duckwork.fordex.ai/docs/reference/environment-variables) |
| Gateway logs | `~/.duckwork/logs/gateway.log` (or `duckwork logs`) |
| Sessions | `duckwork sessions browse` (reads state.db) |
