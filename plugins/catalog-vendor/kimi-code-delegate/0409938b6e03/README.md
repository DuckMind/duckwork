# Duckwork Kimi Code

Standalone Duckwork Agent plugin for **explicit, read-only delegation** to a locally
authenticated Kimi Code CLI over ACP.

The plugin deliberately does **not** register Kimi as a Duckwork model provider. Kimi Code
0.29.2 does not expose a verified privileged system/developer instruction channel over ACP,
so using it for Duckwork primary, fallback, or auxiliary model turns would weaken instruction
priority. Duckwork remains the orchestrator and calls `kimi_code_delegate` only when delegation
is useful.

## Status

Version 0.1.0 is tested with Kimi Code 0.29.2 and Duckwork Agent upstream commit
`1dfe781edd5e96d09511cf27d800a03e63b09789`. Real, built-plugin delegation succeeds with both
`k3` and `k3-256k`; protocol, installation, disable/remove, timeout, capability-drift, and
side-effect-denial paths are covered separately.

An earlier exhausted-account smoke remains useful negative evidence: direct Kimi CLI mode
reported HTTP 403, while ACP returned only a textless `end_turn`. The plugin therefore reports
unknown provider status when ACP omits the cause and never guesses that an empty turn means
quota exhaustion.

## Security boundary

- One fresh `kimi acp` process and ACP session is created per tool call.
- The plugin never reads, copies, refreshes, or prints OAuth token contents.
- Kimi receives a small allowlisted environment and uses its own CLI-owned login under `HOME`
  or `KIMI_CODE_HOME`.
- ACP permission requests are rejected. Filesystem and terminal requests receive errors.
- No MCP servers are forwarded.
- Command and working directory are operator-owned `config.yaml` settings, never model input.
- Timeouts, wire-line limits, prompt limits, bounded stderr, and redaction are enforced.
- Empty responses are errors rather than successful turns.

The read-only instruction included in the delegated prompt is guidance, not a security
control. The ACP client-side denials are the security control.

## Prerequisites

- Duckwork Agent with pip plugin entry-point support
- Python 3.11 or newer
- Kimi Code CLI 0.29.2 or a compatible newer release
- An interactive Kimi CLI login completed directly with:

```bash
kimi login
```

## Installation

The preferred public installation path uses Duckwork' native Git plugin manager:

```bash
duckwork plugins install s-a-s-k-i-a/duckwork-kimi-code --enable
duckwork kimi-code doctor
```

Restart a running gateway after installation so it discovers the plugin. Duckwork clones the
repository into its own plugin directory and can update or remove it through the same CLI.

Alternatively, install the tagged Python package into the same environment as Duckwork:

```bash
python -m pip install "git+https://github.com/s-a-s-k-i-a/hermes-kimi-code.git@v0.1.0"
duckwork plugins enable kimi-code-delegate
duckwork kimi-code doctor
```

Pip entry-point and native Git discovery both use the plugin id `kimi-code-delegate`. Neither
path patches Duckwork Core files.

## Configuration

All behavioral settings live in `config.yaml`, following Duckwork policy for non-secret
configuration:

```yaml
plugins:
  enabled:
    - kimi-code-delegate
  entries:
    kimi-code-delegate:
      # Optional. Defaults to ~/.kimi-code/bin/kimi, then PATH.
      command: /absolute/path/to/kimi
      # Optional. Defaults to the Duckwork process working directory.
      working_directory: /absolute/read-only-context/root
      timeout_seconds: 300
      startup_timeout_seconds: 10
      model: k3
      # Optional. Auto negotiates Kimi ACP's current session value.
      thinking: auto
```

The command is executed directly as `[command, "acp"]`; no shell and no configurable argument
string are involved. Supported models are `k3` and `k3-256k`. Thinking defaults to `auto`, which
uses the current value advertised by the ACP session. Explicit values are `low`, `high`, and
`max` in Kimi Code 0.29.2. Future option ids are accepted by configuration but applied only when
the installed ACP session advertises that exact value; unsupported values fail closed.

## Use

Duckwork sees one tool:

```text
kimi_code_delegate(prompt, model?, thinking?)
```

The prompt must be self-contained. Kimi cannot read local files, execute commands, call MCP
servers, or make changes through this plugin. If context is needed, Duckwork must include the
relevant non-secret text in the delegated prompt.

Run a no-inference preflight at any time:

```bash
duckwork kimi-code doctor
duckwork kimi-code doctor --json
```

The doctor checks executable startup, ACP identity/capabilities, and whether Kimi accepts the
ACP `login` handshake. Kimi Code 0.29.2 may accept that handshake before a real prompt even
when the interactive CLI later requires `kimi login`, so Doctor reports OAuth as **unverified**.
Only a successful delegated prompt proves the live login. Doctor itself performs no inference.

When Kimi returns no text and no ACP error detail, the tool reports `empty_response`, states that
the provider status is unknown, and asks the user to check interactive login and account quota.
The structured result also confirms that Duckwork model routing was not changed and no ACP
approval request was forwarded to the user.

## Uninstall

For a native Git installation:

```bash
duckwork plugins disable kimi-code-delegate
duckwork plugins remove kimi-code-delegate
```

For a pip installation:

```bash
duckwork plugins disable kimi-code-delegate
python -m pip uninstall duckwork-kimi-code
```

Removing the package removes the tool. Duckwork Core remains untouched. You may separately
remove the corresponding `plugins.entries.kimi-code-delegate` configuration block.

## Project tracking and upstream relationship

- Tracking umbrella: [s-a-s-k-i-a/duckwork-agent#47](https://github.com/DuckMind/duckwork)
- Implementation: [#44](https://github.com/DuckMind/duckwork)
- Verification: [#45](https://github.com/DuckMind/duckwork)
- Release: [#46](https://github.com/DuckMind/duckwork)
- Thinking negotiation: [#48](https://github.com/DuckMind/duckwork)
- Quota-state UX: [#49](https://github.com/DuckMind/duckwork)
- Native distribution path: [#50](https://github.com/DuckMind/duckwork)
- Fail-closed boundary hardening: [#51](https://github.com/DuckMind/duckwork)

Generic ACP Core work already exists upstream in
[Fordex/duckwork-agent#68222](https://github.com/DuckMind/duckwork).
This plugin does not duplicate that PR and does not add a named Kimi integration to Core.

## Author

Saskia Teichmann ([@s-a-s-k-i-a](https://github.com/s-a-s-k-i-a)).
