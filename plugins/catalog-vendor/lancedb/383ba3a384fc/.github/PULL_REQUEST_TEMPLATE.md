<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
## What this changes

<!-- A short description of the change and why it's needed. Link any related issue. -->

## Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest` passes (with a sibling `../duckwork-agent` checkout)
- [ ] Added/updated tests for behavior changes (offline, mocked — no real API calls)
- [ ] Updated docs (README / config reference) if behavior or config changed
- [ ] If this is a release: bumped the version in both `pyproject.toml` and `plugin.yaml`, and updated `CHANGELOG.md`
