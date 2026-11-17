# Duckwork SEO port status

**State:** Duckwork SEO 0.1.0 is frozen pending independent review. Source: `claude-seo` v2.4.2, commit `4b99de2`. The upstream project remains attributed under MIT; preserved FLOW material retains its CC BY 4.0 attribution. No remote fork, push, publish, or catalog submission was performed.

## Ported package

The root `skills/` directory contains 26 registered SEO workflows and 19 registered specialist role skills. `plugin.yaml` and `__init__.py` provide native Duckwork registration, namespaced `skill_view` access, the credential-scoped `duckwork_seo_run` tool, the `duckwork seo` CLI, and a non-blocking JSON-LD feedback hook. Runtime scripts use an explicit allowlist and profile-local data/cache/venv paths. Claude-only marketplace manifests, installers, hooks, and settings mutators were removed. Optional provider prompts remain as companion references; only Banana has extension-specific helper scripts. See [EXTENSIONS.md](EXTENSIONS.md) for provider-by-provider scope and unsupported/unverified services.

## Reproduction and verification

The pre-tool port baseline recorded focused regressions at **11 passed** and the full suite at **866 passed, 0 failed, 6 skipped**. Catalog-readiness CI now installs the exact Duckwork 0.22.2 release on Linux and macOS, then runs `duckwork plugins validate . --install-deps --json` and `duckwork plugins doctor . --ci`. Both catalog gates pass locally in a temporary isolated Duckwork home, discovering one tool and one hook.

Duckwork validators: `duckwork plugins validate . --install-deps --json` and `duckwork plugins doctor . --ci`.

A temporary isolated profile was used; no regular user profile was modified. Duckwork discovered 45 skills (26 workflows + 19 roles), and `find_plugin_skill("duckwork-seo:seo")` resolved to the registered `skills/seo/SKILL.md`. `duckwork seo setup --skip-browser` left `browser_ready=false`; full `duckwork seo setup` installed isolated dependencies and Chromium. A caller-directory smoke of `duckwork seo run drift_report.py` succeeded with relative input and output paths. A separate read-only public render of `https://example.com` returned HTTP 200 with Chromium and no error. A real Duckwork-loaded `transform_tool_result` hook preserved a file-write result while reporting invalid JSON-LD schema feedback; the file remained present. The hook checks supported file-write calls that expose the target as `path` or `file_path`; edit variants without an explicit path are outside this check.

Security/packaging checks: a repository scan found no private home-directory or temporary smoke-test paths in active docs, skills, scripts, or plugin source. Historical project URLs/licensing and two historical `claude-seo` references in DataForSEO source context remain intentionally.

## Install and use

Follow the local-copy procedure in [INSTALLATION.md](INSTALLATION.md). Optional MCP servers are configured in the active profile's `~/.duckwork/config.yaml` under `mcp_servers` or through `duckwork config edit`; follow each provider's current official guide. Provider API compatibility, credentials, billing, and external side effects were not tested.
