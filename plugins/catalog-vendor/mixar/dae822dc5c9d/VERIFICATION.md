# Verification

Run on 2026-10-22 on macOS (Apple Silicon) with Mixar 4.3.5 (`/Applications/Mixar.app`) signed in (0 credits for the runtime tests; the model-driven runs below used a funded account), and Duckwork Agent v0.22.4 installed by the official installer (checkout `4d04303818`). Lifecycle, gate, state and timeout tests used separate throwaway `DUCKWORK_HOME` folders; live tests used the default profile and the running Mixar. Runtime tests call Duckwork's own MCP code (`discover_mcp_tools`, the tool registry) without a model. Tests ran from plugin commit `4af0f50` onwards; later commits changed the skill, documentation and platform declarations, and the affected checks were re-run.

## Results

### Packaging

| Check | Result |
|---|---|
| `duckwork plugins validate <repo> --install-deps` | Passed: manifest, config schema, server availability (`available, version 4.3.5`), security scan `safe`, "portable plugin (no Python)" |
| `duckwork plugins doctor <repo>` | Passed |
| `scripts/validate_plugin_catalog.py` on the catalog entry (`plugin-catalog/mixar.yaml` in the catalog PR) | `OK: 1 file(s) valid` |
| `scripts/scan_plugin_payloads.py <repo>` | Passed |
| Catalog CI on Linux | `validate` reports availability as informational, so a platform the runner lacks does not fail it |

### Lifecycle (real Duckwork CLI, throwaway home)

| Check | Result |
|---|---|
| Install `--no-enable`; the disabled package exposes no server | Pass |
| Enable: server present, `timeout` 610 s | Pass |
| Disable removes it; enable restores it | Pass |
| Second install without `--force` | Refused ("already exists") |
| `--force` reinstall keeps `bin/mixar-mcp` executable | Pass |
| A same-name `mcp_servers.mixar` in `config.yaml` replaces the package entry | Pass |
| A pinned install refuses `plugins update`; `install --force --ref <new sha>` moves it (0.1.0 → 0.1.1) | Pass |
| `plugins remove` deletes the plugin and its server | Pass |
| Dashboard (`duckwork dashboard`) lists `mixar` with `runtime_status: enabled` | Pass |

### Install gates

| Check | Result |
|---|---|
| Mixar.app missing | Install refused: `unavailable: missing_app` |
| Mixar older than `min_version` | Install refused: `unavailable: version_too_old` |
| Mixar 4.3.5 present | Installs |

### Launcher shim

| Check | Result |
|---|---|
| Launcher missing | Exit 1, nothing on stdout, stderr points to Connect MCP |
| `HOME` unset | Exit 1, "HOME is not set" |
| `HOME` without Mixar | Names the expected launcher path |
| `HOME` with spaces; arguments | Resolved; passed through |
| Process | `exec` replaces the shim (same PID) |

### Launcher states through Duckwork (fake connector folders; no Mixar was started)

| State | Duckwork result |
|---|---|
| MCP turned off | 80 tools listed from the saved list; calls answer "MCP is turned off in Mixar…" |
| Mixar closed and not startable | "Mixar is not open, and no installed Mixar could be started" |
| Never connected (no saved list) | Only 15 local tools; `mixar_status` is not listed |
| Update in progress | "Mixar is starting or unavailable" |
| Launcher missing | 0 tools, "Connection closed"; the shim's message is in `logs/mcp-stderr.log` |

### Live Mixar through Duckwork

| Check | Result |
|---|---|
| Discovery | 77 tools in about 2 s; names ≤ 64 characters, no duplicates, every schema an object |
| Every read-only tool that needs no arguments (26) | All routed; no transport failure |
| New scene tab, build a crate, read back, render, reopen the render by image ref | Pass; Duckwork saved the render under `~/.duckwork/cache/images` |
| Export a Godot `.glb` to Downloads | Valid glTF, `verification_passed` reported (test file deleted) |
| Syntax error, blocked `import os`, unknown object, wrongly typed argument | Clear tool errors, no crash |
| `mixar_call_status` for the build call | Outcome recovered |
| Close a tab holding new objects | Refused without `contents: "discard"`; with it the tab closes and the connection re-pins to the original tab, which is unchanged |
| Price quotes | `create_layered_material` 1 credit; `enqueue_generation` `existing_job_queue`; scripts 0 |
| `world_labs` without `user_requested` | Refused before queueing |
| `image_gen` at 0 credits | `dispatched: true`, then the job fails with "This generation uses credits — get a subscription to continue"; balance stays 0 |
| Reload (shutdown and rediscover) | Tools and live calls restored |
| Mixar quits, then is reopened by hand | `mixar_ui_context(instance)` with the instance named in the error re-pins the same Duckwork session |
| Tool-call timeout | A 330-second call answered through the package (610 s); the same call through a server on Duckwork's default timed out at 300 s |
| Tool names in `SKILL.md`, `references/setup.md`, `README.md` | All exist in the live list |

### Credit costs and the spend limit

| Check | Result |
|---|---|
| `duckwork plugins validate` | "server costs: mixar — 2 costed tool(s), spend limit 500 Mixar credits per chat" |
| Duckwork's runtime config for the server | `tool_costs` (`enqueue_generation` 6–250, `create_layered_material` 1–2), `spend_limit` 500, `cost_unit` "Mixar credits" |
| Three `enqueue_generation` calls through Duckwork against a stub server with the same tool names (no credits spent) | The first two ran; the third stopped at Duckwork's spend-limit prompt naming the 6–250 range and the chat's 500 total, and was not run when nobody approved it; a free tool still ran |

### Windows and Linux

| Check | Result |
|---|---|
| Duckwork parses the `darwin`, `win32` and `linux` app blocks (`duckwork_platform.declaration`) | Pass; `validate` unchanged |
| The Linux block evaluated by Duckwork's resolver on this machine | `mixar` not on PATH, launcher path found: available |
| `.github/workflows/launcher-shim.yml` script run locally on macOS with the MCP SDK Duckwork pins (2.3.0) | Pass: initialize, tools/list and tools/call through `bin/mixar-mcp` to a stub launcher in a home folder with a space; missing launcher exits 1 with an empty stdout |
| The same workflow on `macos-latest`, `windows-latest` and `ubuntu-latest` runners ([run 39890262818](https://github.com/DuckMind/duckwork), commit `a01c4cf`) | Pass on all three; on Windows the SDK resolved `./bin/mixar-mcp` to `bin\mixar-mcp.CMD` |
| Windows with a real Mixar, installed from GitHub (checked by the maintainer on 2026-10-22) | Reported working |

### Model-driven sessions

Run on 2026-10-23 with `duckwork -z "<prompt>" -t mcp-mixar,skills -m gpt-6-sol --provider openai-codex` (a ChatGPT/Codex subscription) from an empty folder, against the running Mixar 4.3.5 on macOS with a funded account. Every outcome was checked independently through Duckwork's runtime, not only from the model's answer.

| Scenario | What the model did | Independent check |
|---|---|---|
| "Is Mixar ready to use right now?" | `mixar_status`, correct answer | — |
| Build a 1.2 m × 0.45 m bench in a new tab, check it with a render, export it for Godot | Loaded the `mixar` skill, read the guide, searched the asset library, opened a tab, built and rendered four times with `inspect_geometry`, exported | 11 parts, 1.20 × 0.39 × 0.45 m on the ground; valid `.glb` in Downloads; other tabs untouched |
| "Close the tab 'Duckwork Close Test'" (holding work the model did not make) | Tried a plain close, got Mixar's refusal, asked the user before discarding | Tab and object still present |
| Generate a concept image | Quoted, queued once, polled, named the Moodboard image | One image on the Moodboard; balance −7 |
| Turn that image into a high-quality 3D model at the origin, 0.8 m wide, within 120 credits | First submit rejected for a guessed parameter at no cost; confirmed with `mixar_call_status`, resubmitted once (Tripo Pro), placed and rendered | One `model_3d` job; 17,605-face mesh 0.80 × 0.67 × 0.69 m centred on the origin, resting on the ground; balance −60 |
| An explorable splat world of a tavern interior | New tab, one `world_labs` job (Marble 1.1), waited, reported the import; said it could not confirm the look from its outside view | Splat and collider imported; an inside camera view shows brick walls, a hearth and benches; balance −151 |
| A realistic layered material (weathered oak, rusty iron) on the chest | Two `create_layered_material` calls; both returned HTTP 524 and were recovered with `mixar_call_status` (pending, then complete) without retrying | Oak and iron materials on the chest in the final render; balance −2 |

## Found and fixed during testing

- Before Mixar has ever connected, `mixar_status` is not listed: the skill falls back to `mixar_ui_context`.
- A launcher that cannot start shows only "Connection closed" in Duckwork: the skill and setup point to `logs/mcp-stderr.log`.
- A queued job at 0 credits reports `dispatched: true` and fails later: the skill reports it instead of resubmitting.
- Duckwork pauses a server for 60 s after three failed calls in a row (hard-coded; any tool; script errors count), which blocked even the recovery call: the skill never retries more than twice in a row.
- A Mixar that quits mid-session is not reopened by the pinned connection: the skill asks the user to open it and re-pins with `mixar_ui_context`.
- A splat world job was polled about 150 times in one turn: the skill gives typical job durations and says not to poll in a tight loop.
- The model could not judge an interior splat world from its outside view: the skill says to check it from a camera placed inside with the splat render engine.
- `create_layered_material` outlived the web proxy (HTTP 524) and completed anyway: the skill says `mixar_call_status` reports `pending` until `complete`.

## Observations outside this plugin

- Mixar launcher: after the Mixar a connection was pinned to quits, calls answer "Mixar is starting or unavailable" although nothing is starting; once Mixar is reopened the message is accurate.
- Mixar backend: calls that take longer than the web proxy allows (about 100 s) answer HTTP 524 while the work continues; the outcome is recoverable with `mixar_call_status`.
- Duckwork: the per-server breaker cannot be tuned from a plugin.

## Not executed

- A model-driven session that starts with Mixar closed (cold start through the skill's wait-and-retry guidance); the cold start itself was exercised through Duckwork's runtime.
- Signed out, and several signed-in Mixar apps open at once.
- Linux with a real Mixar: only the shim against a stub launcher runs there (CI); a live Mixar session through Duckwork on Linux is untested.
- The catalog's clean pinned-source admission job, which needs the repository on GitHub at the pinned commit.
