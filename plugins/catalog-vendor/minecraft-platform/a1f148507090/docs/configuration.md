# Configuration Reference

All configuration is done via environment variables. These can be set in:

- Systemd drop-in files (`~/.config/systemd/user/duckwork-gateway.service.d/minecraft.conf`)
- Shell exports before running `duckwork gateway run`
- The Duckwork `.env` file

## Required

### `MINECRAFT_ENABLED`
Must be `true` to activate the Minecraft platform adapter.

```
MINECRAFT_ENABLED=true
```

### `MINECRAFT_SERVER`
The hostname or IP address of your Minecraft server.

```
MINECRAFT_SERVER=127.0.0.1
MINECRAFT_SERVER=mc.example.com
```

## Connection

### `MINECRAFT_PORT`
Minecraft server port. Default: `25565`.

```
MINECRAFT_PORT=25565
```

### `MINECRAFT_USERNAME`
The bot's in-game username. Default: `DuckworkBot`.

```
MINECRAFT_USERNAME=DuckworkBot
```

### `MINECRAFT_AUTH`
Authentication mode. Default: `offline`.

- `offline` — for servers in offline mode (no authentication required)
- `microsoft` — for online-mode servers (Microsoft account, device code flow)

```
MINECRAFT_AUTH=offline
MINECRAFT_AUTH=microsoft
```

## Chat Behaviour

### `MINECRAFT_PREFIX`
Command prefix for Duckwork commands. Messages starting with this prefix are treated as commands (`$new`, `$help`). Messages without it go to Duckwork as normal chat.

Default: empty (no prefix — all chat goes to Duckwork).

```
MINECRAFT_PREFIX=$
MINECRAFT_PREFIX=!
```

### `MINECRAFT_PRIVATE_MESSAGES`
When `true`, all Duckwork responses go via `/tell` (private message) instead of public chat.

Default: `false` (public chat).

```
MINECRAFT_PRIVATE_MESSAGES=false
MINECRAFT_PRIVATE_MESSAGES=true
```

> **Note:** When `true`, progress/debug messages still go via `/tell`. The `private_messages` setting only changes where the final response appears.

## Access Control

### `MINECRAFT_ALLOW_ALL_USERS`
When `true`, any player on the server can talk to Duckwork. For development/testing.

Default: `false`.

```
MINECRAFT_ALLOW_ALL_USERS=true
```

### `MINECRAFT_ALLOWED_USERS`
Comma-separated list of Minecraft usernames allowed to interact with the bot. Only used when `MINECRAFT_ALLOW_ALL_USERS=false`.

```
MINECRAFT_ALLOWED_USERS=iQvt,Notch,Dinnerbone
```

## Internal

### `MINECRAFT_BRIDGE_PORT`
Internal port for the HTTP bridge between the Python adapter and the Node.js Mineflayer process. Change only if there's a port conflict.

Default: `13000`.

```
MINECRAFT_BRIDGE_PORT=13000
```

### `MINECRAFT_HOME_CHANNEL`
Default player username for cron job delivery and automated notifications.

```
MINECRAFT_HOME_CHANNEL=iQvt
```

## Gateway Behaviour

The plugin sets `notice_delivery: private` by default, which means tool progress messages (terminal commands, file edits) are delivered via `/tell` private whisper rather than public chat. This keeps the public chat clean.
