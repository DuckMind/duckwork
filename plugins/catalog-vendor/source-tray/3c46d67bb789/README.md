# source-tray

Duckwork plugin: **URLs this agent session actually opened** (`web_search`, `web_extract`, `browser_navigate`). Desktop pane + `/sources`. Not a search engine.

Lives under `plugins/source-tray/` in the fordex-puling workspace so it stays **separate from debug-desk**. Catalog ships as a YAML pin later (`category: web`) via https://github.com/DuckMind/duckwork — not as plugin code in Fordex core.

## Install (dev)

```bash
duckwork plugins install ./plugins/source-tray
duckwork plugins enable source-tray
```

Restart the gateway. Desktop: **Capabilities → Plugins → Source Tray**.

```
/sources
/sources clear
```

Tools: `source_tray_list`, `source_tray_clear`.

State: `$DUCKWORK_HOME/plugin-data/source-tray/state.json`.

## v1 rules

- Deterministic. No LLM.
- Unique URLs, last 40, newest overwrite the same URL
- Does not scrape every link inside extracted page bodies
