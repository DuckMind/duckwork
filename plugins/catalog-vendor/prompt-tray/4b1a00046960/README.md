# prompt-tray

Duckwork Desktop plugin: **saved chat prompts**. Click one, it lands in the composer.
Ships with Review / Plan / Explain; add your own. No API keys.

Lives under `plugins/prompt-tray/` so it stays separate from debug-desk.

## Install (dev)

```powershell
duckwork plugins install C:\Users\aydin\Desktop\fordex-puling\plugins\prompt-tray
duckwork plugins enable prompt-tray
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\prompt-tray" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\prompt-tray\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\prompt-tray\plugin.js" -Force
```

Restart Duckwork. Open the **prompt tray** pane.

1. Click **Review** / **Plan** / **Explain** (or your own)
2. Text appears in the chat box (paste with Ctrl+V if it does not)
3. Edit if you want, then Send

Slash: `/prompts`

State: `$DUCKWORK_HOME/plugin-data/prompt-tray/prompts.json`

## v1 rules

- Click inserts; it does not auto-send
- Unique Python modules (`prompt_store`, not `store`)
- Max 40 prompts, no LLM rewrite
