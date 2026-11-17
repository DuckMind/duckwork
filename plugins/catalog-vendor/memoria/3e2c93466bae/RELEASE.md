<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Release preparation

Current status: 0.1.1 PR preview for review. No GitHub release, PyPI/npm package or
Duckwork catalog entry has been published by this change.

Cloud API acceptance completed on October 8, 2026: all 13 checks passed, with zero
active test memories remaining. See [CLOUD_ACCEPTANCE.md](CLOUD_ACCEPTANCE.md).
Full natural-language agent conversation acceptance remains separate from these
direct lifecycle/tool-hook checks.

Deploy the matching API with `/v1/observe/deduplicated` before distributing 0.1.1.
Repeat live acceptance for a turn that explicitly saves one fact and contains a
second unsaved fact: the explicit record should remain active at T1, the second
fact should be captured, and no translated/paraphrased copy of the first should
appear. The October 8 Cloud report covers 0.1.0, not this new route.
Also verify same-turn store→correct and store→forget, recovery after a pre-write
extraction failure, and a missing branch without an erroneous upgrade diagnosis.
Exercise large and quote-heavy store/update inputs under the host's per-result
and aggregate tool budgets; compact receipts must still supply exclusion IDs,
including when aggregate pressure persists the receipt itself. If extraction
emits a paraphrase despite the prompt, it may insert a duplicate, but must keep
the excluded T1 active.
The API/proxy must preserve `X-Memoria-Observe-Deduplicated` and
`X-Memoria-Observe-Error`; without these markers the plugin conservatively treats
503 as uncertain and unmarked 404 as an unavailable endpoint.

1. Keep the Cloud acceptance current and validate on the final
   supported Duckwork build. Test installing/updating/removing the directory in a
   disposable Duckwork profile. Keep the user's actual profile unchanged during testing.
2. Review and commit `plugins/duckwork` and its CI workflow. Publish that reviewed
   commit to `matrixorigin/Memoria`; obtain its **full 40-character SHA**. A SHA
   before this directory exists is not a release pin.
3. Verify `duckwork plugins install 'https://github.com/DuckMind/duckwork'
   --ref <SHA>` from a clean profile. Version 0.1.1 uses the directory distribution;
   a PyPI or npm package is not required.
4. Submit a PR to `Fordex/duckwork-agent` adding `plugin-catalog/memoria.yaml`.
   Replace `<RELEASE_SHA>` below with that actual commit. Confirm the current catalog
   rules and maintainer identity before submitting.
5. After maintainer acceptance, test `duckwork plugins install memoria` and
   `duckwork memory setup`, then expose Duckwork onboarding on the Memoria website.
   Subsequent releases require a new reviewed SHA/catalog update.

Catalog draft (intentionally not an installable pin):

```yaml
name: memoria
repo: https://github.com/matrixorigin/Memoria
sha: <RELEASE_SHA>
subdir: plugins/duckwork
version: "0.1.1"
description: Memoria Cloud memory provider with scoped recall, explicit memory tools and opt-in durable background capture. Supports self-hosted API origins.
maintainer: matrixorigin
tier: community
category: memory
requires_duckwork: ">=0.21.5"
docs_url: https://github.com/matrixorigin/Memoria/tree/<RELEASE_SHA>/plugins/duckwork
capabilities:
  provides_tools: []
  provides_hooks: []
  provides_middleware: []
  requires_env: []
```

Provider-owned tools are registered through the memory manager, rather than the
general plugin tool registry. The API Key is prompted by the memory setup schema,
so it is not an admission-time `requires_env` gate.

References: [memory providers](https://duckwork-agent.fordex.com/docs/developer-guide/memory-provider-plugin),
[catalog submission](https://duckwork-agent.fordex.com/docs/developer-guide/plugins/catalog-submission).
