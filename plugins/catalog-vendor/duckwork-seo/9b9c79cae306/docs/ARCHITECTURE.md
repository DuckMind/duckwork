# Architecture

Duckwork SEO is a standalone native plugin. Duckwork loads `plugin.yaml`, imports `__init__.py`, registers all bundled workflow and role skills through `ctx.register_skill()`, exposes the `duckwork seo` CLI tree, and installs a `transform_tool_result` hook for JSON-LD feedback after file-write tools.

The 26 source workflows live in `skills/seo-*/`; reference material stays alongside the owning skill and is loaded through `skill_view(name="duckwork-seo:seo-*", file_path="references/<file>")`. The 19 former specialist agents are converted to `skills/role-seo-*/SKILL.md` and are delegated with the existing `delegate_task` tool. Duckwork does not register them as a separate agent type; each delegated task should explicitly load its matching role skill and receive its goal, relevant evidence, and output location in `context`.

The 56 Python utilities keep their original domain behavior. `scripts/duckwork-seo` dispatches allowlisted offline scripts through `scripts/runtime.py`, which creates a managed virtual environment and browser under Duckwork plugin data storage. Credentialed scripts use `duckwork_seo_run`; it resolves only the selected script's allowlisted names from the active Duckwork profile vault and starts the child in the Duckwork host plugin process. It does not inherit a Docker terminal's isolation, and script arguments may reference host paths visible to that process. Skills request user approval before paid, external, or mutating calls; the tool does not implement an approval gate.

The registration layer currently imports the private Duckwork core helper
`plugins.plugin_storage.plugin_data_dir` because no public profile-aware storage
resolver was found in Duckwork 0.22.2. Maintainers must recheck that import when
raising `requires_duckwork`; it is not a stable public plugin API.

Optional integrations are preserved under `extensions/` as script/resource packages. Their former installers and MCP mutations were Claude-specific and are removed. Users configure MCP servers using Duckwork configuration and provider documentation; no API connection is assumed by plugin discovery or local validation.

The post-write hook checks JSON-LD in HTML-like files through `validate_jsonld()`. It adds findings to the tool result after the file is written, so it is advisory and cannot undo changes.

```text
Duckwork PluginManager
  └─ register(ctx)
      ├─ 26 workflow skills ──┐
      ├─ 19 role skills ──────┼─ skills_list / skill_view
      ├─ duckwork seo CLI       ├─ isolated offline runtime
      ├─ duckwork_seo_run       ├─ host credentialed subprocess
      └─ transform hook ──────┘  JSON-LD feedback
```

See [installation and verification](../README.md), [extension notes](EXTENSIONS.md), and [the port plan](DUCKWORK_PORT_PLAN.md).
