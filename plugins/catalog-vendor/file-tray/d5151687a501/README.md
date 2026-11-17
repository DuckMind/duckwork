# file-tray

Duckwork plugin: **paths this agent session actually touched** (`read_file`,
`write_file`, `patch`). Desktop pane + `/files`. No API keys. Does not write
user files itself — only records paths.

Repo: https://github.com/DuckMind/duckwork

## Install

```powershell
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable file-tray
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\file-tray" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\file-tray\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\file-tray\plugin.js" -Force
```

Restart Duckwork. Open the **file tray** pane. Status chip: `ft N`.

1. Ask the agent to read or edit a file
2. Paths appear in the pane (`read` / `write` / `patch`)
3. Click a name to insert the path into the composer; **copy** / **reveal** as needed

Slash: `/files`  `/files clear`

State: `$DUCKWORK_HOME/plugin-data/file-tray/state.json`

## v1 rules

- Unique Python modules (`file_store`, not `store`)
- Unique paths, last 40; same path updates action + timestamp
- Ignores terminal / web tools (those are not file tools)
- No network, no API keys
