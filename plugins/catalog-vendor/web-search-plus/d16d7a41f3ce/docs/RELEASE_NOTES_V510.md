# Web Search Plus 5.1.0

Provider keys now come through Duckwork. Web Search Plus reads them from your active Duckwork profile and no longer reads `.env` files itself, as the Duckwork plugin catalog requires (rule 11).

## Breaking changes

- **Keys come from your Duckwork profile only.** Keys kept only in the plugin folder's `.env` or in `~/.duckwork/plugins/.env` are no longer seen. Move each one into your profile:

  ```bash
  duckwork config set BRAVE_API_KEY <key>
  duckwork web-search-plus status
  ```

  Duckwork Desktop has the same fields under Settings > Plugins > Web Search Plus and keeps keys out of your shell history. Keys already in `~/.duckwork/.env` keep working unchanged.
- **Setup runs inside Duckwork.** `duckwork web-search-plus status` and `duckwork web-search-plus setup` show which keys the active profile sees and print the `duckwork config set` command for each missing one. Setup no longer asks for keys or writes `.env` files; routing preferences, keyless opt-ins and the Jev switch still go to `plugins/config.json`. `python3 setup.py status|setup|bench` point to the Duckwork commands.
- **Jev reads `TYPESAFE_API_KEY` only.** `TYPESAFE_API_KEY_FILE`, `--jev-key-file` and `jev.api_key_file` are ignored.
- **The standalone `search.py` does not read `.env` files.** Export the keys first: `set -a; . ~/.duckwork/.env; set +a`.

## When a key change applies

- On the gateway (Telegram, Discord, API), a new or changed key applies from your next message.
- In the interactive CLI, run `/reload` first.
- To switch a provider off, set its key to an empty value (`duckwork config set BRAVE_API_KEY ""`). A removed line (`duckwork config unset`) of a key Duckwork does not know by name stays active until Duckwork restarts.

## Changed

- On a multiplexing Duckwork gateway each profile sees only its own keys, including in fallback and research worker threads. A read without a profile scope reports Duckwork' own error instead of "no provider configured".
- Duckwork Desktop settings gain a TypeSafe key field and a DonSeTch binary path field.
- Duckwork builds without `agent.secret_scope` fall back to the process environment.

## Fixed

- **Research mode says why a provider was skipped**, for example "Out of credits or quota at its last call", instead of "Provider attempt did not return a payload".
- **Key hints** in `status`, `setup` and provider errors say when a new key applies instead of recommending `/reset`, which does not reload keys.
- **Brave's real query limit.** Queries are shortened only past Brave's documented 600 characters and 75 words; 5.0.1 cut at 400 characters and 50 words.

Full list: [CHANGELOG](../CHANGELOG.md).
