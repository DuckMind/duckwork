# Validation evidence — v0.1.0

Executed on Linux, Python 3.11, against Duckwork upstream commit `28aceb3451f5a5d2a27396b2adf29231be34c482`.

## Automated suite

`python3 -m unittest discover -s tests -v`

Result: 18 tests passed, exit status 0. Includes a real loopback HTTP server and background scheduler. The local server is an explicitly synthetic protocol fixture, not an inference model. Cached-token values in this test exercise accounting only.

## Duckwork integration

`PYTHONPATH=/path/to/duckwork-agent /path/to/duckwork-python tests/duckwork_integration.py`

Result, exit status 0:

```text
PASS: real Duckwork registered worker -> local HTTP POST after 30-second idle interval
PASS: real Duckwork A → B → A configuration isolation, lifecycle, unchanged request, unload cleanup
```

This imports the actual Duckwork PluginManager, loads/registers the plugin, reads temporary profile config, dispatches middleware/hooks, and unloads it. The real background worker sends a POST over a loopback socket after a real 30-second interval. No credential or production profile is used. This is not a full AIAgent-to-live-model or cache-effectiveness benchmark.

An early integration failure exposed ambient-profile configuration reads in background operation. The implementation was corrected to retain the registration ContextVars context, and the A → B → A test then passed. Tests also account for Duckwork emitting `on_session_end` on successful turn finalization.

## Catalog admission validation

Ran current upstream `duckwork_cli.plugin_validate.validate_plugin_dir` against this plugin with real Duckwork dependencies. All 13 checks passed: manifest, fields, version requirement declaration, config declaration, environment names, loadability, dependencies, isolated registration probe, declared tools/hooks/middleware, tool collisions and security scan. Security verdict: `safe`; warnings: none.

## Not established

No paid cloud model was invoked. No cache-hit, latency, cost-saving or Codex support claim is made. macOS/Windows testing is configured in GitHub Actions; consult the actual workflow run for results, rather than treating the configuration as proof. The live owner's Duckwork installation was not modified or enabled.
