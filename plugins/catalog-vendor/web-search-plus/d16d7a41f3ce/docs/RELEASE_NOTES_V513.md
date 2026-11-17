# Web Search Plus 5.1.3

Fixes found by testing like a normal user: a fresh Duckwork profile, default settings, real chats. No configuration changes are needed.

## Fixed

- **Upgrading from 5.0 no longer loses your key silently.** Keys in a `.env` in the plugin folder or in `~/.duckwork/plugins/` are not read under Duckwork since 5.1. `status` and `setup` now name that folder and the command to run (`duckwork config set BRAVE_API_KEY <key>`, then `/reload`). While that file is your only key source, `web_search_plus` and `web_extract_plus` stay available and answer with these steps instead of disappearing, so the model can tell you what to do. The file is only checked for existence, never opened. Once the keys are in your profile, `status` says the file can be deleted.

## Changed

- **Duckwork' own `web_search` can use your keys.** Duckwork shows its built-in `web_search` to the model and may hide plugin tools behind Tool Search, so with default settings the model often never calls Web Search Plus. With a key configured, `status` and `setup` now show how to route Duckwork' own tools through Web Search Plus:

  ```bash
  duckwork config set web.search_backend wsp
  duckwork config set web.extract_backend wsp   # with a key that can extract pages (Tavily, Exa, Linkup, ...)
  duckwork config set web.extract_backend exa   # search-only keys such as Brave: keep Duckwork' extraction
  ```

  `status` warns about the two setups that break extraction: search on `wsp` with no extract backend set (Duckwork then picks `wsp` for extraction too), and `web.extract_backend wsp` without a key that can extract pages. Web Search Plus never writes your Duckwork config.
- **Neutral tool description.** `web_search_plus` no longer tells the model to prefer Duckwork' `web_search`.
- `status --json` adds `legacy_env_files`, `native_backend_hint` and `duckwork_native.extract_backend_set`.

The MCP server and standalone CLI are unchanged.

Full list: [CHANGELOG](../CHANGELOG.md).
