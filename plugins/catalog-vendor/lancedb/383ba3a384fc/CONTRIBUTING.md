<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Contributing

Thanks for your interest in improving the LanceDB memory plugin for Duckwork Agent! Issues and PRs are welcome.

## Development setup

This repo isn't pip-installed — Duckwork loads it from its directory. For local development:

```sh
git clone https://github.com/DuckMind/duckwork
cd duckwork-agent-memory
uv sync --extra dev
```

The test suite imports a few Duckwork modules (e.g. `agent.memory_provider`, `tools.registry`), so it expects a **sibling Duckwork checkout** at `../duckwork-agent`:

```sh
git clone https://github.com/DuckMind/duckwork ../duckwork-agent
```

To wire the plugin into a live Duckwork for end-to-end testing, see the **Installation: developers** section of the [README](README.md) (symlink approach).

## Before you open a PR

Run lint and tests locally — they must pass, and CI runs the same checks:

```sh
uv run ruff check .
uv run pytest
```

Guidelines:

- Match the existing style: ruff, 100-char lines, type hints, `from __future__ import annotations`.
- Add or update tests for any behavior change. **Tests must run offline** — mock the embeddings/LLM client instead of calling a real API (see `tests/test_embeddings.py` for the pattern).
- Keep the plugin and the benchmark separate: code under `src/` must never import from `benchmarks/`.

## Versioning & releases

We follow [SemVer](https://semver.org). On a release:

1. Bump the version in **both** `pyproject.toml` and `plugin.yaml` (CI fails if they drift).
2. Add a `CHANGELOG.md` entry.
3. Tag the commit (`vX.Y.Z`) and cut a GitHub Release.

Because Duckwork installs the plugin by cloning `main`, keep `main` releasable at all times.

## Reporting issues

Use the issue templates. For bugs, include your Duckwork version, plugin version, OS/Python, the retrieval mode in use, and relevant `agent.log` lines plus your `duckwork memory status` output.
