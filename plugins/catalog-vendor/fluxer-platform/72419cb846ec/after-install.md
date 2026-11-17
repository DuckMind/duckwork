# Fluxer plugin installed

Fluxer support is installed, but it still needs a bot token and an explicit user allowlist before Duckwork will answer messages.

## 1. Enable the platform

```bash
duckwork config set platforms.fluxer.enabled true
```

## 2. Add your bot token

Append this to `~/.duckwork/.env`. Do not replace an existing `.env` file wholesale:

```bash
FLUXER_BOT_TOKEN=<fluxer-bot-token>
```

Keep the real token private.

## 3. Allow users

The adapter is deny-by-default. If you skip this, Duckwork can connect to Fluxer but will ignore inbound messages.

Recommended:

```bash
FLUXER_ALLOWED_USERS=your_fluxer_user_id
```

Development only:

```bash
FLUXER_ALLOW_ALL_USERS=true
```

## 4. Optional home channel

For cron jobs and default Fluxer notifications:

```bash
FLUXER_HOME_CHANNEL=your_default_channel_or_dm_id
FLUXER_HOME_CHANNEL_NAME="Fluxer Home"
```

## 5. Optional realtime voice auto-join

Realtime voice is disabled by default. To let the plugin-managed supervisor automatically join specific voice rooms after the Fluxer gateway connects, add:

```bash
FLUXER_VOICE_ENABLED=true
FLUXER_VOICE_AUTO_JOIN=true
FLUXER_VOICE_BRAIN_PROVIDER=duckwork
FLUXER_VOICE_TARGET_USER_IDS=your_fluxer_user_id
FLUXER_VOICE_CHANNEL_IDS=your_voice_channel_id
```

Or configure the equivalent `platforms.fluxer.extra.voice` block in `~/.duckwork/config.yaml`, or use **Duckwork Dashboard → Config → Fluxer**. `brain_provider: duckwork` is the default/recommended mode for full Duckwork session persistence and Honcho ingestion; `auto` and `xai-fast` are explicit latency trade-offs. Auto-join refuses to arm unless both target user IDs and channel IDs are set, so an enabled plugin cannot silently listen to arbitrary users. Keep any deployment-local assistant/personality context outside the repo and point to it with `FLUXER_VOICE_CONTEXT_FILE` only if needed. `FLUXER_VOICE_SUPERVISOR_DISABLED` is an internal child-process recursion guard and should normally be left empty/false.

For the full 43-field voice config reference, hardware/provider tuning notes, VAD guidance, and troubleshooting, read `docs/voice-configuration.md`.

## 6. Restart and test

```bash
duckwork gateway restart
```

Test delivery from Duckwork:

```python
send_message(target="fluxer:<channel_id>", message="Fluxer plugin is alive.")
```

For the full explanation of Fluxer, Duckwork wiring, safety defaults, group-chat behavior, and troubleshooting, read `README.md`.
