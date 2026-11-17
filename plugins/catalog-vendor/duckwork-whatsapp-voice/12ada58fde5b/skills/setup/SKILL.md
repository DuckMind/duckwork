---
name: setup
description: "Set up WhatsApp voice calls for Duckwork (duckwork-whatsapp-voice): install, link, run and test."
version: 1.0.0
author: hermes-whatsapp-voice
license: MIT
platforms: [linux, macos]
metadata:
  duckwork:
    tags: [WhatsApp, voice, calls, setup]
---

# Set up WhatsApp voice calls

You are setting up the `duckwork-whatsapp-voice` plugin for your owner. Work through the steps in
order. Run each command on the machine where Duckwork runs, check the expected result, and stop to ask
the owner only where a step says **Ask**. Never ask the owner to paste an API key or password into
the chat: every secret is read from Duckwork's own `.env`. Paths below assume the default Duckwork home
(`~/.duckwork`); if `DUCKWORK_HOME` is set or a profile is active, use that home instead.

Load this file in Duckwork with `skill_view("duckwork-whatsapp-voice:setup")`, or give its URL to any
coding agent: https://github.com/DuckMind/duckwork

## 0. Check the prerequisites

```bash
duckwork --version                     # expect 0.21.5 or newer
grep -E '^WHATSAPP_MODE=' ~/.duckwork/.env
grep -cE '^(GOOGLE_API_KEY|GEMINI_API_KEY)=' ~/.duckwork/.env   # expect 1 or more
```

- Unless the output is `WHATSAPP_MODE=bot`, stop. A missing line means self-chat mode. **Tell the
  owner** that voice calls need a separate bot number (Duckwork WhatsApp `bot` mode), because nobody
  can call their own number.
- If the Gemini count is 0: **Ask** the owner to add a Gemini API key to Duckwork with `duckwork model`
  (choose Gemini) or to `~/.duckwork/.env` as `GOOGLE_API_KEY=...`. Keys come from
  https://aistudio.google.com/apikey. Wait until the count is 1 or more.

## 1. Install the plugin

```bash
duckwork plugins install ashwanthbalakrishnan5/duckwork-whatsapp-voice --enable --yes-deps
```

Expect `Plugin duckwork-whatsapp-voice enabled.` If `duckwork plugins list` already shows it, run
`duckwork plugins update duckwork-whatsapp-voice` instead.

## 2. Set the owner's number

**Ask** for the owner's own WhatsApp number in international format (for example `+15551234567`).
This is the only number the plugin will ever call, and the only caller it answers.

```bash
duckwork config set plugins.entries.duckwork-whatsapp-voice.settings.owner_number +15551234567
```

## 3. Enable the Duckwork API server

The voice agent hands real work to Duckwork through it. Skip this step if both lines already exist.

```bash
grep -E '^API_SERVER_(ENABLED|KEY)=' ~/.duckwork/.env
```

If they're missing, append them (generate the key; never print it in chat):

```bash
grep -q '^API_SERVER_ENABLED=' ~/.duckwork/.env || echo 'API_SERVER_ENABLED=true' >> ~/.duckwork/.env
grep -q '^API_SERVER_KEY=' ~/.duckwork/.env || echo "API_SERVER_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> ~/.duckwork/.env
```

Then restart the gateway: `duckwork gateway restart` (or restart the service the owner runs it as). Check it listens:
`curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8642/v1/runs/x` should print `401`
or `404`, not `000`.

## 4. Link the sidecar to the bot's WhatsApp number (needs the owner)

The plugin's sidecar becomes one more linked device of the **bot's** number. It can't reuse
Duckwork's existing WhatsApp login, because WhatsApp allows only one live connection per linked
device. **Ask** the owner to have the bot's phone in hand, then use one of:

- **Dashboard (easiest):** the owner opens the Duckwork dashboard, goes to the **WhatsApp Voice** tab,
  clicks **Pair with WhatsApp**, and scans the QR from the bot's phone (WhatsApp > Linked devices >
  Link a device).
- **Terminal QR:** run `duckwork whatsapp-voice pair` in a terminal the owner can see, and they
  scan it.
- **Pair code (works over SSH):** run `duckwork whatsapp-voice pair --phone <bot number>`, and tell
  the owner the 8-character code to enter under Linked devices > Link a device > Link with phone
  number instead. They must confirm on the phone promptly; if it fails with `hmac-mismatch`, use a
  QR instead.

The first run downloads the sidecar binary (checksum-verified). Linking is done when the output
says `Linked.` or the dashboard shows **Linked**.

## 5. Keep the sidecar running

```bash
duckwork whatsapp-voice service
```

This prints a systemd user unit (Linux) or a launchd plist (macOS), with instructions in its
comments. Save it to the path shown and enable it. On Linux:

```bash
mkdir -p ~/.config/systemd/user
duckwork whatsapp-voice service | grep -v '^#' > ~/.config/systemd/user/duckwork-whatsapp-voice.service
systemctl --user daemon-reload && systemctl --user enable --now duckwork-whatsapp-voice
loginctl enable-linger "$USER"     # keeps it running while logged out
```

Check: `duckwork whatsapp-voice status` shows `"logged_in": true` and `"duckwork_connected": true`.

## 6. Test it with the owner

1. **Ask** the owner to call the bot's number from their phone. The voice should answer within a
   second or two and greet them in Duckwork's own persona.
2. Run `duckwork whatsapp-voice call "Quick test of the voice line"`. Their phone should ring. Once
   they answer, `duckwork whatsapp-voice status` shows the call.

After each call the owner gets a short WhatsApp summary.

## 7. Offer customization

Tell the owner what they can change, in the dashboard's **WhatsApp Voice** tab, the Desktop app's
plugin settings, or `duckwork config set plugins.entries.duckwork-whatsapp-voice.settings.<key> <value>`:

- `voice_instructions`: tone, call length, how to pronounce names (for example "keep calls very short").
- `languages`: language codes the voice may speak and listen for, for example `en-US, ta-IN`.
- `voice`, `voice_model`, `assistant_name`, `ring_timeout_seconds`, `max_call_minutes`,
  `answer_inbound`, `send_summary`.
- `live_config`: any Gemini Live setup field (https://ai.google.dev/api/live).

Saving in the dashboard applies changes. After `duckwork config set`, restart the sidecar:
`systemctl --user restart duckwork-whatsapp-voice` (Linux) or
`launchctl kickstart -k gui/$(id -u)/com.duckwork.whatsapp-voice` (macOS).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No Gemini API key found` | Step 0: add a Gemini key to Duckwork. |
| `sidecar not reachable` | The service isn't running: `systemctl --user status duckwork-whatsapp-voice` (Linux) or `launchctl list | grep whatsapp-voice` (macOS). |
| Service exits with `not linked to WhatsApp yet` | Step 4, then start the service again. |
| Calls connect but the voice can't do things | `duckwork_connected` is false: step 3. |
| Owner's calls aren't answered | `owner_number` must match the calling phone exactly (country code included). |
| Logs | `journalctl --user -u duckwork-whatsapp-voice -e` (Linux) or `~/.duckwork/plugin-data/duckwork-whatsapp-voice/sidecar.log` (macOS) |
