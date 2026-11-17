# Changelog

## v0.1.1

- **Plugin id is now `office-desk`.** `duckwork-office` is already taken by another plugin in the Duckwork plugin
  catalog, and Duckwork installs a plugin under its manifest name, so the two would collide. The repository keeps its
  name. Enable `office-desk` in `config.yaml`; an existing Desk in `plugin-data/duckwork-office` is still used.
- **Settings through Duckwork.** `plugin.yaml` declares `config_schema` (`folders`, `default_author`,
  `recalc_timeout`). Duckwork renders them under Desktop Settings > Plugins > office-desk and stores them under
  `plugins.entries.office-desk.settings`. The plugin has no settings UI of its own.
- Manifest: declares `provides_hooks` (`pre_llm_call`, `post_llm_call`), `author`, `homepage`, `api_version`.
- README: settings and a disclosure section (files, LibreOffice subprocess, session store, no network).

## v0.1.0

- First public release: 14 guarded Office tools, the Desk page, receipts and revert.
