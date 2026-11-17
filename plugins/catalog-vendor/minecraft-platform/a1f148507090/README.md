# Duckwork Minecraft Gateway ⛏️

A first-class [Duckwork Agent](https://duckwork-agent.fordex.com) platform plugin that lets you chat with Duckwork directly inside **Minecraft**.

Join a Minecraft server with a Mineflayer bot, and every player gets their own Duckwork session — same features as Discord, Telegram, or WhatsApp. Tools, commands, code execution, file editing — all accessible from in-game chat.

![Minecraft](https://img.shields.io/badge/Minecraft-1.21.11-green)
![Duckwork](https://img.shields.io/badge/Duckwork-Plugin-blue)
![Node](https://img.shields.io/badge/Node-%3E%3D22-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)

## Features

- **Per-player sessions** — each player gets their own Duckwork session (like DMs on Discord)
- **Full command support** — `$new`, `$help`, `$model`, `$stop` all work in chat
- **Plain text responses** — no markdown, no formatting codes (servers reject them)
- **Public chat responses** — Duckwork replies in public chat
- **Private tool progress** — terminal/file operations go via `/tell` private whisper
- **Auto-wander** — the bot wanders, jumps, and looks at nearby players
- **256-char chunking** — long responses split with `[1/3]` markers
- **Configurable prefix** — `$command` syntax keeps server commands from conflicting
- **Offline or Microsoft auth** — supports both offline and online-mode servers
- **Persistence** — survives gateway restarts via systemd drop-in

## Quick Start

### Prerequisites

- Duckwork Agent installed and running (`duckwork gateway run`)
- Node.js >= 22
- A Minecraft server (offline or online mode)
- Python 3.12+

### Installation

The plugin lives at `~/.duckwork/plugins/minecraft/`. Install it:

```bash
# Clone or copy the plugin
git clone https://github.com/DuckMind/duckwork ~/.duckwork/plugins/minecraft
# or symlink:
ln -sf /path/to/duckwork-minecraft-gateway ~/.duckwork/plugins/minecraft

# Install Node dependencies
cd ~/.duckwork/plugins/minecraft/bridge
npm install --production --no-audit --no-fund
```

### Configuration

Set environment variables (via systemd drop-in, `.env`, or `duckwork config`):

```bash
export MINECRAFT_ENABLED=true
export MINECRAFT_SERVER=your.server.ip
export MINECRAFT_PORT=25565
export MINECRAFT_USERNAME=DuckworkBot
export MINECRAFT_AUTH=offline    # or "microsoft"
export MINECRAFT_PREFIX=$        # prefix for Duckwork commands ($new, $help)
export MINECRAFT_ALLOW_ALL_USERS=true
```

Or create a systemd drop-in at `~/.config/systemd/user/duckwork-gateway.service.d/minecraft.conf`:

```ini
[Service]
Environment="MINECRAFT_ENABLED=true"
Environment="MINECRAFT_SERVER=your.server.ip"
Environment="MINECRAFT_PORT=25565"
Environment="MINECRAFT_USERNAME=DuckworkBot"
Environment="MINECRAFT_AUTH=offline"
Environment="MINECRAFT_ALLOW_ALL_USERS=true"
Environment="MINECRAFT_PREFIX=$"
```

### Starting

```bash
# Reload systemd, then restart gateway
systemctl --user daemon-reload
systemctl --user restart duckwork-gateway

# Or if running in foreground:
duckwork gateway restart
```

### Usage

Join your Minecraft server. The bot (`DuckworkBot`) will be wandering around.

| What to type | What happens |
|---|---|
| `hi` | Duckwork replies in public chat |
| `$new` | Reset your session |
| `$help` | Show available commands |
| `$model` | Show current LLM model |
| `write a poem` | Duckwork writes and responds |
| `what's the time?` | Duckwork checks and replies |

> **Tip:** The `$` prefix is only needed for commands. Regular chat goes straight to Duckwork.

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `MINECRAFT_ENABLED` | — | Required: `true` to enable the adapter |
| `MINECRAFT_SERVER` | — | Required: Minecraft server hostname/IP |
| `MINECRAFT_PORT` | `25565` | Server port |
| `MINECRAFT_USERNAME` | `DuckworkBot` | Bot's in-game username |
| `MINECRAFT_AUTH` | `offline` | `offline` or `microsoft` |
| `MINECRAFT_PREFIX` | `` (none) | Command prefix (`$new`, `$help`). Empty = no prefix |
| `MINECRAFT_PRIVATE_MESSAGES` | `false` | `true` = all replies via `/tell` private |
| `MINECRAFT_BRIDGE_PORT` | `13000` | Internal bridge HTTP port |
| `MINECRAFT_ALLOWED_USERS` | — | Comma-separated allowlist of usernames |
| `MINECRAFT_ALLOW_ALL_USERS` | `false` | `true` = any player can use the bot |
| `MINECRAFT_HOME_CHANNEL` | — | Default player for cron/notification delivery |

## Architecture

```
Minecraft Server
      ↑ Mineflayer (TCP/MC protocol)
      ↓
Node.js Bridge (bridge/index.js)
  - Mineflayer bot
  - HTTP server (health, messages, send)
  - Idle wander loop
      ↑ HTTP poll (500ms)
      ↓
Python Adapter (adapter.py)
  - Duckwork BasePlatformAdapter
  - Per-player session management
  - Message chunking (256-char limit)
  - § formatting / markdown conversion
      ↑
      ↓
Duckwork Gateway
  - LLM + tools
  - Command dispatch
  - Session persistence
```

## File Structure

```
duckwork-minecraft-gateway/
├── README.md              # You are here
├── LICENSE                # MIT
├── CHANGELOG.md           # Release history
├── plugin.yaml            # Duckwork plugin metadata
├── __init__.py            # Plugin entry point
├── adapter.py             # Python adapter (gateway integration)
├── bridge/
│   ├── package.json       # Node deps
│   └── index.js           # Mineflayer bot + HTTP bridge
├── docs/
│   ├── setup.md           # Detailed setup guide
│   ├── commands.md        # Command reference
│   ├── configuration.md   # All config options
│   ├── architecture.md    # Architecture deep-dive
│   └── formatting.md      # Minecraft § codes reference
└── scripts/
    └── install.sh         # One-shot install script
```

## Development

```bash
# Clone the repo
git clone https://github.com/DuckMind/duckwork
cd duckwork-minecraft-gateway

# Install Python deps (none extra — uses Duckwork gateway packages)
# Install Node deps
cd bridge && npm install

# Symlink to Duckwork plugins
ln -sf $PWD ~/.duckwork/plugins/minecraft

# Set env vars and restart gateway
duckwork gateway restart
```

## Version History

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT © Kyssta
