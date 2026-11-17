# lib-docs

Duckwork plugin: **current library docs** from public **npm** and **PyPI**.
No API keys (Context7-style job without a Context7 account). Desktop pane +
`/docs`.

Repo: https://github.com/DuckMind/duckwork

Disclosure: HTTPS to `registry.npmjs.org` and `pypi.org` (package name /
version leave the machine). Optional README fallback via `cdn.jsdelivr.net`.

## Install

```powershell
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork plugins enable lib-docs
```

Copy the pane (Duckwork 0.21 installer may skip it):

```powershell
New-Item -ItemType Directory -Force -Path "$env:LOCALAPPDATA\duckwork\desktop-plugins\lib-docs" | Out-Null
Copy-Item "$env:LOCALAPPDATA\duckwork\plugins\lib-docs\desktop\plugin.js" "$env:LOCALAPPDATA\duckwork\desktop-plugins\lib-docs\plugin.js" -Force
```

Restart Duckwork. Pane: **lib docs**. Chip: `docs N`.

## Use

```
/docs react
/docs npm react
/docs pypi fastapi
/docs recent
```

`auto` probes **both** registries. If the name exists on npm and PyPI
(e.g. `react`), it prefers the likely ecosystem (scoped/`@` → npm,
`snake_case` → PyPI, otherwise npm) and adds a warning + `also_on`.
Force with `/docs npm …` or `/docs pypi …`. Slash replies use a markdown
summary (not a raw JSON dump).

Tools: `lib_docs_resolve`, `lib_docs_get`, `lib_docs_recent`.

Ask the agent: “fastapi Depends nasıl çalışır — lib-docs ile bak”.

State: `$DUCKWORK_HOME/plugin-data/lib-docs/recent.json`

## v1 rules

- Unique Python modules (`docs_store` / `docs_fetch`, not `store`)
- Stdlib `urllib` only (no httpx required)
- README truncated; no API keys
- Name-collision aware auto mode
- Not a substitute for private/internal docs
