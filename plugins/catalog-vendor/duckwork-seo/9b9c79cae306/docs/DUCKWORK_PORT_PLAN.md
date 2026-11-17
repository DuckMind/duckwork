# Duckwork SEO port plan

**Goal:** Preserve Claude SEO v2.4.2's SEO workflows, 26 skills, 19 specialist roles, scripts, and data as an installable Duckwork plugin.

**Architecture:** Use a standalone native Duckwork plugin with `register(ctx)`, namespaced skills, a CLI entry point that launches the existing isolated Python runtime, and a `transform_tool_result` hook for post-write JSON-LD feedback. Specialist roles become read-only plugin skills used through Duckwork `delegate_task`; network and paid API scripts remain explicit runtime commands.

**Validation:** Completed focused and full test suites, Duckwork `plugins validate` / `plugins doctor`, isolated plugin skill discovery, CLI/runtime setup, offline SEO workflow, Chromium rendering against `https://example.com`, and a real `transform_tool_result` schema-feedback hook check. No live provider API calls were made.

**Status:** Implementation and local integration verification are frozen. See [DUCKWORK_PORT_STATUS.md](DUCKWORK_PORT_STATUS.md) for exact commands, outputs, limitations, and install steps.

## Implementation checkpoints

1. Register all workflow and role skills, the isolated runtime CLI, and the non-blocking schema hook.
2. Replace Claude paths, tool names, and subagent language in skill content with Duckwork conventions; preserve MIT and CC BY 4.0 notices.
3. Remove Claude-only packaging and hook manifests; retain useful runtime, extensions, schemas, fixtures, and attribution.
4. Run plugin validation, runtime/security tests, and local integration checks; document install, optional services, credential limits, and verified coverage.
