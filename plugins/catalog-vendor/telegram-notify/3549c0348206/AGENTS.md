# Duckwork Telegram Notify Development Guide

This repository is a standalone Duckwork Agent native plugin. Keep the project
independently installable: the plugin root must retain `plugin.yaml` and
`__init__.py`, and the runtime implementation lives in
`duckwork_telegram_notify/`.

## Safety rules

- Never print, commit, test-fixture, or send the Telegram bot token.
- Do not read arbitrary Duckwork configuration into Telegram messages.
- Hook callbacks are observers and must remain fail-open: Telegram/network
  failures must never abort the Duckwork turn.
- Use `get_duckwork_home()` for persistent profile-scoped files.
- Use `scripts/run_tests.sh` from the Duckwork checkout for integration tests;
  local unit tests may be run with the Duckwork virtualenv and pytest.

## Verification

Run the unit suite from the repository root:

```bash
python -m pytest -q
```

After edits, load the installed plugin through `duckwork plugins doctor` and
exercise hooks through Duckwork' `PluginManager.invoke_hook` rather than only
calling formatter functions.
