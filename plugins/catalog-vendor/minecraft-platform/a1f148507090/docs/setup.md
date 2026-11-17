# Setup Guide

## Prerequisites

- **Duckwork Agent** — installed and running (`duckwork gateway run` or systemd service)
- **Node.js** >= 22 (`node --version`)
- **A Minecraft server** — accessible from the Duckwork machine (offline or online mode)
- **npm** — for installing Mineflayer deps

## Step 1: Install the Plugin

```bash
# Clone the repo
git clone https://github.com/DuckMind/duckwork ~/.duckwork/plugins/minecraft

# Install Node.js dependencies
cd ~/.duckwork/plugins/minecraft/bridge
npm install --production --no-audit --no-fund
```

> Already have it? `cd ~/.duckwork/plugins/minecraft && git pull`

## Step 2: Configure Env Vars

### Option A: Systemd drop-in (recommended for persistent setups)

Create `~/.config/systemd/user/duckwork-gateway.service.d/minecraft.conf`:

```ini
[Service]
Environment="MINECRAFT_ENABLED=true"
Environment="MINECRAFT_SERVER=127.0.0.1"
Environment="MINECRAFT_PORT=25565"
Environment="MINECRAFT_USERNAME=DuckworkBot"
Environment="MINECRAFT_AUTH=offline"
Environment="MINECRAFT_ALLOW_ALL_USERS=true"
Environment="MINECRAFT_PREFIX=$"
```

Then reload and restart:

```bash
systemctl --user daemon-reload
systemctl --user restart duckwork-gateway
```

### Option B: Export before running Duckwork

```bash
export MINECRAFT_ENABLED=true
export MINECRAFT_SERVER=127.0.0.1
export MINECRAFT_PORT=25565
export MINECRAFT_USERNAME=DuckworkBot
export MINECRAFT_AUTH=offline
export MINECRAFT_ALLOW_ALL_USERS=true
export MINECRAFT_PREFIX=$
duckwork gateway restart
```

### Option C: Duckwork config

```bash
duckwork config set minecraft.enabled true
duckwork config set minecraft.server 127.0.0.1
duckwork config set minecraft.port 25565
# ... etc
duckwork gateway restart
```

## Step 3: Verify it's running

```bash
# Check gateway logs
journalctl --user -u duckwork-gateway --no-pager -n 20 | grep -i minecraft

# Check bridge health
curl -s http://127.0.0.1:13000/health

# Expected response:
# {"status":"connected","players":["DuckworkBot","iQvt"],"username":"DuckworkBot"}
```

## Step 4: Join the Minecraft server

Join your server. The bot should be online and wandering. Type something in chat:

```
hello
```

Duckwork should reply. Try a command:

```
$help
```

## Microsoft Auth (Online Mode)

For online-mode servers, set `MINECRAFT_AUTH=microsoft`. Mineflayer will prompt with a device code URL on first launch:

```bash
export MINECRAFT_AUTH=microsoft
duckwork gateway restart
```

Check the bridge logs for the device code URL, visit it, and enter the code.

## Troubleshooting

### "Bot connects then gets kicked"

Check for illegal characters. The adapter strips non-Latin-1 characters automatically. If you see "Illegal characters in chat" in the server logs, it's likely the username itself — use a plain ASCII username.

### "No response from Duckwork"

1. Check the bridge is connected: `curl -s http://127.0.0.1:13000/health`
2. Check logs: `journalctl --user -u duckwork-gateway --no-pager -n 50 | grep minecraft`
3. Check bridge logs: `cat ~/.duckwork/logs/minecraft-bridge.log`
4. Make sure `MINECRAFT_ENABLED=true` is set

### "The bot isn't moving"

The idle wander loop runs every 8-15 seconds. If the bot is receiving messages, it's working fine. Wandering is a background cosmetic feature.

### Gateway restart blocked

If `duckwork gateway restart` says "Blocked: cannot restart from inside the gateway process":

```bash
systemctl --user restart duckwork-gateway
```
