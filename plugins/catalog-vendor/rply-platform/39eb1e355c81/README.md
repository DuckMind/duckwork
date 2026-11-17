# rply for Duckwork Agent

A [Duckwork Agent](https://duckwork-agent.fordex.com) messaging platform plugin for [rply](https://rply.sh), the inbox for agents that run without you. Write to Duckwork from the rply app on your phone or laptop, and get its replies, questions, approvals and scheduled job results there, with push notifications.

Full guide: https://github.com/DuckMind/duckwork

## Install

Requires Duckwork Agent 0.22.2 or newer.

```sh
duckwork plugins install https://github.com/DuckMind/duckwork --enable
duckwork gateway setup     # pick rply, enter the agent code from the rply app (or leave it empty to create a channel)
duckwork gateway restart
```

Without the setup menu (for example when Duckwork sets itself up from the rply app's setup prompt):

```sh
duckwork rply join https://app.rply.sh <agent-code>     # or: duckwork rply init https://app.rply.sh --name "Duckwork"
duckwork gateway restart                                # or duckwork gateway install, the first time
```

For more profiles, repeat with `duckwork -p <name> ...`. Each profile has its own copy of the plugin and joins the channel as its own agent.

## Features

- Messages both ways, with seen / working / done and a live note of what Duckwork is doing
- Images and files both ways
- Clarifying questions and dangerous-command approvals as rply questions
- `rply_request_secret` tool: API keys are encrypted on the human's device and saved to `.env`; Duckwork never sees the value
- Cron delivery (`--deliver rply`), a pinned table of scheduled jobs and a dashboard app with run / pause / resume
- One rply agent per Duckwork profile, addressed with `@name`

## Disclosures

- Network: talks only to the configured rply server (`RPLY_SERVER`, default https://app.rply.sh). It keeps a long-running connection (long-polling) for messages and dashboard calls.
- Reads outside its own data: Duckwork' scheduled jobs and session list (for the pinned table and the dashboard). Dashboard buttons run, pause and resume jobs.
- Stored credentials: the rply agent token in the profile's `.env` (written by `duckwork gateway setup`), an X25519 keypair for secrets in `<profile>/rply/secret-key.json` (mode 0600), and secrets the human sends, saved to the profile's `.env`.
- Background processes: none besides the gateway's own tasks. No shell commands, no telemetry, no self-updating.

## Files

- `adapter.py`: the platform adapter, the secret tool and the registration
- `sealed_box.py`: rply's sealed box (X25519 + HKDF-SHA256 + XChaCha20-Poly1305) for opening secrets
- `dashboard.html`: the dashboard app

## License

MIT (see `LICENSE`). The rest of rply is AGPL-3.0.
