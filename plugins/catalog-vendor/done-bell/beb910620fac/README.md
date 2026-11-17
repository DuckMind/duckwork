# done-bell

Duckwork plugin: **ring when a turn finishes** so you can leave the window.

OS notification (when away), optional chime, status chip (`busy` / `done` /
`needs you`). No API keys. Does not send chat, write code, or touch user files.

Lives under `plugins/done-bell/` so it stays separate from debug-desk.

Repo: https://github.com/DuckMind/duckwork

## Install (dev)

```powershell
duckwork plugins install C:\Users\aydin\Desktop\fordex-puling\plugins\done-bell
duckwork plugins enable done-bell
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\done-bell" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\done-bell\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\done-bell\plugin.js" -Force
```

Restart Duckwork. Status bar chip: `busy` while working, `done` when idle.

1. Send a chat, switch to another window
2. When the turn finishes you get an OS notify + chime
3. If Duckwork waits for approval, the chip says `needs you`

Slash: `/bell`  `/bell mute`  `/bell unmute`

Pane: **done bell** — toggles and **Test bell**.

State: `$DUCKWORK_HOME/plugin-data/done-bell/bell.json`

## v1 rules

- Unique Python modules (`bell_store`, not `store`)
- Desktop watches `host.state.busyBySession` (gateway turns)
- CLI/TUI also ring via `on_session_end` (no double OS toast on gateway)
- Commands in approval hooks are not stored (secrets)
