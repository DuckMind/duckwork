---
name: diagnosing-plugins
description: Diagnose Duckwork plugins that do not load or run — the plugins.enabled opt-in gate, capability consent, discovery locations, and sub-category selection keys.
version: 1.2.13
metadata:
  duckwork:
    tags: [duckwork, plugins, troubleshooting]
    related_skills: [duckwork-configuration-guide, diagnosing-host-pressure]
---

# Diagnosing Plugins

A Duckwork plugin is a **Python package**: a directory with a `plugin.yaml` manifest and a `register(ctx)` function. The single most common failure: **the plugin is discovered but not enabled** — Duckwork deliberately loads nothing from third-party code until you add it to `plugins.enabled`.

> **Disambiguation**: if a provider sub-category (e.g. `context.engine`, `image_gen.provider`) is misconfigured, see `diagnosing-providers` — that is a provider configuration problem, not a plugin-loading problem.

## 1. Discovery locations (later sources override same-name earlier ones)

| Source | Path | Gate |
|---|---|---|
| Bundled | `<install>/plugins/` | Platform/backend sub-plugins auto-load; bundled standalone plugins still need opt-in |
| User | `$DUCKWORK_HOME/plugins/<name>/` | `plugins.enabled` allow-list |
| Project | `<repo>/.duckwork/plugins/` | Requires `DUCKWORK_ENABLE_PROJECT_PLUGINS=true` at startup |
| pip | `duckwork_agent.plugins` entry points | `plugins.enabled` |
| Nix | `services.duckwork-agent.extraPlugins` | Nix config |

`duckwork plugins install owner/repo [--ref <40-char SHA>] [--enable|--no-enable]` installs from Git (pinned commits only); `duckwork plugins update` refuses to move a pinned plugin. Sub-category directories have their **own loaders and selection keys** — they do not obey `plugins.enabled`. Verified present at current main: `platforms/<name>/` (messaging channels, gated per messaging platform in config), `memory/<name>/` (one active, `memory.provider`), `context_engine/<name>/` (`context.engine`), `model-providers/<name>/` (picked via `--provider`/config), `image_gen/<name>/` (`image_gen.provider`), plus `browser/`, `video_gen/`, `cron_providers/`, `dashboard_auth/`, `web/`, `computer_use/` (`plugins/computer_use/__init__.py`: bundled `plugins/computer_use/<name>/` providers plus the built-in `cua` driver, one active), and `delegation/` (`delegation.backend` selects the bundled strategy; the `default` strategy then reads `delegation.provider` / `model` / `base_url`; `plugins/delegation/default/plugin.yaml`). **`observability/` is not one of these** — it was listed here from v2026.9.11 until 2026-10-19 but `plugins/observability/` exists neither at the pinned baseline nor at upstream main. **Not every bundled entry auto-loads:** upstream's discovery reports disabled bundled plugins as *"not enabled in config (run `duckwork plugins enable <key>` to activate)"* (`duckwork_cli/plugins_discovery.py`), and bundled Kanban is one of them — check `duckwork plugins list` for the real state instead of assuming a bundled directory is live. **The set grows — list `plugins/` in the installed source instead of trusting this list.**

## 2. The enable gate and capabilities

```yaml
plugins:
  enabled: [my-plugin]
  disabled: [noisy-plugin]   # deny-list always wins over enabled
```

Three ways to flip: `duckwork plugins` (interactive), `duckwork plugins enable <name>`, `duckwork plugins disable <name>`. Declared capabilities require a separate one-time consent recorded under `plugins.entries.<id>.granted_capabilities` (legacy `allow_*` keys are still read). Verified capability ids at current main: **`tools.override`** and **`gateway.platform_actions`** — this list is code-defined and grows, so check `plugin_capability_granted()` / `ctx.has_capability()` rather than trusting any doc (an earlier revision of this skill named a `llm.model_override` id that **does not exist**). Two behaviours worth knowing: **bundled plugins are trusted for `tools.override`** (no consent needed), and unknown ids or unreadable consent **fail closed** (False). **Non-interactive installs/enables grant nothing** — the plugin runs with capabilities off and must degrade gracefully (`ctx.has_capability()`).

## 3. How to inspect

- `duckwork plugins` — interactive UI (SPACE toggles enabled).
- `duckwork plugins list` — enabled / disabled / not-enabled per plugin.
- `duckwork plugins capabilities [name]` — declared vs granted.
- `/plugins` in chat — status listing.
- `duckwork logs --follow` — a plugin whose `register()` raises is skipped with a logged error (never crashes Duckwork), so read the log for load failures.

## 4. Pitfalls (symptom → cause → fix)

1. **Installed but tools/hooks/commands absent** — not in `plugins.enabled` (install defaults to disabled; `--enable` or the post-install prompt is opt-in). → **Permanent:** add it to `plugins.enabled` (`duckwork plugins enable <name>`) and restart. **Temporary:** there is no read-only way to load a disabled plugin — enabling is the fix, so do it deliberately rather than working around it. Bundled standalone plugins are opt-in too — only platform/backend sub-plugins auto-load.
2. **Plugin works but a privileged feature is off** — capability declared but never granted (non-TTY install, or declined). → `duckwork plugins capabilities <name>`; re-consent via interactive `duckwork plugins enable <name>`.
3. **Project plugin ignored** — `.duckwork/plugins/` is disabled by default. → Set `DUCKWORK_ENABLE_PROJECT_PLUGINS=true` before starting Duckwork, and only for trusted repos.
4. **Plugin in `list` but nothing loads at all** — `register()` raised (bad code, missing dependency). → Check `duckwork logs` for the load error; fix the plugin or its requirements. If the log instead says `load timed out after Ns` (optionally followed by `called register_*() after its load timed out; ignored`), the loader's own budget expired before `import()` + `register()` returned. That budget covers the **plugin's** work as much as the host's, so the message alone does not tell you which one was too slow — a slow import or a blocking `register()` reaches the same deadline on a healthy host. Compare the configured `plugins.load_timeout_seconds` against what that plugin's import and `register()` actually do, and run `diagnosing-host-pressure` (`bash skills/diagnosing-host-pressure/scripts/host_pressure_probe.sh`) to rule the host in or out. Only treat it as host pressure once the probe says so. Re-run the same load once before blaming either side: a cold first load — fresh install, pin change, empty caches — can exceed the default on a slow host and pass on immediate retry. The loader's per-plugin budget is configurable: `plugins.load_timeout_seconds` in `config.yaml` (default 10; negatives and non-numbers fall back to 10 with a warning; values above 600 clamp to 600; `0` disables the deadline and loads the plugin inline) — raise it or set it to `0` only once the probe or a repeated pattern establishes the cause, then restart.
5. **Edits to a bundled plugin don't apply** — a same-name user plugin at `$DUCKWORK_HOME/plugins/<name>/` overrides the bundled copy. → Edit the user copy (the one that actually wins) or remove it.
6. **`duckwork plugins update` refuses** — the install is pinned to an exact commit SHA. → Choose a new commit explicitly: `duckwork plugins install <source> --force --ref <new-sha>`.
7. **Plugin edits after install lost on update** — updates autostash and re-apply local edits, but conflicts can drop them. → Keep plugin customizations in your own fork/repo and install from that.
8. **It's not really a plugin** — TTS/STT command providers are config-driven (`tts.providers.<name>` / `stt.providers.<name>` with `type: command`); MCP integrations are `mcp_servers:` entries; gateway hooks are directories. → Route to the right surface: **`diagnosing-mcp`**, **`diagnosing-hooks`**, or the config docs.
9. **Core plugin gone after update (e.g. Spotify)** — some bundled plugins moved to the catalog; an enabled entry with no matching directory is not a broken install. → `duckwork plugins install <name>` from the catalog (or remove it from `plugins.enabled`).
10. **Installed directory exists but the plugin is never listed** — discovery could not read the directory, so it skipped it and moved on: `Skipping unreadable plugin directory <path>: [WinError 5] Access is denied` (Windows) or `Permission denied` (POSIX). `duckwork plugins list` simply omits the plugin, and `duckwork update` / `duckwork pm install` adds `Could not inspect plugin manifest <path>/plugin.yaml`. → Check the ACL: `icacls <path>` failing with `Access is denied`, or on Windows `dir /q` showing an owner other than you, means the DACL grants your account no read (an orphaned owner SID does this). Fix from an **elevated** prompt — `takeown /f <path> /r /d Y` then `icacls <path> /grant "<you>:(OI)(CI)F" /T` — or delete the directory and reinstall the plugin, then confirm it appears in `duckwork plugins list`. Skipping one unreadable directory is deliberate: it must not abort discovery for every other plugin (`duckwork_cli/plugins_discovery.py::scan_directory`; `duckwork_cli/config.py::_platform_plugin_manifests`).

## 5. Localization workflow

1. `duckwork plugins list` — is it discovered? No → wrong location / not installed (§1 table; project plugins → pitfall 3).
2. Discovered but "not enabled" → pitfall 1 (`duckwork plugins enable`).
3. Enabled but broken → `duckwork logs` for a `register()` failure (pitfall 4) or a capability gap (pitfall 2). A **load-timeout** message alone does not tell you which side was slow — check pitfall 4 and run `diagnosing-host-pressure` (`bash skills/diagnosing-host-pressure/scripts/host_pressure_probe.sh`) to rule the host in or out; only treat it as host pressure once the probe says so.
4. Sub-category plugin (memory/context/model-provider/platform) → check its selection key in config, not `plugins.enabled`.
5. Restart the session/gateway and verify: tools appear in `/tools list`, commands in `/` autocomplete, hooks via `duckwork hooks list`.
6. Re-run the detector: `duckwork guide plugins` headless or `/duckwork-doctor plugins` in-session; `+` means healthy, `~` means informational, and `x`/`?` means unresolved.

## Report

This skill diagnoses plugins that do not load or run — the plugins.enabled opt-in gate, capability consent, discovery locations, and provider sub-categories. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your plugin is installed but its tools and commands are absent because it is not in the `plugins.enabled` allowlist. Duckwork deliberately loads nothing from third-party code until you explicitly enable it.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Plugin not in `plugins.enabled` | `duckwork plugins list` shows `my-plugin: not enabled`; no tools or commands from the plugin appear in the session |
| MEDIUM | Plugin discovered but not enabled after install | `duckwork plugins list` shows the plugin under "Installed" but not under "Enabled" |

### Recommended Fix
Run `duckwork plugins enable my-plugin`, then restart the session. Verify with `duckwork plugins list` (should show "Enabled") and check that the plugin's tools appear in `/tools list`.

### References
- `$DUCKWORK_HOME/config.yaml` — `plugins.enabled` list
- `duckwork_cli/plugins.py` — `plugins.enabled` handling
- `duckwork_cli/plugins_discovery.py` — plugin discovery and "not enabled" message

---

*Facts re-verified 2026-09-28 against upstream source at commit `46a0daee58abbc1b07f84f505a5ba90f1958295c` (corrective pass): entry-point group `duckwork_agent.plugins` and the project-plugins gate `DUCKWORK_ENABLE_PROJECT_PLUGINS` (`plugins/memory/__init__.py`, `duckwork_cli/plugin_dev.py`); the capability set and fail-closed behaviour (`duckwork_cli/plugins.py::has_capability`, `plugin_capability_granted`); `plugins.enabled` handling (`duckwork_cli/plugins.py`); the sub-category directory list (`plugins/`, narrowed in the corrective pass — bundled Kanban is gated by `plugins.enabled`, per `duckwork_cli/plugins_discovery.py`); selection keys `context.engine` (`duckwork_cli/web_server_config.py`) and `image_gen.provider` (`agent/image_gen_*.py`). One claim was corrected (the nonexistent `llm.model_override` id). Spotify core-to-catalog move verified 2026-10-15 against the installed source at `9bda154d` (v0.21.7): absent from bundled `plugins/`, present as official catalog entry (`spotify` 2.0.0); migration in `duckwork_cli/left_core_migration.py`. Sub-category directory list re-verified 2026-10-19 against upstream main (`git ls-tree -d` on `plugins/`, and `plugins/computer_use/__init__.py`): the guide's pin gained `computer_use/` -- a provider directory with no `plugin.yaml` of its own and its own selection key -- and lost `observability/`, which was never an upstream directory (absent at baseline `d97007c`, at upstream main, and at every fetched commit). Upstream `plugins/` lists the same 22 directories at both ends of the window, so the 44->46 `VALID_HOOKS` growth and the `post_compaction` / `on_session_delete` additions need no change here -- those names are read from the installed source, never enumerated. Re-verified 2026-10-20 against the installed source at `dd519c74` (v0.22.2+1915): the per-plugin load deadline is configurable via `plugins.load_timeout_seconds` — default 10s, negatives and non-numbers fall back to 10 with a warning, `>600` clamps to 600, `0` disables the deadline and loads inline (`duckwork_cli/plugins_loader.py::_resolve_plugin_load_timeout`, `duckwork_cli/plugins_loader.py::run_with_load_deadline`); matching observation on this host: one cold first load after a fresh pin-install timed out on the default and the immediate retry passed (`duckwork plugins doctor duckwork-guide --ci`: rc=1 once, then rc=0 twice). Corrected 2026-10-20: the budget is per plugin, not global, and it is set only in config -- no plugin's `__init__.py` carries a load-timeout figure. Re-verified 2026-10-20 against the installed source at `9bda154d`: an unsearchable plugin directory is skipped with a warning and the plugin is absent from discovery (`duckwork_cli/plugins_discovery.py::scan_directory`), and the platform-manifest scan records the skip (`duckwork_cli/config.py::_platform_plugin_manifests`); observed on this host (Windows, WinError 5) on a directory owned by an unresolved SID. Re-checked 2026-10-23 against upstream main: `plugins/delegation/<name>/` plugins are `kind: backend`, selected by `delegation.backend`; the bundled `default` strategy then reads `delegation.provider` / `model` / `base_url` (`agent/delegation_registry.py`, `plugins/delegation/default/plugin.yaml`, `website/docs/developer-guide/delegation-provider-plugin.md`). Upstream discovery scans `plugins/delegation/` (it is not in the excluded-category set), so it is documented here but deliberately not in `constants.PLUGIN_SUBCATEGORY_DIRS`, which drives the guide's discovery skip. Re-verify before reuse.*
