# Duckwork SEO: agent instructions

This is a local Duckwork port of AgriciDaniel/claude-seo v2.4.2. It is a native Duckwork plugin, not a Claude Code plugin.

## Package structure

- `plugin.yaml` and `__init__.py`: Duckwork plugin manifest and `register(ctx)` integration.
- `skills/seo-*/SKILL.md`: 26 SEO workflows registered as `duckwork-seo:seo-*` plugin skills.
- `skills/role-seo-*/SKILL.md`: 19 specialist roles for Duckwork `delegate_task` calls.
- `scripts/`: 56 bundled utilities and a stdlib-only isolated runtime launcher.
- `schema/`, `data/`, `extensions/`, `assets/`: templates, source data, optional integrations, and assets.
- `hooks/validate-schema.py`: JSON-LD validator used by the Duckwork `transform_tool_result` hook.

## Runtime rules

- Run bundled Python only through `duckwork seo run <script.py>`; never use global Python for plugin utilities.
- Run `duckwork seo doctor --json` before work requiring the managed environment. Setup is user-initiated because it downloads dependencies and Chromium.
- Load bundled skill material using `skill_view(name="duckwork-seo:seo-*", file_path="references/<file>")`; use `duckwork seo show <relative-path>` only for non-skill bundled files.
- Use native Duckwork tools (`read_file`, `write_file`, `patch`, `search_files`, `terminal`, `web_search`, `web_extract`, `delegate_task`). Invoke workflow skills by their `duckwork-seo:seo-*` namespaced names.
- Delegate specialist work with `delegate_task`, asking the child to load `duckwork-seo:role-seo-*`; run sequentially if delegation is unavailable.
- Never invoke cost-bearing API operations without explicit user approval. Do not read secrets from config files; use configured MCP providers or the supplied credential utility.
- Do not make live network calls in tests. Preserve SSRF checks and avoid storing runtime state in the plugin install tree.

## Licensing and validation

Keep the upstream MIT license and contributor attribution. FLOW prompt materials remain CC BY 4.0. Validate changes with `duckwork plugins validate`, `duckwork plugins doctor --ci`, and relevant `rtk pytest` suites.
