<p align="center">
  <img src="../assets/mcp-serve.jpg" alt="MCP Serve plugin for Duckwork Agent" width="100%">
</p>

# MCP Serve

Part of [Duckwork Official Plugins](https://github.com/DuckMind/duckwork). Formerly built into Duckwork core as `duckwork mcp serve`.

Run Duckwork as an MCP server. Any MCP client (Claude Code, Claude Desktop, Cursor, Codex, your own harness) launches `duckwork mcp-serve` over stdio and gets your Duckwork messaging conversations as tools: list and read conversations across Telegram, Discord, Slack, WhatsApp, Signal, Matrix and the rest, poll or wait for new messages, send messages, and see approval requests. With `--tools` it also gets Duckwork' own web, browser, vision, image generation, skills and text-to-speech tools.

## Install

```bash
duckwork plugins install mcp-serve
# or straight from this repo (tracks main):
duckwork plugins install Fordex/duckwork-official-plugins#mcp-serve
```

## Connect an MCP client

```json
{
  "mcpServers": {
    "duckwork": {
      "command": "duckwork",
      "args": ["mcp-serve"]
    }
  }
}
```

Use `["-p", "<profile>", "mcp-serve"]` to serve another profile's conversations; the plugin must be installed in that profile too (`duckwork -p <profile> plugins install mcp-serve`).

**Coming from `duckwork mcp serve`?** Change the client's `args` from `["mcp", "serve"]` to `["mcp-serve"]`. The ten tool names, their parameters and descriptions are unchanged. On a Duckwork without the old command, `duckwork mcp serve` prints this new spelling and the install line.

## Tools

| Tool | What it does |
|---|---|
| `conversations_list` | Active conversations with their session keys, platform, chat type and last activity |
| `conversation_get` | One conversation's details |
| `messages_read` | Recent messages of a conversation |
| `attachments_fetch` | Images, media and other non-text parts of one message |
| `events_poll` / `events_wait` | New messages since a cursor; `events_wait` long-polls |
| `messages_send` | Send to `platform:chat_id` (or a channel name), through Duckwork' own send path |
| `channels_list` | Targets you can send to |
| `permissions_list_open` / `permissions_respond` | Approval requests seen during this session |

Messages come from the profile's `state.db`. Events start when the server starts; older history is read with `messages_read`. Reading needs no running gateway; `messages_send` does, since the platform connections live there.

## `--tools`: Duckwork' tools for other agents

```json
{ "command": "duckwork", "args": ["mcp-serve", "--tools"] }
```

Adds these Duckwork tools next to the bridge, using this profile's configured providers and credentials:

`web_search` · `web_extract` · `browser_navigate` · `browser_click` · `browser_type` · `browser_press` · `browser_snapshot` · `browser_scroll` · `browser_back` · `browser_get_images` · `browser_console` · `browser_vision` · `vision_analyze` · `image_generate` · `skill_view` · `skills_list` · `text_to_speech`

- **Off by default.** Without `--tools` the server exposes only the conversation bridge.
- **A fixed allowlist.** Terminal, file, code execution, process, kanban and delegation tools are never exposed, whatever the profile enables: they would hand the client a shell on your machine outside Duckwork' approval prompts (kanban tasks run as full agents).
- **No local files.** `browser_navigate` and `web_extract` take only web URLs (no `file:`), `vision_analyze` only web or `data:` images (no local paths), and `text_to_speech` writes only into Duckwork' own cache (its `output_path` is not offered). Web URLs include local-network addresses such as `localhost:3000`, as they do for the Duckwork model.
- **Your profile's choices apply.** Only toolsets enabled for the CLI in `duckwork tools` are offered, and a tool whose backend is not configured (no web provider, no image key, no local browser) is left out, the same availability rules the Duckwork model sees.
- **Your hooks still apply.** Shell hooks and plugin `pre_tool_call` hooks run around every call; `--accept-hooks` skips the first-use consent check for shell hooks, as it does for the gateway.
- Tool output is secret-redacted (`DUCKWORK_REDACT_SECRETS`), and calls cost whatever the configured provider charges.

## Options

```bash
duckwork mcp-serve                 # conversation bridge only
duckwork mcp-serve --tools         # plus Duckwork' tools (see above)
duckwork mcp-serve --verbose       # debug logging on stderr
```

The server is stdio only. Logs go to stderr; stdout is the MCP wire.

## Development

```bash
cd duckwork-official-plugins/mcp-serve
DUCKWORK_AGENT_REPO=$HOME/src/duckwork-agent PYTHONPATH=$HOME/src/duckwork-agent python -m pytest -q
```

MIT licensed. Built by [Fordex](https://fordex.com).
