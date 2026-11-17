# Web Search Plus 4.1.0

## Native Duckwork tools, backed by WSP

Duckwork users can now route `web_search` and `web_extract` through WSP's existing in-process engine. The `wsp` backend is opt-in; installing the plugin does not change routing. Existing Plus tools remain available.

```yaml
web:
  search_backend: wsp
  extract_backend: wsp
```

Search and extraction can use different backends, for example `search_backend: wsp` with `extract_backend: firecrawl`. Keep the Duckwork web toolset enabled for this mode. Remove or disable any separate wrapper registering the same `wsp` name, and use Duckwork' plugin capability-grant flow when prompted.

Thanks to [LugMuad](https://github.com/LugMuad) for proposing and testing this integration in [#125](https://github.com/DuckMind/duckwork), including the report that native search can also appear through Duckwork' browser toolset. This release handles that native search path through WSP when selected; it does not change Duckwork' toolset membership rules.

Native calls do not fall back to the WSP CLI when the in-process engine cannot load. Use Plus tools for per-call provider selection, research mode and other controls absent from Duckwork' native schemas. Read the [configuration, cache and timeout limits](NATIVE_BACKEND.md).

## DonSeTch 3.6.1

The adapter now reads compact MCP evidence and namespaced fetch diagnostics while retaining older structured responses. Search titles and snippets stay bound to their ranked source URLs. The stdio transport setting applies only to the DonSeTch child process.

[DonSeTch](https://github.com/dondai44423/donsetch), maintained by [dondai44423](https://github.com/dondai44423), is a separately installed AGPL-3.0-only program, not bundled WSP code. It remains explicit-only unless the operator opts it into WSP routing. A local installation still performs outbound web requests and consumes local resources.

Historical Hound integration and source-enrichment work credit [Hound / Master-Fetch](https://github.com/dondai1234/master-fetch), Bishesh Bhandari's independent MIT-licensed project. The removed Hound provider is not restored by this release.

## Verification and scope

The candidate passed 1,082 tests plus six subtests, isolated real Duckwork plugin discovery and unload, native/Plus coexistence, and real native DonSeTch search and two-URL extraction. Lint, generated schemas and schema-boundary checks passed.

The native backend is specific to the Duckwork plugin. The matching MCP 4.1.0 release carries the DonSeTch adapter update, not Duckwork plugin registration. Neither release automatically changes a running host's configuration.
