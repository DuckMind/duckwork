# Handoff notes — duckwork-plugin-honcho

This repository is a **handoff copy** of the `honcho` memory provider that shipped inside
`Fordex/duckwork-agent` under `plugins/memory/honcho/`. Fordex is moving every memory
provider out of the core tree; this repo exists so the upstream project (<https://honcho.dev>)
can clone it, take ownership, and submit it to the [Duckwork plugin catalog](https://duckwork-agent.fordex.com/plugins)
under their own org. It is **not** an officially maintained Fordex plugin.

What it is: Honcho user-modelling memory.

## Install (as a user)

```
duckwork plugins install Fordex/duckwork-plugin-honcho
duckwork plugins enable honcho
duckwork memory setup            # or: set memory.provider: honcho in config.yaml
```

Dependencies in `pyproject.toml` are installed into the Duckwork venv automatically and survive
`duckwork update`.

## What changed versus the in-tree copy

Mechanical only; behaviour is identical.

- Absolute self-imports (`from plugins.memory.honcho.x import ...`) became relative imports so the
  package loads from `~/.duckwork/plugins/honcho/` under the loader's synthetic namespace.
- Shared helpers vendored: `_shared_query_rewrite.py` (were `plugins/memory/*.py`).
- Added `pyproject.toml` declaring: `honcho-ai>=2.2.0,<3`, `httpx>=0.27,<1`.

## For the maintainer taking this over

- `config_schema.py` still imports from `plugins.memory.config_schema`: Duckwork core loads that file
  directly and the dashboard expects core's `ProviderConfigSchema` type, so it must not be vendored.
- The in-tree `tools.lazy_deps.ensure("memory.honcho")` calls were removed: they pinned the exact
  (old) version in Duckwork' lazy-deps registry and downgraded newer installs (duckwork-agent#86992).
  `pyproject.toml` is now the only dependency authority; bump it when you need a newer client.
- The setup wizard imports private helpers from `duckwork_cli.memory_setup` (`_curses_select`,
  `_prompt`, ...). Those are Duckwork internals, not API; expect to own a copy or drop the wizard
  hook if they move.
- Tests were not copied: the in-tree tests import `plugins.memory.honcho` and depend on the
  duckwork-agent test harness. See `tests/plugins/memory/` in duckwork-agent for the originals.
- While the in-tree copy still exists, a same-named user plugin is shadowed by it
  (bundled providers win on name). It takes effect the moment core drops `plugins/memory/honcho`.

Original authors are preserved in duckwork-agent's history: `git log -- plugins/memory/honcho`.
