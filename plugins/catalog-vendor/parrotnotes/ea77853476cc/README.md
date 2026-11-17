# ParrotNotes plugin for AI agents

Work with your [ParrotNotes](https://parrotnotes.app) in-person meeting notes from inside your AI agent. Ask for your latest meeting, search a transcript, pull out action items, or save a summary back to the note.

ParrotNotes is an AI note-taker for in-person meetings. It records in the background on iOS, Android and macOS with no meeting bot, then turns each conversation into a transcript, summary and action items.

One install ships:

- The hosted ParrotNotes MCP server (`parrotnotes`) at `https://mcp.parrotnotes.app/mcp`, over Streamable HTTP.
- `skills/parrotnotes/`, the workflow skill: how to find the right note, which of the two note IDs each tool takes, when to reuse a saved insight, and when to ask before overwriting one.

ParrotNotes signs in with OAuth 2.0 and Dynamic Client Registration. There is no API key, and nothing secret lives in this repository. On first use your agent opens `https://parrotnotes.app/auth/authorize` in the browser: sign in and approve access.

## Duckwork Agent

```bash
duckwork plugins install parrotnotes          # from the Duckwork plugin catalog
duckwork plugins enable parrotnotes
```

Before the catalog listing is live, install straight from GitHub with `duckwork plugins install ascetx/parrot-notes-duckwork-plugin --no-enable`, then enable it the same way.

The Agent Plugins v1 `mcp.json` format has no field for OAuth, so tell Duckwork once that this server signs in with OAuth:

```bash
duckwork mcp add parrotnotes --url https://mcp.parrotnotes.app/mcp --auth oauth
duckwork mcp login parrotnotes
```

Start a new Duckwork session afterwards. Tokens are cached under `~/.duckwork/mcp-tokens/` and refresh on their own. Your `config.yaml` entry and the plugin's `mcp.json` entry share the name `parrotnotes`, and the config entry wins. The plugin still supplies the skill. On a headless host, see Duckwork' [OAuth over SSH guide](https://duckwork-agent.fordex.com/docs/guides/oauth-over-ssh#mcp-servers).

## Claude Code

```bash
claude plugin marketplace add ascetx/parrot-notes-duckwork-plugin
claude plugin install parrotnotes@parrotnotes
```

Or inside a session: `/plugin marketplace add ascetx/parrot-notes-duckwork-plugin`, then `/plugin install parrotnotes@parrotnotes`. Claude Code runs the OAuth sign-in the first time a ParrotNotes tool is used, or run `/mcp` to sign in straight away.

On claude.ai and the Claude apps, add ParrotNotes from the [Claude directory](https://claude.ai/directory/parrotnotes) instead.

## Codex

```bash
codex plugin marketplace add ascetx/parrot-notes-duckwork-plugin
codex plugin add parrotnotes@parrotnotes
codex mcp login parrotnotes
```

## GitHub Copilot CLI

```bash
copilot plugin marketplace add ascetx/parrot-notes-duckwork-plugin
copilot plugin install parrotnotes@parrotnotes
```

## Any other MCP client

Add `https://mcp.parrotnotes.app/mcp` as a remote (Streamable HTTP) MCP server with OAuth. It is listed in the [official MCP Registry](https://registry.modelcontextprotocol.io/v0.1/servers?search=app.parrotnotes) as `app.parrotnotes/parrotnotes`. To add only the skill to an Agent Skills client, run `npx skills add ascetx/parrot-notes-duckwork-plugin`. Per-client setup: https://parrotnotes.app/docs/mcp

## Try it

- "Summarize my most recent ParrotNotes meeting notes and list the action items."
- "Find my notes from the Henderson site visit and give me the key points."
- "What did the client commit to on Tuesday's call? Save that back as action items."
- "List everything I've labelled project-alpha."

## Tools

Duckwork exposes each tool as `mcp__parrotnotes__<tool>`.

| Tool | What it does | Access |
|---|---|---|
| `get_recent_notes` | Lists your most recent notes, with pagination and an audio/text filter | Read |
| `search_notes` | Full-text search across titles, transcripts and text | Read |
| `get_note` | Returns one note with its full transcript and content | Read |
| `get_note_insights` | Returns insights saved against a note: summaries, action items, sentiment | Read |
| `get_user_labels` | Lists your labels | Read |
| `get_note_labels` | Returns the labels on one note | Read |
| `get_notes_by_label` | Returns the notes carrying one label | Read |
| `get_subscription_status` | Returns your plan status and expiry | Read |
| `save_note_insight` | Saves an insight against a note you own | **Write** |

Eight of the nine tools are read-only. `save_note_insight` is the only one that changes data. It can replace an existing insight of the same type and language, and the skill tells Duckwork to confirm with you first. Nothing is ever deleted.

## Requirements

- A ParrotNotes account. The free tier works.
- At least one note, made in the ParrotNotes app. This plugin reads your existing notes and cannot create new ones.

## Privacy and security

- Every query is scoped to the signed-in user through Postgres row level security. A session cannot reach another account's data.
- Transport is HTTPS only. Expired or revoked tokens get a `401` with `error="invalid_token"`, and Duckwork prompts you to sign in again.
- Your data is not used to train AI models.
- The plugin has no Python code, hooks or environment variables, and it does not update itself.
- Full policy: https://parrotnotes.app/privacy

## Troubleshooting

**Tools fail with 401 or "unauthorized".** Run `duckwork mcp login parrotnotes`. Signing out of ParrotNotes on the web with a global scope ends every session for your account, including this one.

**Tools return empty results.** The account has no notes yet. Record or import something in the app first.

**The skill can't find its tools.** Run `duckwork mcp test parrotnotes`, then start a new session.

## Support

- Email: support@parrotnotes.app
- Setup for other clients: https://parrotnotes.app/docs/mcp
- Terms: https://parrotnotes.app/terms

## License

This repository (plugin manifests, skill and docs) is MIT licensed. The hosted ParrotNotes service and MCP server are separate and governed by the [ParrotNotes terms](https://parrotnotes.app/terms).
