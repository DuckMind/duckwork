<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Contributing

Thanks for considering a contribution to **duckwork-rtk-rewrite**, a community (non-official)
Duckwork plugin for **RTK** ([`rtk-ai/rtk`](https://github.com/rtk-ai/rtk), Apache-2.0).

## Development gates

Every change must pass:

- `duckwork plugins validate --json .` — the catalog admission gate.
- `python3 -m unittest discover -s tests -q` — the unit suite.
- `bash -n` on every `*.sh`, and `python3 -m py_compile` on every `.py`.
- The CI workflow (`duckwork plugins validate` + shell syntax + python compile).
- The security workflow (Gitleaks + ShellCheck, error severity only).

## What is mirrored, and what is not

`__init__.py`, `tests/` and `upstream/plugin.yaml` are mirrors of upstream
`rtk-ai/rtk` → `hooks/duckwork/` (Apache-2.0). Do not rewrite them to taste: run
`scripts/sync-upstream.sh`, re-apply the local `tests/` layout fix
(`_PLUGIN_CANDIDATES` in `tests/test_rtk_rewrite_plugin.py`), and commit the diff. Everything
else (`plugin.yaml`, `desktop/`, `docs/`, `scripts/update.sh`) is maintained here.

The rewrite rules themselves belong upstream in Rust. If a command rewrites badly, that is an
upstream issue — this plugin has no rule engine and should not grow one.

## Pull requests

- Keep the plugin a community helper: no secrets, no private local paths, no hostnames, no
  personal operational logs.
- User-facing strings in English.
- Keep the plugin fail-open: never make a failing `rtk` call block or abort a command.
- Bump `version` in `plugin.yaml`, update the footer in `desktop/plugin.js`, and add a
  `CHANGELOG.md` entry.
