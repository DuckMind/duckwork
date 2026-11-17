# Cursor SDK provider for Duckwork

**Experimental.** This plugin connects Duckwork to the official `@cursor/sdk` Agent SDK. It does not use a private API, browser cookies, or an OpenAI-compatible proxy.

This is a subscription-oriented integration, not a guarantee of free or included inference. Cursor decides entitlement and billing. An authenticated account or a model listing does not prove that requests are included in your subscription. Confirm your account's allowance and spending settings before using it. The plugin cannot enforce an included-only spending cap.

## Requirements

- Duckwork 0.22.0 or later, with the `ProviderProfile.create_client` plugin API.
- macOS or Linux, Node.js 22.13 or later, and Git on `PATH`.
- Credentials accepted by the official Cursor SDK, configured as `CURSOR_API_KEY` in the active Duckwork profile. Use Duckwork's credential setup. Do not paste a key into a command or this repository.

The SDK is pinned to `@cursor/sdk` 1.0.37. Windows is not supported by the current POSIX hook-command quoting.

## Install

Until the catalog entry is accepted, install from the repository:

```sh
duckwork plugins install https://github.com/DuckMind/duckwork
```

Review the plugin's subprocess and file-write permissions when prompted. In the installed plugin directory, install the pinned Node dependency:

```sh
cd ~/.duckwork/plugins/cursor-sdk
npm ci --ignore-scripts
```

For a named Duckwork profile, use that profile's plugin directory instead. Configure `CURSOR_API_KEY` through Duckwork, then select provider `cursor-sdk` and an exact model selection with `duckwork model`. Installation does not change your default provider automatically.

The CLI reports one row per base model from a bundled development catalog snapshot. `model-selections.json` also contains exact parameterized selections. The snapshot is not a live account entitlement check and may become outdated. Fast and Advanced picker controls, along with thinking and effort settings, require Duckwork to call the optional picker hooks. The plugin alone does not add those controls to older releases. Unsupported parameter combinations fail rather than silently switching models.

## How the transport works

Duckwork's instructions are written to a project-scoped Cursor rule, and the existing conversation is sent as structured text. This is not a native system-role override and has not been proven equivalent to Duckwork's normal prompt hierarchy.

Each request starts a local SDK agent in a separate plugin-owned Git workspace. Cursor's built-in tools are disabled except for the MCP callback transport. Project hooks deny native actions and permit only discovery and the offered Duckwork callbacks. A callback returns a tool request to Duckwork. It does not execute that tool. Duckwork retains responsibility for approvals, tool execution, and returning the genuine result on the next request.

The worker is disposed after a response. Workspaces and SDK state currently remain under the installed plugin's `runtime/` directory, which can contain private conversation data. Keep that directory private and manage its retention deliberately. This repository's ignore rules keep it out of Git. They are not a retention policy.

Credentials are read through Duckwork's profile-scoped secret accessor and passed only to the SDK subprocess. There is no direct credential-file read or automatic fallback to a different API provider. SDK failures are returned as fixed categories rather than raw messages that could disclose prompt or account data.

## Verification and limits

The package has offline Python transport/catalog tests and Node worker/hook tests. These tests use SDK fixtures and dummy credentials. They do not prove real inference, subscription billing, native-hook enforcement in every Cursor runtime, desktop activation, or acceptance by every listed model.

Other limits:

- Text-only messages. Image/vision handling is not implemented.
- SDK responses are buffered. OpenAI-shaped stream chunks are emitted after completion, not token by token.
- Cursor may require a separate data-retention acknowledgment for a model. The plugin does not accept it for you.
- Timeout/interrupt cleanup is tested offline. Live cancellation still needs qualification.
- The adapter uses Duckwork's internal OpenAI-shape and effort helpers. Those imports need compatibility review when Duckwork changes.

Do not use this experimental transport where strict prompt hierarchy or permission equivalence is a security requirement without independently qualifying the live SDK boundary.

## Run offline tests

Run from the plugin directory with a Python interpreter that has Duckwork and its dependencies available:

```sh
python -m unittest discover -s tests -v
npm test
duckwork plugins validate .
```

No inference request or real credential is needed for the test suites. No GitHub Actions workflow is included.

## References

- [Cursor SDK documentation](https://cursor.com/docs/sdk)
- [Duckwork model-provider plugin API](https://duckwork-agent.fordex.com/docs/developer-guide/model-provider-plugin)
- [Duckwork plugin catalog](https://github.com/DuckMind/duckwork)

License: MIT. Cursor SDK dependencies retain their own licenses and terms.
