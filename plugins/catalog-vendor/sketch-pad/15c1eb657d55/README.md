# sketch-pad

Duckwork Desktop plugin: **draw with the mouse**, Confirm, and the PNG attaches to
your **next chat message**. Ask "what is this shape?" when you have no photo.

Lives under `plugins/sketch-pad/` so it stays separate from debug-desk and
source-tray.

## Install (dev)

```powershell
duckwork plugins install C:\Users\aydin\Desktop\fordex-puling\plugins\sketch-pad
duckwork plugins enable sketch-pad
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\sketch-pad" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\sketch-pad\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\sketch-pad\plugin.js" -Force
```

Restart Duckwork. Open the **sketch pad** pane (right side, next to Source Tray).

1. Draw
2. **Confirm**
3. Type your question in chat and **Send** — the sketch is attached

Slash: `/sketch`

State: `$DUCKWORK_HOME/images/sketch_pad_*.png` (vision-readable). Plugin-data keeps a copy.

## v1 rules

- White pad, black pen
- Last confirmed PNG only
- Saved under `DUCKWORK_HOME/images` so `vision_analyze` can read it (not `plugin-data`)
- No screenshot of the OS desktop
- Unique Python modules (`sketch_store`, not `store`)
