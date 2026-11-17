# duckwork-protonpass

Proton Pass secret source for [Duckwork Agent](https://github.com/DuckMind/duckwork).
At startup Duckwork resolves `pass://vault/item/field` references (or a whole vault) through the
official [`pass-cli`](https://protonpass.github.io/pass-cli/) and puts the values in its
environment, so provider keys don't have to sit in plaintext in `~/.duckwork/.env`.

It covers the same ground as the bundled 1Password and Bitwarden sources:

| Bundled source | This plugin |
|---|---|
| 1Password `op://` env map | `protonpass`: ENV_VAR -> `pass://vault/item/field` |
| Bitwarden Secrets Manager project | `protonpass_vault`: every env-var-titled item of one vault |
| `duckwork secrets onepassword setup/status/token/set/remove/sync/disable` | `duckwork protonpass setup/status/token/set/remove/sync/disable` |
| Service-account token or desktop session | Personal access token, AI-agent token, or your own `pass-cli login` session |

Precedence, conflict warnings, protected bootstrap tokens, timeouts and the `(from Proton Pass)`
provenance labels are handled by Duckwork' secret-source orchestrator, as for the bundled sources.

## Requirements

- Duckwork Agent >= 0.20.1
- `pass-cli` installed by you, following
  [Proton's installation guide](https://protonpass.github.io/pass-cli/get-started/installation/)
  (the plugin never downloads binaries). Live-tested with pass-cli 2.4.2; error handling also
  verified against 2.1.2.
- A Proton Pass plan with CLI access

## Install

```bash
duckwork plugins install lucas-nicolas/duckwork-protonpass --enable
```

## Set up (headless server, recommended)

Create a scoped, expiring token on any machine where you are logged in to `pass-cli`.
An **AI-agent token** is a personal access token that also writes every read, with its reason,
to an end-to-end-encrypted audit log (`pass-cli agent monitor duckwork`):

```bash
pass-cli agent create duckwork --expiration 1m --vault "Duckwork"
# or a plain personal access token:
#   pass-cli pat create --name duckwork --expiration 1m
#   pass-cli pat access grant --personal-access-token-name duckwork --vault-name Duckwork --role viewer
```

Then on the Duckwork host:

```bash
duckwork protonpass setup --token 'pst_...::...'      # verified with Proton before it is saved to ~/.duckwork/.env
duckwork protonpass set OPENAI_API_KEY    "pass://Duckwork/OpenAI/password"
duckwork protonpass set ANTHROPIC_API_KEY "pass://Duckwork/Anthropic/api key"
duckwork protonpass sync                                # dry run: shows what would apply, never the values
```

Bulk mode (Bitwarden-style): items whose **title** is a valid env-var name, e.g. an item titled
`GROQ_API_KEY`, contribute their `password` field (or `--field`):

```bash
duckwork protonpass setup --vault "Duckwork"   # enables protonpass_vault for that vault
```

Explicit mappings beat bulk values on the same variable. Bulk mode needs a plain personal access
token: Proton refuses `--show-secrets` listings for agent tokens.

### Using your own login instead of a token

If no token is set, the plugin uses whatever `pass-cli login` session the Duckwork process can see
and never logs in itself. Fine on a laptop; processes that don't share your session (cron, a
systemd gateway, Docker) will warn and fall back to `.env`, so use a token there.

## Configuration

```yaml
secrets:
  protonpass:
    enabled: true
    env:
      OPENAI_API_KEY: "pass://Duckwork/OpenAI/password"
    token_env: PROTON_PASS_PERSONAL_ACCESS_TOKEN   # env var holding the token; unset var = own session
    binary_path: ""            # pin pass-cli; when set, PATH is not consulted
    key_provider: fs           # PROTON_PASS_KEY_PROVIDER for the plugin-owned token session
    cache_ttl_seconds: 300     # 0 disables memory + disk cache
    override_existing: true    # vault values win over stale .env lines
  protonpass_vault:
    enabled: false
    vault: "Duckwork"            # vault name
    field: password
```

References can use names or IDs for the vault and item (`pass://<share id>/<item id>/<field>`
is unambiguous when titles are duplicated). The field segment is required.

## How it works

1. `duckwork` starts, loads `~/.duckwork/.env`, then calls the source.
2. With a token: under a file lock, the plugin logs in once into its own session directory
   `~/.duckwork/cache/protonpass/<token fingerprint>/` (0700). PAT and agent sessions last 2 hours;
   the plugin logs in again after 110 minutes, or once on an authentication error.
3. Each reference is one `pass-cli item view -- <ref>` call with
   `PROTON_PASS_AGENT_REASON="Duckwork startup: load <ENV_VAR>"`, so an agent token's audit log
   shows which variable read which item.
4. A pull where every reference resolved is cached for `cache_ttl_seconds` (in memory and in
   `~/.duckwork/cache/protonpass_cache.json`, 0600). Partial pulls are never cached.

Failures never block startup: you get one warning line, a `→` hint with the command that fixes it,
and Duckwork continues with whatever `.env` already had.

## Security and disclosure

- **Network:** only through your `pass-cli`, which talks to Proton's API. The plugin itself opens
  no sockets and sends no telemetry; it sets `PROTON_PASS_DISABLE_TELEMETRY=1` for pass-cli.
- **Token handling:** read from Duckwork' environment (`~/.duckwork/.env`), passed only to the
  `pass-cli login` child, in its environment, never on argv. Any echo of it in pass-cli errors is
  redacted. `duckwork protonpass token` verifies a new token before overwriting the old one.
- **Child processes:** argv only (no shell), an allowlisted environment (PATH, HOME, locale and
  `PROTON_PASS_*` tuning knobs; none of Duckwork' other credentials), stdin closed, 30 s timeout,
  references after `--`.
- **Files written:** the session directory above (pass-cli's encrypted session plus its local
  key when `key_provider: fs`; the token in `.env` can already recreate that session), the 0600
  value cache, and `secrets.protonpass*` in `config.yaml`. The `protonpass_cache.json` cache holds
  resolved values in plaintext like the bundled sources' caches; set `cache_ttl_seconds: 0` to
  keep values off disk.
- **Reads outside its own data:** in own-session mode, pass-cli (not the plugin) reads your
  pass-cli session from its default location.
- **No self-update, no downloaded binaries, no background processes.**

## Troubleshooting

| Warning | Fix |
|---|---|
| `pass-cli not found on PATH` | install pass-cli or set `binary_path` |
| `pass-cli login with the personal access token failed` | expired/revoked token: `duckwork protonpass token` |
| `This operation requires an authenticated client` | no token and no `pass-cli login` session visible to this process |
| `could not read 'pass://…'` | wrong vault/item/field, or the token has no access to that vault |
| `AI-agent tokens cannot list secrets` | bulk mode needs a plain personal access token |

## Development

```bash
git clone https://github.com/DuckMind/duckwork
uv sync --project duckwork-agent --locked --python 3.14   # Duckwork <= 0.21: --python 3.11
uv pip install --python duckwork-agent/.venv/bin/python pytest
duckwork-agent/.venv/bin/python -m pytest tests -q
```

The tests drive a fake `pass-cli` reproducing pass-cli's real messages and session layout
(identical in 2.1.2 and 2.4.2), plus Duckwork' own secret-source conformance kit. CI runs them on the
`requires_duckwork` floor, the latest release and Duckwork `main`.

`tests/live_e2e.py` is an opt-in end-to-end run against a **real** account (never in CI). It needs a
logged-in `pass-cli` and a sandbox vault it may write to; it creates two throwaway items, a 1-day
AI-agent token and a 1-day personal access token, checks own-session, agent-token and PAT modes
(values, provenance, session reuse across processes, Proton audit-log reasons, no token on argv or
outside `.env`), then deletes everything it created:

```bash
PP_E2E_VAULT=duckwork python3 tests/live_e2e.py   # prints booleans/lengths only, never values
```

Thanks to
[flamerged/duckwork-protonpass-plugin](https://github.com/DuckMind/duckwork),
whose documented pass-cli findings (three-segment URIs, the `item list` JSON shape) saved real
probing time; this is an independent, smaller implementation.

MIT licensed.
