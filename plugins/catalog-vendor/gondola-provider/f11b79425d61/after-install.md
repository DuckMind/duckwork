# Gondola provider installed. One more step.

`duckwork plugins install` placed this plugin at a flat path
(`$DUCKWORK_HOME/plugins/gondola-provider/`), but Duckwork discovers model
providers only from `$DUCKWORK_HOME/plugins/model-providers/<name>/`. Until you
move the directory, `duckwork model` and `duckwork doctor` will not see Gondola.

**macOS / Linux / WSL:**

```bash
mkdir -p "$HOME/.duckwork/plugins/model-providers"
mv "$HOME/.duckwork/plugins/gondola-provider" \
   "$HOME/.duckwork/plugins/model-providers/gondola-provider"
```

(replace `$HOME/.duckwork` with `$DUCKWORK_HOME` if you set that variable)

**Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\duckwork\plugins\model-providers" | Out-Null
Move-Item "$env:LOCALAPPDATA\duckwork\plugins\gondola-provider" `
          "$env:LOCALAPPDATA\duckwork\plugins\model-providers\gondola-provider"
```

Then run `duckwork doctor`: Gondola should appear under API Connectivity.

**Simpler alternative:** skip `duckwork plugins install` entirely and clone this
repo straight into the target directory. See "Recommended install" in
README.md.
