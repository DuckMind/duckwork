# command-tray

Duckwork plugin: **shell commands this agent session actually ran** (`terminal`
tool — success and failure). Desktop pane + `/commands`. No API keys. Does not
re-execute commands; click inserts into the composer.

Repo: https://github.com/DuckMind/duckwork

Complements **debug-desk** (last failure only) and **file-tray** / **source-tray**.

## Install

```powershell
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable command-tray
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\command-tray" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\command-tray\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\command-tray\plugin.js" -Force
```

Restart Duckwork. Open the **command tray** pane. Status chip: `cmd N`.

1. Ask the agent to run a shell command (e.g. `pytest -q` or `dir`)
2. The command appears with `ok` / `fail` + exit code
3. Click to insert into the composer; **copy** as needed

Slash: `/commands`  `/commands clear`

State: `$DUCKWORK_HOME/plugin-data/command-tray/state.json`

## v1 rules

- Unique Python modules (`cmd_store`, not `store`)
- Unique commands, last 40; same command updates status / runs count
- Output preview truncated; tokens/secrets redacted
- Ignores non-terminal tools
- No network, no API keys
