# Mixar for Duckwork Agent

Connect [Duckwork Agent](https://github.com/DuckMind/duckwork) to [Mixar](https://www.mixar.app), the AI-native 3D editor built on Blender 5.2. With this plugin Duckwork can build and edit 3D scenes, generate models, textures, rigs and animation with AI, render stills and turntables, and export game-ready assets for Unity, Unreal and Godot.

The plugin is a portable Agent Plugin package:

- `mcp.json` starts the MCP server that Mixar installs for the signed-in user, through `bin/mixar-mcp` (`bin/mixar-mcp.cmd` on Windows).
- `skills/mixar` teaches Duckwork the Mixar workflow: check readiness, read the scene, build in small steps, verify with a render, and deliver.
- `plugin.json` tells Duckwork to offer the server only when Mixar 4.2.1 or newer is installed, and gives scene calls a 610-second tool-call timeout.

## Requirements

- Mixar 4.2.1 or newer on macOS, Windows or Linux. Duckwork refuses the install when it cannot find it (see [Platforms](#platforms) for where it looks).
- A Mixar account, signed in in the app, with **Connect MCP** turned on. Both are done once in Mixar's interface.
- Duckwork running on the same computer as Mixar. The launcher only reaches the Mixar app on its own computer, so a Duckwork on a remote server or in a container cannot use this plugin.
- Duckwork Agent v0.22.3 or newer.

Duckwork supplies the model. You do not need a Mixar API key, a personal access token or a separate Python environment: the launcher runs on Mixar's embedded Python.

## Install

From the Duckwork plugin catalog:

```bash
duckwork plugins install mixar
```

Or straight from GitHub:

```bash
duckwork plugins install Mixar-AI/duckwork-mixar --enable
```

Then in Mixar: sign in, open the profile menu > **Connect MCP**, and check that the status line reads "MCP is on". Run `/reload-mcp` in Duckwork (or start a new session) and ask it to check Mixar's status. If no Mixar tools appear, `~/.duckwork/logs/mcp-stderr.log` says why.

The tools appear under the `mixar` server, for example `mcp__mixar__scene_overview` and `mcp__mixar__execute_bpy_script`. `skills/mixar/references/setup.md` covers first-run setup and troubleshooting.

## What Duckwork can do with it

| Area | Tools |
|------|-------|
| Read the scene | `scene_overview`, `scene_hierarchy`, `get_object_details`, `inspect_geometry` |
| Build | `execute_bpy_script`, `move_groups`, `place_camera` |
| AI generation | `get_generation_params`, `enqueue_generation`, `get_all_queue_status` (3D models, retopology, UV, rigs, animation, textures, images, video, splat worlds) |
| Assets and materials | `search_asset_library`, `list_terrain_assets`, `create_layered_material` |
| Verify | `render_viewport`, `view_image`, `inspect_uv_map`, `inspect_mesh_seams` |
| Deliver | `export_scene` (`unreal`, `unity`, `godot`, `web`, `ar` and `print` presets), `export_asset`, `render_scene_image`, `render_scene_video` |
| Scene tabs | `mixar_scene_new`, `mixar_scenes`, `mixar_scene_switch`, `mixar_projects`, `mixar_project_open` |
| Account | `mixar_status`, `mixar_credit_balance`, `mixar_tool_quote`, `mixar_guide` |

The live list comes from the running Mixar and can grow between releases.

## Disclosure

Read this before installing.

- **Runs code from the installed Mixar app.** `bin/mixar-mcp` executes `~/.mixar/connector/mixar-mcp` (on Windows, `bin/mixar-mcp.cmd` runs `%USERPROFILE%\.mixar\connector\mixar-mcp.cmd`), a launcher the Mixar desktop app writes for the current user, which runs Mixar's bundled `mcp.py` on Mixar's embedded Python. The plugin ships no binary and downloads nothing.
- **Arbitrary Python inside Mixar.** `execute_bpy_script` and other scene tools run Python in the Mixar process with your privileges. A loopback connection is not a sandbox.
- **Can start Mixar.** A tool call made while Mixar is closed may open the installed Mixar app. Listing tools never does.
- **Mixar stays open.** If a tool call opened Mixar, it keeps running after Duckwork exits; quit it like any other app.
- **Network calls through Mixar.** The launcher talks to the desktop app over loopback with a per-launch bearer token. The desktop app forwards calls to Mixar's backend (`api.mixar.app`) under your signed-in account.
- **Prompts and images go to AI providers.** For a generation, Mixar's backend passes the prompt, reference images and relevant scene context to the AI provider that runs the chosen model (such as OpenAI, Anthropic, Google, fal.ai, Replicate or Tripo). Mixar does not use them to train AI models.
- **Diagnostic records.** Mixar's backend records each MCP tool call (its inputs, including prompts, and its results) for troubleshooting and service improvement. It deletes these records within 30 days of collection and their backup copies within 7 days. This is separate from **Share Usage Data**.
- **Spends Mixar credits.** AI generation jobs and `create_layered_material` cost Mixar credits from your account; every other tool is free. `mixar_tool_quote` gives the current price before a call. The plugin declares these credit ranges to Duckwork, which names the cost in its approval prompts and asks for an explicit yes before a chat passes 500 Mixar credits (it counts each call at the top of its range).
- **No stored credentials.** The plugin and the launcher never hold your Mixar token; the desktop app attaches its own login to each call.
- **Reads outside the plugin.** The launcher reads `~/.mixar/` (its manifest, the saved tool list and the discovery records of running Mixar apps).
- **Usage data.** The plugin sends none. Mixar's own desktop usage analytics are on by default, exclude prompts, file names and scene content, and can be turned off under **Edit → Preferences → System → Privacy → Share Usage Data**.
- **Developer override.** If `MIXAR_MCP_LAUNCHER` is set (in your shell or the Duckwork `.env`), the plugin runs the program it names instead of Mixar's launcher. Leave it unset unless you are testing a Mixar build.
- **No self-update.** Updates arrive only as a new pinned commit in the Duckwork plugin catalog. Mixar itself updates through its own updater, outside this plugin.

Full details are in the [Mixar Privacy Policy](https://www.mixar.app/legal/privacy-policy).

## Platforms

| Platform | Where Duckwork looks for Mixar | Version check | Launcher the plugin starts |
|----------|------------------------------|---------------|----------------------------|
| macOS | `Mixar.app` in `/Applications` or `~/Applications` | the app's `Info.plist` | `~/.mixar/connector/mixar-mcp` |
| Windows | the Mixar entry in installed apps (`mixar.exe` in its install folder), or `%ProgramFiles%\Mixar\mixar.exe` | the installed-apps entry | `%USERPROFILE%\.mixar\connector\mixar-mcp.cmd` |
| Linux | a `mixar` command on `PATH`, or the launcher Mixar writes on first run | none (presence only) | `~/.mixar/connector/mixar-mcp` |

`mcp.json` holds one command, `./bin/mixar-mcp`. On macOS and Linux it is the POSIX shell script; on Windows the MCP SDK Duckwork uses resolves the same command through `PATHEXT` to `bin/mixar-mcp.cmd`. Mixar for Linux is a portable archive with no fixed install folder, so open Mixar once before installing the plugin, or put its `mixar` executable on your `PATH`.

## Development

```bash
duckwork plugins validate /path/to/duckwork-mixar --install-deps
duckwork plugins doctor /path/to/duckwork-mixar
```

The **Launcher shim** workflow (`.github/workflows/launcher-shim.yml`) starts `bin/mixar-mcp` the way Duckwork does against a stub Mixar launcher on macOS, Windows and Ubuntu runners.

Two optional variables point the package at a development or QA build of Mixar. Set them in your shell or the Duckwork profile's `.env`:

- `MIXAR_MCP_LAUNCHER`: another launcher, for example a source build's.
- `MIXAR_MCP_DISCOVERY_DIR`: another discovery folder for running Mixar apps.

`VERIFICATION.md` records what has been checked and what has not.

## License

MIT. See `LICENSE`. Mixar itself is a separate product under its own license.
