# Duckwork Windows ops

Agent skills for triaging Duckwork on Windows and under WSL: the failures that do
not happen on macOS or Linux, and the evidence that tells them apart.

- **duckwork-windows-triage** — background processes that survive a quit, WSL to
  Windows interop where an argument reaches `cmd.exe` as shell syntax, config
  and encoding failures (UTF-8 BOM, legacy code pages), long-path and
  reserved-name errors, and terminal differences. Ships with a copy-paste
  command reference.

The package adds **instructions only**: no model tools, no hooks, no daemon, no
network calls, no credentials, and no replacement harness. It uses the host's
existing terminal and approval flow. Nothing here installs or upgrades software
on its own; where a fix would change the user's machine, the skill says to
propose it and ask.

## Why this is a plugin and not a bundled skill

The failure modes it covers come from real reports (#131561, #132069, #61059)
and were re-verified against current `main`. Windows continues to produce new
ones, and the Windows surface changes faster than the bundled skill set — a
plugin can be re-pinned as it grows, without waiting on a Duckwork release. The
developer-facing Windows notes that already live in the bundled `duckwork-agent`
skill (`references/windows-quirks.md`) are referenced, not duplicated.

## Install

```sh
duckwork plugins install duckwork-windows-ops
duckwork plugins list
duckwork plugins enable duckwork-windows-ops
```

Start a new session so the skill is indexed. To remove it:
`duckwork plugins uninstall duckwork-windows-ops`.

Try:

> Duckwork left a pile of python processes behind after I quit it on Windows. Use
> duckwork-windows-triage to find out which of them are actually orphaned before
> killing anything.

Or, when a link open behaves like a command line:

> On WSL, opening a link with an `&` in it ran something else. Walk
> duckwork-windows-triage's interop section and tell me what to capture.

## Disclosure

- **Reads:** process tables (`Win32_Process`), the Duckwork config it is asked to
  inspect, and the file headers of the same file. Nothing outside the paths a
  user names.
- **Writes:** nothing. The two destructive commands in the reference file
  (killing a process or a tree) are marked and gated on asking first.
- **Network:** none.
- **Credentials:** none; the skill never reads `.env` files, `auth.json`, or
  any credential store.

## License

MIT — see `LICENSE`.
