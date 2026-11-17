# Finding catalog

Every `broken` or `unknown` result from `duckwork guide` carries a stable `id`,
a plain-language `impact`, and a concrete `fix`. The same keys appear in the
`duckwork guide --json` document, so a skill or script can route on `id` instead
of matching English prose.

`checks.FINDING_IDS` is the single source for the copy, and this catalog is
generated from it plus the `_CHECKS` call graph. Do not edit the table by hand:
`python tools/render_docs.py` fails when it drifts, and `--write` refreshes it.

- `scope` is the `duckwork guide <scope>` argument that can report the finding;
  `any` means the runner itself emits it.
- `fix` is the sanctioned next action — a `duckwork` command, a file and field
  edit, or a report target when the finding is a duckwork-guide defect.
- IDs are public API once released: add entries, never rename one.

<!-- BEGIN GENERATED: findings-catalog -->
| id | scope | meaning | impact | fix |
|---|---|---|---|---|
| `CHECK_CRASHED` | any | check crashed | The affected check failed to run, so its surface was not inspected (a defect in duckwork-guide, not in your config). | Re-run `duckwork guide <scope>`; if it repeats, file the exception type and `duckwork --version` at https://github.com/DuckMind/duckwork |
| `COMMANDS_BUNDLE_MALFORMED` | `commands` | command bundle malformed | Commands defined in the listed bundles will not resolve. | Fix or remove the listed bundle files, then re-run `duckwork guide commands`. |
| `CONFIG_MISSING` | `config` | config file missing | Duckwork runs on built-in defaults; any custom provider, model, or tool choice is ignored. | Run `duckwork setup` or restore the file to the reported path, then re-run `duckwork guide config`. |
| `CONFIG_PATH_UNRESOLVED` | `config` | config path unresolved | Duckwork cannot locate `config.yaml`, so custom providers, models, and tools may silently fall back to defaults. | Run `duckwork config path`; if it fails, reinstall the Duckwork CLI. |
| `CONFIG_UNPARSEABLE` | `config` | config.yaml does not parse | Duckwork cannot load its settings, so affected features fall back or fail at startup. | Fix the YAML at the reported path (indentation, quoting, duplicate keys), then re-run `duckwork guide config`. |
| `CONFIG_UNREADABLE` | `mcp`, `plugins` | config unreadable or unparsable | The affected surface cannot be inspected because the config could not be loaded (unreadable file or invalid YAML). | Check read permissions on the reported path, and if the file is readable fix its YAML, then re-run `duckwork guide`. |
| `FAST_MODE_UNRESOLVED` | any | fast mode skipped a surface | The affected surface was skipped, so its real state is unknown. | Re-run `duckwork guide <scope>` without `--fast`. |
| `HOME_UNRESOLVED` | `commands`, `hooks`, `memories`, `sessions`, `skills`, `update` | Duckwork home unresolved | The affected surface cannot be inspected because the Duckwork home directory could not be resolved. | Run `duckwork config path` to confirm the profile resolves, then re-run `duckwork guide <scope>`. |
| `HOOKS_ALLOWLIST_INVALID` | `hooks` | shell-hooks allowlist invalid | The shell-hook consent list cannot be read, so approved hooks may be skipped or re-prompt, and any other hook problems are quoted in the detail. | Repair or delete the reported `shell-hooks-allowlist.json`, then fix the hook problems in the detail and re-run `duckwork guide hooks`. |
| `HOOKS_CONFIG_NOT_FOUND` | `hooks` | hooks config missing | Hooks cannot be inspected because the profile's config file was not found. | Run `duckwork config path` and restore the profile's `config.yaml`. |
| `HOOKS_CONFIG_UNREADABLE` | `hooks` | hooks config unreadable | Hooks cannot be inspected because the config file could not be loaded. | Check read permissions on the profile's `config.yaml`, and if the file is readable fix its YAML, then re-run `duckwork guide hooks`. |
| `HOOKS_DOCTOR_FINDINGS` | `hooks` | hooks doctor findings | One or more hooks fail or are misconfigured, so the events they guard are unhandled. | Fix each hook reported by `duckwork hooks doctor`, then re-run `duckwork guide hooks`. |
| `HOOKS_DOCTOR_OPAQUE` | `hooks` | hooks doctor output unrecognized | Hook health could not be determined because the doctor output was not recognized. | Run `duckwork hooks doctor` manually and compare its output with the installed Duckwork version. |
| `HOOKS_DOCTOR_UNAVAILABLE` | `hooks` | hooks doctor unavailable | Hook health could not be verified, so a broken hook can fail silently at runtime. | Run `duckwork hooks doctor` manually and fix the error it reports. |
| `HOOKS_FINDINGS` | `hooks` | hook findings | One or more shell hooks are malformed, unreachable, or not allowlisted, so the events they guard are unhandled. | Fix the listed hook entries in `config.yaml`, and approve each valid hook at the interactive prompt when the detail says it is not allowlisted; then re-run `duckwork guide hooks`. |
| `HOOKS_INSPECTION_FAILED` | `hooks` | hook inspection failed | Hooks could not be inspected because the hook configuration raised an error. | Re-run `duckwork guide hooks`; if it repeats, report the exception type shown in the reason. |
| `HOOKS_INSPECTION_UNAVAILABLE` | `hooks` | hooks inspection unavailable | Hooks were skipped in this run, so hook failures surface only during a session. | Hooks are inspected in-process by default and nothing was inspected here — add `--deep` (or run `duckwork hooks doctor` directly) for the live check that executes each approved hook once. |
| `MCP_SERVER_MALFORMED` | `mcp` | MCP server entry malformed | The listed MCP servers will not start, so their tools are unavailable to the agent. | Move foreign keys such as `mcpServers` under the top-level `mcp_servers` mapping, make `mcp_servers` a mapping, and fix the listed entries (`command` for stdio, `url` for HTTP); then re-run `duckwork guide mcp`. |
| `MEMORIES_ISSUES` | `memories` | memory issues | The listed memory files are inconsistent, so stored context may be stale or ignored. | Fix the listed files under `$DUCKWORK_HOME/memories/`, then re-run `duckwork guide memories`. |
| `PLUGINS_CONFIG_SHAPE` | `plugins` | plugins config malformed | The `plugins` section or its `enabled`/`disabled` keys have the wrong shape, so Duckwork ignores those settings and plugins may not load. | Rewrite `plugins` in `config.yaml` as a mapping with `enabled` and `disabled` lists, then re-run `duckwork guide plugins`. |
| `PLUGINS_MISSING_OR_BROKEN` | `plugins` | plugin missing or broken | The listed enabled plugins are missing or failed to load, so their commands, tools, and hooks are absent. | Run `duckwork plugins list`; reinstall a missing plugin, and for an exclusive provider select its category key (for example `memory.provider`) instead of `plugins.enabled`. |
| `SESSIONS_LOG_UNPARSED` | `sessions` | session log unparsed | Session activity cannot be analyzed because the log format was not recognized. | Re-run `duckwork guide sessions`; if it repeats, check the log format written by the installed Duckwork version. |
| `SESSIONS_LOG_UNREADABLE` | `sessions` | session log unreadable | Session activity cannot be analyzed, so runaway sessions stay undetected. | Check read permissions on the reported agent log, then re-run `duckwork guide sessions`. |
| `SESSIONS_RUNAWAY` | `sessions` | runaway session | The listed sessions are burning API calls and context without progress, which inflates cost and degrades answers. | Start a new session instead of resuming the listed one, and separate generation from verification into distinct turns. |
| `SKILLS_ISSUES` | `skills` | skill issues | The listed skills will not load or will be shadowed, so their instructions and slash commands are missing. | Fix the listed frontmatter, name, or path problems, then re-run `duckwork guide skills`. |
| `UPDATE_CHECKOUT_UNRESOLVED` | `update` | install checkout unresolved | The install checkout cannot be located, so update health cannot be verified. | Run `duckwork doctor` to confirm the install layout, then re-run `duckwork guide update`. |
| `UPDATE_LAYOUT_UNRECOGNIZED` | `update` | install layout unrecognized | The install layout was not recognized, so a stuck update lock cannot be ruled out. | Run `duckwork doctor` to confirm the install layout, then locate the checkout and its update lock by hand. |
| `UPDATE_LOCK_HELD` | `update` | update lock held | Every `duckwork` invocation can wedge until the process holding the checkout exits. | Wait for the process holding the checkout to exit (owner PID in the reason); do not remove the lock while it is held. |
| `UPDATE_LOCK_INDETERMINATE` | `update` | update lock indeterminate | Update ownership cannot be determined, so removing the lock could interrupt a live update. | Check whether the owner PID in the reason is alive by hand before touching the reported lock file. |
| `UPDATE_LOCK_MALFORMED` | `update` | update lock malformed | The update lock does not name an owner, so update state cannot be determined. | The lock must contain one PID; if no update is running, remove the reported file with human confirmation. |
| `UPDATE_LOCK_UNPROBEABLE` | `update` | update lock unprobeable | A dead update owner may still be holding the checkout, and that could not be verified. | Check for a running `duckwork` or `git` process by hand before touching the reported lock file. |
| `UPDATE_LOCK_UNREADABLE` | `update` | update lock unreadable | A stale update lock may be blocking every `duckwork` command, and it could not be read. | Check read permissions on the reported lock file, then re-run `duckwork guide update`. |
<!-- END GENERATED: findings-catalog -->
