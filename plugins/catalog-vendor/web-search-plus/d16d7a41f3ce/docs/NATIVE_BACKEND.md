# Native Duckwork backend

The `wsp` backend lets Duckwork' `web_search` and `web_extract` tools call the existing WSP engine in-process. It addresses the integration requested in [#125](https://github.com/DuckMind/duckwork) without the separate CLI wrapper proposed there.

This is an opt-in interface, not a change in search quality or provider policy. Installing WSP does not select it. `web_search_plus` and `web_extract_plus` retain their current schemas and defaults.

## Select the backend

Use a Duckwork version that supports `PluginContext.register_web_search_provider` and the `WebSearchProvider` API. Load and enable the existing `web-search-plus` plugin through Duckwork. If your Duckwork version asks for a provider capability grant, review and grant it through Duckwork; this plugin does not bypass that decision.

In the active profile's Duckwork `config.yaml`, explicitly select either capability:

```yaml
web:
  search_backend: wsp
  extract_backend: wsp
```

The same from the command line (the syntax is `duckwork config set <dotted.key> <value>`; run `/reload` afterwards):

```bash
duckwork config set web.search_backend wsp
duckwork config set web.extract_backend wsp   # only with an extraction key
```

Select `wsp` for extraction only if one of your keys can extract pages (Brave, for example, only searches); otherwise every `web_extract` fails in WSP and the keyless rescue below sends the URL to anonymous services. Do not leave `web.extract_backend` unset when search is on `wsp`: Duckwork then picks `wsp` for extraction too and refuses with "search-only backend". With search-only keys keep Duckwork' extraction, for example `duckwork config set web.extract_backend exa` (keyless tier). `status` warns about both setups.

This is the recommended setup once you have a search key: otherwise Duckwork' own `web_search` keeps using Duckwork' own backends, and Duckwork' Tool Search may hide the Plus tools. `duckwork web-search-plus status` and `setup` print this hint while a search provider is configured and the backend is not selected. Remember the [keyless rescue](#keyless-rescue-duckwork-behavior-on-by-default) below when you select it.

For mixed routing, keep your extraction provider:

```yaml
web:
  search_backend: wsp
  extract_backend: firecrawl
```

The shared `web.backend: wsp` setting is also supported. Per-capability settings take precedence. WSP's own routing configuration still controls which underlying provider its `auto` route uses. Explicit-only providers, including DonSeTch, are not automatically opted into the routing pool.

Native tools require the Duckwork `web` toolset enabled. If you previously configured Plus-only Fastpath, remove **only** `web` from `agent.disabled_toolsets`, retaining any other disabled toolsets. Inspect the configuration without changing it:

```bash
python ~/.duckwork/plugins/web-search-plus/setup.py fastpath --json
```

For another profile, use that profile's plugin path and `DUCKWORK_HOME`, or pass `--config-path` explicitly. The doctor inspects configuration; it does not prove a loaded backend or working credentials. Apply runtime changes in a fresh Duckwork process when no work is active.

## Behavior and limits

- No CLI fallback: an unavailable in-process engine produces an error. Since 5.0 the Plus tools have no subprocess fallback either; `WSP_FORCE_SUBPROCESS` is ignored.
- Native search uses WSP's 20-result cap. Duckwork may bucket a smaller request before dispatch; the adapter reports the effective cap and Duckwork slices the final rows.
- Native tool schemas do not expose the full Plus feature set. Use Plus tools for per-call provider choice, research mode, locale/domain filters, spans, or detailed quality reports.
- Extraction preserves requested URL association and reports missing or failed items individually. The native Duckwork wrapper also applies its own content-size limits.
- The bridge uses WSP's existing request timeout. A timeout ends the caller's wait; Python cannot forcibly stop an already-running provider thread. It is not a guarantee that upstream network work was cancelled.
- Duckwork' outer search cache keys on the backend name `wsp`, query and count, not WSP's inner provider settings. After changing inner routing or credentials, use a fresh Duckwork process rather than expecting an identical cached query to prove the new settings. Do not share one native runtime across different profiles or credential contexts.

## Keyless rescue (Duckwork behavior, on by default)

Selecting `wsp` is opt-in on the WSP side, but Duckwork adds its own safety net on top. With `web.keyless_rescue` at its default (`true`, and `web.keyless_fallback` also on), a **failed** native `wsp` `web_search` or `web_extract` call is retried once, for that call only, on Duckwork' anonymous keyless ring (Exa, Parallel, Firecrawl, Keenable free tiers). The result then carries `rescued_from` / `backend_error`, and the next call uses `wsp` again.

Privacy implication: when a WSP call fails (provider outage, bad key, timeout), the **query text or the URLs** of that call are sent to those third-party free-tier services, even if none of them is in your WSP routing. The retry is made by Duckwork, not by WSP, and WSP cannot see or veto it for search calls. Nothing is sent when WSP succeeds.

What WSP does about it: URLs that WSP refuses on purpose (private/internal addresses, blocked names such as `localhost`, hostnames that do not resolve) come back with Duckwork' `blocked_by_policy` marker, which Duckwork never forwards to the ring. Ordinary provider failures are not marked, so they remain eligible for rescue. Search has no equivalent marker in Duckwork, so a failed search query can be rescued.

To turn the rescue off in the active profile:

```bash
duckwork config set web.keyless_rescue false
```

(or set `web: {keyless_rescue: false}` in `config.yaml`; `web.keyless_fallback: false` also disables it). Apply it in a fresh Duckwork process. `duckwork web-search-plus status` and `python ~/.duckwork/plugins/web-search-plus/setup.py fastpath` show whether the native backend is selected and whether the rescue is on; both only read `config.yaml` and never change it.

## Rollback

Restore your previous `web.search_backend` and `web.extract_backend` settings (and `web.backend`, if set), then apply them in a fresh process. For Plus-only mode, disable the `web` toolset as before. Disabling or unloading WSP removes its native provider registration through Duckwork' registration handle; it does not rewrite backend pins in your configuration.

No separate `web/wsp` wrapper plugin is required. Remove or disable a previously installed wrapper before selecting this backend so two plugins do not compete for the `wsp` name.
