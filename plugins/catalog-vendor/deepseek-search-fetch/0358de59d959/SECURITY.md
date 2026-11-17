# Security policy

## Reporting a vulnerability

Use GitHub's private reporting: **[Report a vulnerability](https://github.com/DuckMind/duckwork)**.
Please do not open a public issue for a security problem.

Include what you need to make it reproducible: affected version, Duckwork version, the
configuration involved, and the smallest steps that show the problem. **Never send your
API key** — if a secret appears in a log line you want to share, replace it with `***`.

Expect an acknowledgement within a few days; this is a single-maintainer, community project.

## Supported versions

Fixes land on the latest 1.0.x release. The plugin manifest declares
`requires_duckwork: ">=0.22.0"`; older Duckwork hosts refuse to load it rather than silently
losing the plugin's settings. The plugin is tested against Duckwork v0.22.2 (the release
current at the time of writing) and the public provider ABC on `main`.

## Scope

In scope for this repository:

- The API key's handling — it must be read only through Duckwork' provider env helper,
  never logged, and never sent anywhere except `api.deepseek.com`. A profile-scoped
  refusal must become an unavailable/error result, never another profile's key.
- The base-URL override guard: `DEEPSEEK_BASE_URL` may only name the exact origin
  `https://api.deepseek.com` over https or a loopback test host. Any way to redirect the
  bearer key through configuration is a vulnerability. The refusal warning must not
  repeat a raw value that can carry userinfo.
- Anything that turns a hostile *response* (from the API, or from a page it fetches) into
  code execution, file access, or a crash that outlives the call. Response text is repaired
  for UTF-8/JSON serialization and a malformed result row is skipped rather than fatal.
- Malformed input handling — an unpaired surrogate, a 100 kB query, a `None`/string/scalar
  URL: the plugin returns a search error envelope or a per-entry `error` in the extract
  list, never raises or hangs. A trickling body is aborted by a wall-clock deadline.

Out of scope here (report upstream instead):

- Bugs in Duckwork Agent itself — the dispatcher, provider resolution, the keyless rescue
  path, or `duckwork plugins validate`: [Fordex/duckwork-agent](https://github.com/DuckMind/duckwork).
- DeepSeek's own API, billing, account security, or the accuracy of its search results.
- The general risk that any Duckwork plugin runs with the agent's environment. That is a
  host design property, not something this plugin can fix; it is why this plugin ships
  no file, subprocess or network surface beyond the two endpoints.

## Design notes relevant to attackers

- Runtime imports are the standard library, the `httpx` Duckwork already ships, and the public
  `duckwork_cli.config` module read (guarded) for `web.extract_timeout`.
- No `eval`, `exec`, dynamic imports, subprocesses, or file I/O in the plugin's own code.
  Key resolution goes through Duckwork' config/.env layer.
- Requests go to `api.deepseek.com` only — two endpoints, bearer auth, TLS — and error bodies are truncated to 300 characters before they reach a log.
- The plugin cannot update itself: Duckwork' catalog pins a full commit SHA precisely so
  that installed code cannot move to an unreviewed revision.
