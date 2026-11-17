# Duckwork Cloudflare Sandbox

[![Test](https://github.com/DuckMind/duckwork)](https://github.com/DuckMind/duckwork)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**English** | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

Run the Duckwork Agent terminal in a Cloudflare Container: commands, files and `execute_code` run remotely, and the workspace is saved to a snapshot when idle.

A terminal backend plugin for [Duckwork Agent](https://github.com/DuckMind/duckwork). Each workspace is a Cloudflare Container managed by a Durable Object; Duckwork itself stays on your machine or server.

**Status: early.** Tested against a real Cloudflare account and Duckwork install (see [VALIDATION.md](VALIDATION.md), in Japanese). It uses Cloudflare's `durable_object` scheduling policy and `ctx.container` API, which are in public beta.

```text
Duckwork Agent
  └─ terminal backend: cloudflare_sandbox
       └─ HTTPS + bearer token
            └─ Cloudflare Worker
                 └─ Durable Object (one per workspace)
                      └─ Container: Bash / Python / Node.js, /workspace, snapshots
```

## Features

- Runs Duckwork' `terminal`, file tools and `execute_code` in the container.
- Streams UTF-8 output, with stdin, exit codes, timeouts and cancellation.
- Named images and per-workspace instance types.
- Saves an idle workspace to a snapshot and restores it on the next command.

Browser tools, skills, credentials and your home directory stay on the host and are not synced into the container.

## Requirements

- A Duckwork version with terminal environment provider plugins
- Python 3.11+, Node.js 22+ and Docker
- A Cloudflare account with Containers. **Running containers is billed.**

## 1. Deploy the Worker

```bash
git clone https://github.com/DuckMind/duckwork
cd duckwork-cloudflare-sandbox/worker
npm ci
npm test
npm run typecheck
npx wrangler login
npm run deploy
```

The Worker rejects every request until a secret is set. Generate one and store it:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
npx wrangler secret put SANDBOX_API_TOKEN
```

Use the same value as `DUCKWORK_CF_TOKEN` in Duckwork. Do not commit it or put it in `wrangler.jsonc` or the container image.

`worker/wrangler.jsonc` sets the image (`duckwork`), the default instance type (`standard-1`) and the allowed types (`ALLOWED_INSTANCE_TYPES`). `ENABLE_INTERNET=true` allows outbound traffic for git and package managers; set it to `false` to block it.

## 2. Install the plugin in Duckwork

```bash
mkdir -p "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins"
git clone https://github.com/DuckMind/duckwork \
  "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/cloudflare-sandbox"
```

Add these to the profile's `.env` (optional settings are in `.env.sample`):

```dotenv
DUCKWORK_CF_ENDPOINT=https://your-worker.your-subdomain.workers.dev
DUCKWORK_CF_TOKEN=the-secret-you-generated
DUCKWORK_CF_NAMESPACE=personal
DUCKWORK_CF_IMAGE=duckwork
```

```bash
duckwork plugins enable cloudflare-sandbox
duckwork config set terminal.backend cloudflare_sandbox
duckwork config set terminal.cwd /workspace
duckwork config set terminal.container_persistent true
```

Restart Duckwork afterwards. To keep your usual profile on the local terminal, try it in a separate profile first (`duckwork profile create <name> --clone`).

## 3. Verify

Run these from the repository root.

```bash
python scripts/check_duckwork_contract.py --duckwork-source /path/to/duckwork-agent
python scripts/smoke.py --live
```

The first command checks that your Duckwork has the interfaces this plugin needs. The second needs `DUCKWORK_CF_ENDPOINT` and `DUCKWORK_CF_TOKEN` in the environment; it runs commands, saves and restores a snapshot in a temporary workspace, then deletes the workspace. It is billed like normal use.

## Workspaces and persistence

With `container_persistent: true`, the namespace and Duckwork' task ID select the workspace, and its files are kept between sessions. To share one workspace across task IDs or machines, set the same `DUCKWORK_CF_NAMESPACE` and `DUCKWORK_CF_WORKSPACE` (for example `my-project`). Do not use one workspace from several Duckwork processes at the same time.

With `container_persistent: false`, the workspace is deleted when the session ends.

When a session ends, or after about 10 minutes without commands (`IDLE_SECONDS` in `wrangler.jsonc`), the workspace is saved to a snapshot and the container stops. If saving fails, the container keeps running and the save is retried.

**Snapshots are not backups.** They contain files only, so running processes (including background jobs) do not survive. Cloudflare deletes a snapshot 30 days after it is created or restored. Keep important work in git.

If a container is lost before any snapshot exists, the Worker returns `workspace_lost` instead of starting an empty workspace. Use a new workspace name.

## Configuration

| Setting | Meaning |
| --- | --- |
| `terminal.container_persistent` | Keep the workspace in snapshots between sessions. |
| `terminal.cwd` | Working directory inside the container. Default `/workspace`. |
| `DUCKWORK_CF_IMAGE` | An image name defined in `wrangler.jsonc`. |
| `DUCKWORK_CF_INSTANCE` | `lite` or `standard-1` to `standard-4`, and also listed in `ALLOWED_INSTANCE_TYPES`. |
| `DUCKWORK_CF_ACCESS_CLIENT_ID`, `DUCKWORK_CF_ACCESS_CLIENT_SECRET` | A Cloudflare Access service token, if the Worker is behind Access. |

Duckwork' generic container image, CPU, memory and disk settings are not used.

## Security

The bearer token gives full control: whoever holds it can run any command in every workspace. The bridge is meant for a single owner and has no per-user permissions, concurrency limits or spending caps. If others can reach the Worker, put Cloudflare Access in front of it.

The token is never passed into the container, but anything you write inside the container ends up in snapshots.

Duckwork still asks for approval before dangerous commands, so in unattended runs such as `duckwork chat -q`, `execute_code` is blocked unless you allow it in Duckwork' approval settings or with `--yolo`.

## Limits and behavior

| Item | Limit |
| --- | --- |
| Command string | 64 KiB |
| Request body | 1 MiB |
| Output per command | 2,000,000 characters |
| Run time per command | 900 seconds |

Output over the limit is an error, never a truncated result. stdout and stderr are merged, and stdin must be UTF-8 text.

A command that times out gets SIGTERM, then SIGKILL 2 seconds later. Background jobs (`cmd &`) keep running after the command returns; their output is collected for at most 5 seconds afterwards, so redirect it to a file if you need all of it.

If the connection drops, the command may already have run. Nothing is retried automatically.

The Worker API is described in [docs/protocol.md](docs/protocol.md).

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
cd worker
npm ci
npm test
npm run typecheck
```

## References

- [Duckwork terminal environment provider plugins](https://github.com/DuckMind/duckwork)
- [Cloudflare Durable Object Container API](https://developers.cloudflare.com/containers/api/durable-object-container/)
- [Cloudflare scheduling policies](https://developers.cloudflare.com/containers/configuration/scheduling-policy/)
- [Cloudflare snapshots](https://developers.cloudflare.com/containers/guides/snapshots/)

## License

[MIT](LICENSE). Parts of the container supervisor are based on [openclaw/crabbox](https://github.com/openclaw/crabbox) (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
