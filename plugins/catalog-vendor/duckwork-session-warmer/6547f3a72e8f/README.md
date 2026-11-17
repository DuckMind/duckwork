# Duckwork Session Warmer

Opt-in, bounded idle prompt warming for Duckwork Agent and explicitly allowlisted OpenAI-compatible Chat Completions endpoints.

Inspired by [OpenCode v2 session warming](https://opencode.ai/v2/docs/warming/). This is an independent community plugin, not an OpenCode integration or an official Fordex product. It makes real, potentially billable model requests. It does not guarantee a cache hit, lower cost, or faster replies.

## What it does

After a successful Duckwork turn, the plugin retains an in-memory copy of the latest supported request and final assistant text. After four idle minutes it sends a single non-streaming completion with a transient maintenance instruction, then discards the generated response. It repeats within a 30-minute idle window, up to seven attempts per session. Real activity invalidates the old snapshot; warming never extends that window.

There are no model-facing tools, no tool execution loop, no transcript writes, no self-updater, and no additional Python dependencies. `/warming status` reports aggregate counters without prompts, session IDs, credentials, or model output. `/warming stop` clears snapshots and stops future requests until plugin reload/restart. Unloading the plugin also stops it.

## Compatibility and limits

Version 0.1.0 supports text-only OpenAI-compatible `/chat/completions` requests with ordinary function tool schemas. It requires the Duckwork `llm_request` middleware, lifecycle hooks, `ctx.get_config`, and `ctx.on_unload` APIs. Tested against Duckwork source commit `28aceb3451f5a5d2a27396b2adf29231be34c482`; no untested minimum version is claimed.

Not supported: Codex OAuth/Responses, native Anthropic Messages, Bedrock, multimodal requests, server-side tools, arbitrary `extra_body`/headers, or automatic provider credential borrowing. Unknown request fields fail closed. This does NOT enable warming for a Codex-backed Duckwork chat. A dedicated optional environment credential is used rather than reading Duckwork credential stores or retaining a provider execution callback beyond its lifetime.

Exact endpoint and model matching are mandatory. Configure the same provider account/project as the real conversation; cross-account cache sharing is not promised. Other request-mutating middleware after this plugin can make the captured request diverge: do not combine with routing/prompt-rewriting middleware unless you have verified the final request matches. Dedicated credentials, separate routing, and changed tool-choice settings can prevent cache reuse even when visible messages match.

## Install

Before catalog acceptance, install by repository URL (custom, unreviewed source):

```sh
duckwork plugins install mojomast/duckwork-session-warmer --no-enable
duckwork plugins enable duckwork-session-warmer
```

Review the code before enabling. Installing/enabling alone does not start warming: `warming.enabled` must also be explicitly true. Restart the relevant Duckwork process after installing.

## Configure

Merge this into the intended profile's `config.yaml`; preserve your other entries. Example is for a local compatible server, not a promise that one is running:

```yaml
plugins:
  enabled:
    - duckwork-session-warmer
  entries:
    duckwork-session-warmer:
      settings:
        warming:
          enabled: true
          base_url: http://127.0.0.1:8080/v1
          models: [your-exact-model-id]
          interval_seconds: 240
          idle_window_seconds: 1800
          max_requests: 7
          max_sessions: 4
          max_payload_bytes: 524288
          timeout_seconds: 15
```

For an authenticated service, provision `DUCKWORK_SESSION_WARMER_API_KEY` through your secret manager or the profile's protected environment configuration, never in this YAML, prompts, logs, or shell arguments. It is optional for unauthenticated loopback servers. The plugin reads only this explicitly named variable, not your existing OpenAI/Codex/Anthropic credentials. Remote endpoints require HTTPS; plain HTTP is restricted to loopback. Redirects and environment proxies are disabled, to avoid silently changing the credential destination. Custom proxy/organization headers are not supported.

Invalid configuration stays off. Intervals are 30–3600 seconds; windows 30–7200 seconds; attempts 1–30; sessions 1–16; payload caps 1024–2097152 bytes; socket timeouts 1–60 seconds. Window must be at least the interval (equal means expiry before any warming). Config changes invalidate existing snapshots; a new real turn is required to arm again. Configuration reads remain bound to the plugin's registration profile, including on its background thread.

## Safety, privacy and billing

The existing conversation is resent only to the explicitly configured matching endpoint. Copies remain in process memory and are cleared on activity, expiry, stop, unload, or a warming error. Crashes/process exit lose snapshots. No analytics, persistent prompt files, external control server, or background subprocess is created.

Function schemas are preserved, but `tool_choice` becomes `none`; there is no dispatcher even if a provider returns tool calls anyway. A one-token output budget, `n=1`, and `stream=false` limit normal generation; provider billing/behavior remains outside this plugin's control. The circuit opens after one error for that idle period, with no automatic retry. A new successful real turn can arm again.

Each session has a bounded request count; this is not a dollar-denominated budget. A provider may charge for cache writes/reads, the full prompt, or reasoning even when output is tiny. Aggregate counters are process-local, not your provider's billing ledger. The snapshot byte cap is not a token estimator.

An already selected/in-flight HTTP request cannot be recalled by a new user turn, stop, unload, or config edit. Foreground activity is never held waiting on that request; stale completion cannot restore its snapshot. The HTTP timeout is a socket timeout, not a strict end-to-end deadline against a malicious slow-drip server. One background worker serializes warming; multiple Duckwork processes each have their own budgets.

Manual reset/compaction without another model request is not guaranteed to emit a distinct public reset hook. A retained snapshot can therefore remain until its idle expiry (or `/warming stop`); stop warming before manually clearing a sensitive conversation. Restart/re-enable reloads code; workspace checkpoints cannot undo provider charges.

## Verify before relying on it

```sh
python3 -m unittest discover -s tests -v
# With a compatible Duckwork interpreter and checkout on PYTHONPATH:
python tests/duckwork_integration.py
duckwork plugins validate .
```

The suite covers scheduling, request budgets, circuit breaking, prefix/schema preservation, route filtering, payload limits, no history mutation, real HTTP transport, redirect refusal, and background scheduling. The Duckwork integration exercises the real plugin loader/config/middleware/hooks/unload across temporary profiles A → B → A. It does not modify a live user profile.

See [test evidence](docs/TESTING.md), [research and benchmark methodology](docs/RESEARCH.md), and [security policy](SECURITY.md). HTTP fixtures return explicitly synthetic usage counters to test parsing; they are not cache or performance benchmarks. No paid-provider effectiveness claim has been validated for this release.

## When to use it

Try it when a compatible provider's short cache lifetime repeatedly expires during interactive pauses, and measurements show the extra requests are worth their cost. Prefer provider-native retention controls when they solve the problem without repeated requests. Leave it disabled for infrequent sessions, tight rate limits, unsupported routes, or providers where changing tool choice prevents prefix reuse.

## License and contributions

MIT. Maintained by [mojomast](https://github.com/mojomast). Issues and focused PRs with regression tests are welcome. AI-assisted implementation; test results and limitations are documented explicitly. Catalog admission is a separate maintainer review, not a security certification. No automatic updates: catalog installs move only through a reviewed SHA-pin update.
