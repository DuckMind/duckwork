# v0.1.2 — authenticated Cloudflare routing and onboarding

This is a community prerelease of **ourines/duckwork-jev**, an explicit decision-sidekick plugin. It is not an official TypeSafe, Cloudflare or Fordex integration. The main Duckwork chat model and execution permissions are unchanged.

## Changes since v0.1.1

- Support an explicitly configured authenticated Cloudflare AI Gateway via `--gateway-id`, without creating gateways, changing billing or touching generic Cloudflare credentials.
- Send gateway privacy/cache/attempt controls; explain Cloudflare error code 2049 with bounded, sanitized diagnostics rather than exposing raw error responses.
- Accept the observed Cloudflare `result.result` response envelope with bounded unwrapping and fail-closed checks at each layer.
- Add offline `duckwork jev guide`, clearer local-only `status`, and post-setup guidance.
- Bundle an optional ordinary `jev` companion skill for first-mention discovery, with native-tool/CLI fallback and explicit billing boundaries. It must be installed explicitly into the active profile; plugin loading does not write user skills.

## Installation

```sh
duckwork plugins install ourines/duckwork-jev --enable
duckwork jev guide
duckwork jev setup --backend typesafe
# Or use Cloudflare:
# duckwork jev setup --backend cloudflare --account-id YOUR_ACCOUNT_ID --gateway-id YOUR_GATEWAY_ID
```

The repository shorthand above tracks the default branch. For immutable installation, add `--ref` followed by the full 40-character commit SHA resolved by the release tag; `--ref` does not accept a tag name. Setup takes hidden terminal input and makes one tiny potentially billed validation request before saving a credential. `guide`, `status` and `presets` do not call Jev.

A long-running Duckwork Desktop backend may need a full restart to discover a newly installed native plugin. Opening a new chat alone is not a guaranteed reload. Do not interrupt active work; the CLI remains a fallback.

## Verification and limits

- 46 tests pass in the local Duckwork runtime, including profile-isolation integration.
- Isolated Python 3.11 and 3.12 runs each discover 46 tests: 45 pass and the real-Duckwork profile integration test is skipped because Duckwork is not installed in those environments.
- Local `duckwork plugins validate`, `doctor --ci` and `compat` checks pass; the admission scanner reports `safe`.
- Cloudflare connectivity and a small Chinese Noul/Choice/Score smoke test were verified against `jev-1.13.0`. These are connectivity/basic-semantic checks, not a business-accuracy benchmark.
- TypeSafe direct-account live validation, real-workload accuracy, held-out calibration and comparative latency/cost remain unverified.
- GitHub Actions results are tracked on the exact release commit; local results above do not claim a remote CI result.

## Security and scope

The plugin exposes one tool, `jev_evaluate`, and the `duckwork jev` CLI. It registers no hooks or middleware, has no self-updater, does not intercept other tools, and never authorizes execution. Provider responses cannot override local `ok`, advisory or permission fields. Credentials remain in the active Duckwork profile's credential lifecycle. Send only the minimum task context required; external-provider inference can be billed.

Official catalog admission is a separate maintainer-reviewed PR. Publishing this release does not imply official catalog acceptance.
