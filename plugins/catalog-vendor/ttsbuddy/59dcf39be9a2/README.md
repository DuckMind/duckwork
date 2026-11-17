# TTS Buddy for Duckwork Agent

This native Duckwork provider invokes the installed TTS Buddy CLI for authentication, submission, polling, and MP3 downloads. The CLI sends synthesis text to the TTS Buddy API and uses the account's available usage quota; each synthesis is marked with the `agent` execution context. The plugin does not install software, log in, or purchase plans. Speech was validated with Duckwork Agent 0.21.7 and TTS Buddy CLI 0.15.1; account deletion forwarding requires TTS Buddy CLI 0.16.0 or newer. The minimum Duckwork version is 0.21.7.

## Install

Run this on the machine that runs Duckwork:

```bash
duckwork plugins install ngelik/ttsbuddy-cli/plugins/duckwork-ttsbuddy --enable
```

For a reproducible install, add `--ref <full-40-character-commit-sha>`. Duckwork accepts an exact commit SHA for `--ref`, not a branch name or tag. Install the TTS Buddy CLI separately and make it available to the Duckwork process.

The default plugin directory is `~/.duckwork/plugins/ttsbuddy/` (or `$DUCKWORK_HOME/plugins/ttsbuddy/`). With a remote Duckwork backend, install the plugin and CLI on that remote host. Paths passed to the provider refer to files on the host executing Duckwork.

## Configure

Set the global TTS provider and voice in the Duckwork profile's `config.yaml`:

```yaml
tts:
  provider: ttsbuddy
  voice: st_m1
  speed: 1.0
```

The plugin's ordinary per-profile settings live under `plugins.entries.ttsbuddy.settings`:

```yaml
plugins:
  entries:
    ttsbuddy:
      settings:
        cli_path: /usr/local/bin/ttsbuddy
        cli_config_dir: /home/duckwork/.config/ttsbuddy
        language: fr
        poll_timeout_seconds: 600
```

`cli_path` defaults to `ttsbuddy`. `cli_config_dir` is optional. `language` applies only to Supertonic voices. `poll_timeout_seconds` must be between 30 and 1800. The voice picker reads the CLI's curated offline catalog; voice IDs select the engine, so there is no separate model setting.

Choose one credential route for the active profile:

- **Profile secret:** set the plugin's masked `api_key` field in Duckwork **Settings → Plugins**. Duckwork stores it as the profile-scoped `TTSBUDDY_API_KEY`; the plugin passes it only to the TTS Buddy CLI process.
- **Existing CLI login:** set `cli_config_dir` to the absolute directory containing the CLI configuration you selected. The plugin passes that directory to the CLI and never opens credential files.

If both are configured, the profile secret takes precedence. The plugin resolves the current profile settings and secret for each call. It removes inherited `TTSBUDDY_*` variables from the CLI child environment so ambient endpoint, key, and config overrides cannot redirect the request.

## Audio and recovery

The CLI downloads MP3. Duckwork 0.21.7 can convert that artifact to Opus for voice-bubble platforms; the provider does not stream PCM. When another output format is requested, the saved file is still MP3 and uses an `.mp3` filename. TTS Buddy supports speed from `0.5` through `1.5`.

The provider stages and verifies the MP3, publishes it without replacing an existing MP3, and checks that the reported path and byte count match. Duckwork 0.21.7 stages synthesis beside an existing requested output, so a failed synthesis preserves that existing file. On successful delivery, Duckwork may still replace the requested path, and MP3-to-Opus conversion may write a same-stem `.ogg`. **Use the default timestamped output or provide a fresh, unique output path and stem on every call.**

The plugin launches the CLI as a subprocess and passes speech text through standard input. The CLI may read or update its own configuration and job state in the selected `cli_config_dir`; the plugin does not open CLI credential files. With the profile-secret route, Duckwork supplies the API key to the CLI process. With the existing CLI login route, the CLI uses credentials from the selected CLI profile.

A local timeout or interruption stops the CLI process and removes partial local files; it does not cancel a hosted job. If Duckwork reports a known job ID, use its `ttsbuddy_recover` tool with that exact ID and a new output path. Recovery uses the same profile credential route and invokes the CLI's download command for that existing job; it never submits speech. If the outcome is uncertain and no job ID is available, keep the returned idempotency key and do not retry with a different key.

Authentication, quota, rate-limit, and provider errors are returned without raw CLI output, credentials, or signed audio URLs. For account or CLI help, contact [support@ttsbuddy.com](mailto:support@ttsbuddy.com). For the CLI's existing authentication and setup guidance, see the [canonical TTS Buddy CLI skill](https://github.com/ngelik/ttsbuddy-cli/tree/main/skills/tts-buddy).

## Account deletion (TTS Buddy CLI 0.16.0+)

Account deletion is available only from the local Duckwork terminal through the registered `duckwork ttsbuddy` CLI command. The `/ttsbuddy-account` chat command provides guidance only; it never accepts deletion instructions or verification codes. Deletion requires fresh verification of an existing account and permanently removes cloud files, credentials, and identity, while cancelling subscriptions. Local downloaded audio remains.

All deletion stages require an existing, absolute `cli_config_dir` explicitly selected in the active Duckwork profile. The same CLI config directory must be selected for `start`, `confirm`, `status`, and `cancel`, because the TTS Buddy CLI owns the protected continuation and recovery state there. The plugin does not open CLI credential or recovery files. A configured speech `api_key` does not authorize deletion and is never passed to these commands; account deletion uses the selected CLI profile even when the speech secret is also configured. The plugin checks for CLI 0.16.0 before running a deletion stage; older versions continue to support speech.

```text
duckwork ttsbuddy account delete start --email <existing-account-email>
duckwork ttsbuddy account delete confirm --challenge-id <id> --confirm-email <exact-email> --yes
duckwork ttsbuddy account delete status --challenge-id <id>
duckwork ttsbuddy account delete cancel --challenge-id <id>
```

`confirm` requires both the exact prepared email and explicit `--yes`. In a terminal, the plugin prompts for the six-digit email code without echoing it; press Enter only when reusing proof already retained by the CLI. Alternatively, pass `--code-stdin` and provide at most eight bytes of protected input. The code is forwarded only through the child CLI's stdin and is never placed in arguments or receipts. `status` reads stdin only when its own `--code-stdin` flag is explicitly supplied; it delegates verification and GET-only status recovery to the CLI and never submits deletion. An empty code input lets the CLI decide whether verified proof is already retained.

`cancel` revokes an unused challenge and cannot undo a submitted deletion. Use `--apple-manual-fallback-confirmed` only if the service requires manual Sign in with Apple revocation and the account owner accepts that step. The wrapper makes one CLI call per stage and does not retry. It emits allowlisted JSON while preserving safe challenge, request, and correlation IDs, state, partial-cleanup indicators, and the CLI exit status; unknown or incomplete outcomes remain nonzero and should be checked with `status` using the same config directory.

## Deterministic tests

The tests use fake CLI processes and do not contact TTS Buddy. With a pinned Duckwork checkout and its PM test interpreter, run:

```bash
make test-duckwork-plugin \
  DUCKWORK_SOURCE=/path/to/duckwork-agent \
  DUCKWORK_PYTHON=/path/to/duckwork-test-env/bin/python
```
