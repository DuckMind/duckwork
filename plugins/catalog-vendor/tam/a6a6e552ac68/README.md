# tam — total-agent-memory for Duckwork

Long-term memory for Duckwork Agent backed by
[total-agent-memory (TAM)](https://github.com/vbcherepanov/total-agent-memory), over MCP.

- Saves each completed turn (user message + final reply; no tool output) to TAM, skipping trivial
  prompts and very short exchanges. TAM's quality gate, when enabled, has the final say.
- Before each turn, recalls relevant memories from TAM within a token budget.
- Tools: `tam_recall` (search) and `tam_save` (store a durable fact, decision, solution, lesson or convention).
- Shares one store with other agents on the same TAM (Claude Code, Codex CLI, Cursor, ...).

**Local-first.** By default Duckwork starts your installed `tam` binary (MCP stdio), so data stays on
your machine. The spawned process gets a reduced environment with no credentials (no Duckwork provider keys, no
`*_TOKEN` / `*_API_KEY` / `*_SECRET` variables). Remote mode connects
to a TAM HTTP endpoint or a TAM team server (URL + optional `TAM_API_TOKEN`) for shared team memory.

## Quick start

```bash
pipx install total-agent-memory        # provides the `tam` command
duckwork plugins install tam
duckwork memory setup tam                # local/remote, command, data dir, project; tests the connection
duckwork memory status
```

The plugin has no Python dependencies and never crashes Duckwork: if TAM is missing or slow, the
recall for that turn is empty, saves are queued with retry, and shutdown waits a bounded time.

Configuration reference, privacy details and the team-server walkthrough:
https://github.com/DuckMind/duckwork

MIT © 2026 Vitalii Cherepanov
