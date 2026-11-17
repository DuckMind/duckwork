# Setting up Mixar for Duckwork

Installation, MCP availability and scene readiness are separate states. Check each in order.

## 1. Install Mixar

Download Mixar 4.2.1 or newer from https://www.mixar.app. Duckwork refuses this package when it cannot find Mixar, or when the installed version is older than 4.2.1:

- macOS: move `Mixar.app` to `/Applications` or `~/Applications`.
- Windows: run the installer; Duckwork finds Mixar through its installed-apps entry or in `%ProgramFiles%\Mixar`.
- Linux: Mixar is a portable archive with no fixed folder. Open Mixar once before installing the plugin (that writes the launcher Duckwork checks for), or put its `mixar` executable on `PATH`. Linux has no version check.

Mixar updates itself; the plugin never downloads or updates Mixar.

## 2. Sign in and turn on MCP

1. Open Mixar and sign in from the profile menu.
2. Open the profile menu > **Connect MCP**.
3. The status line should read "MCP is on · AI apps can connect to this Mixar". If it says MCP is off, click **Turn on**.
4. Optional: switch on **Let AI apps control Mixar's interface** to allow the `mixar_ui_*` tools.

Mixar writes the launcher this package starts, `~/.mixar/connector/mixar-mcp` (`%USERPROFILE%\.mixar\connector\mixar-mcp.cmd` on Windows), while it runs; with MCP off the launcher only answers that MCP is turned off. If that file is missing after these steps, quit and reopen Mixar.

## 3. Reload MCP in Duckwork

Run `/reload-mcp` in the Duckwork session, or start a new session. Then call `mixar_status` (or `mixar_ui_context` when `mixar_status` is not listed yet): an answer naming the desktop and the scene means Mixar is ready.

If no Mixar tools appear at all, the launcher did not start. Duckwork shows "Connection closed" for the `mixar` server, and `~/.duckwork/logs/mcp-stderr.log` holds the launcher's own message, such as the path where it looked for Mixar's launcher.

## Development and QA builds

`MIXAR_MCP_LAUNCHER` points the package at another launcher (for example a source build's), and `MIXAR_MCP_DISCOVERY_DIR` at another discovery folder. Set them in the shell or in the Duckwork profile's `.env`; when unset, the defaults apply.

## Platforms

The package runs on macOS, Windows and Linux. Duckwork must run on the same computer as Mixar: the launcher only reaches the Mixar app on its own computer.
