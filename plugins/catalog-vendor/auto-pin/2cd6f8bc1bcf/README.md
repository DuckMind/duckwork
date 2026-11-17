# duckwork-plugin-auto-pin

A [Duckwork Agent](https://github.com/DuckMind/duckwork) plugin that pins every new
interactive session automatically, so the sessions you start from the desktop app, the CLI or
the TUI are always at the top of the sidebar without a manual click.

## Behaviour

| Session | Pinned? |
|---|---|
| New top-level session from `desktop`, `cli` or `tui` | yes |
| A branch you fork from one of those | yes |
| Cron, one-shot, API server and messaging-platform sessions | no |
| Subagent / delegate children, compression continuations | no (a continuation inherits the lineage pin) |
| Hidden or archived rows | no |
| Any session that started more than an hour ago | no |

Each automatic pin is recorded once in `<duckwork home>/auto-pin/ledger.txt`, so a session is
decided exactly once: **if you unpin it, it stays unpinned**, even if the session is resumed.
The ledger also lets other tooling distinguish an automatic pin from one you made by hand.

## Install

```bash
duckwork plugins install auto-pin     # from the plugin catalog, once listed
# or, from this repo:
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable auto-pin
```

Restart the desktop backend / gateway if it was already running so it loads the hook.

## What it touches (disclosure)

- Hook: `on_session_start` only. No tools, no middleware, no environment variables, no network.
- Reads the new session's row from the local session database and calls
  `SessionDB.set_session_pinned(session_id, True)` -- the same setter the sidebar pin button uses.
  The shared database handle comes from `duckwork_state_registry.acquire()` / `release()`, which is not
  a documented plugin API yet (`duckwork plugins validate` reports it as a warning, not a failure).
- Writes one short line per pinned session to `<duckwork home>/auto-pin/ledger.txt`.
- Any failure is logged and swallowed; the session simply stays unpinned.

## Configuration

None. The set of pinned sources (`desktop`, `cli`, `tui`) and the one-hour freshness window are
constants at the top of `core.py`.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

MIT
