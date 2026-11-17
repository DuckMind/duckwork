# Authors and provenance

This repository is the **canonical** pt-BR language pack for Hermes Agent: it is the one listed in
the curated plugin catalogue (`NousResearch/hermes-agent`, `plugin-catalog/hermes-lang-pt-br.yaml`),
and the only one that ships versioned releases.

## Timeline

| Date | Event |
|---|---|
| 2026-08-23 | StudioCodeAI opens [NousResearch/hermes-agent#92590](https://github.com/NousResearch/hermes-agent/pull/92590) — the first Desktop pt-BR proposal |
| 2026-08-30 | henrickgu opens [#98933](https://github.com/NousResearch/hermes-agent/pull/98933) for the same surface (closed unmerged on 2026-10-12) |
| 2026-09-16 | commit [`0bbc800f55e`](https://github.com/NousResearch/hermes-agent/commit/0bbc800f55e9227fcb622ce8eec2a711931d60c4) (author: StudioCodeAI) creates `apps/desktop/src/i18n/pt.ts` upstream |
| 2026-09-28 | [#126296](https://github.com/NousResearch/hermes-agent/pull/126296) moves i18n to pluggable, layered language packs |
| 2026-10-13 | the catalog is ported here, in the layout the loader and `hermes plugins validate` expect |
| 2026-10-16 | catalogs complete against `main` (`f7b4357`, pin `b0eab60`) |
| 2026-10-17 | the catalogue entry merges upstream ([#139811](https://github.com/NousResearch/hermes-agent/pull/139811)) |
| 2026-10-19 | core + TUI resynced with `main` (`3820a06`); the pt-PT → pt-BR wording pass by @4nrry merges (`dd9ec89`) |

## Who wrote what

- **Core and TUI** — mirror the `pt` locale bundled upstream (MIT, © Nous Research and its
  contributors), re-registered here as the real `pt-br` id so it wins over the `pt` / `pt-BR` alias.
- **Desktop** — original to this pack, grown out of the work in #92590 / commit `0bbc800f55e`. It is
  the largest surface (5,172 of 5,176 reference keys; the four remaining are arrays/structured values
  a text pack cannot carry).
- **@4nrry** — 85 European-Portuguese → Brazilian-Portuguese wording fixes (pack PR #3, merged as
  `dd9ec89`).
- **@henrickgu** — credited for an independent pack that reused the keys from #92590 and for a
  2,032-key wording comparison (pack PR #2). That pack is a separate, derivative project; it is not
  the catalogue entry and it is not a co-author of this one.

## Credit rules

1. A contribution merged as-is keeps its author and its commits (no anonymous squash).
2. Wording adopted from someone else's proposal gets a `Suggested-by:` trailer in the commit and a
   line in the changelog.
3. Derivative packs are welcome under the MIT license, but only this repository publishes the
   catalogue pin; version numbers and releases are ours.

## License

MIT. The Desktop catalog is © StudioCodeAI; the core and TUI catalogs are © Nous Research and the
Hermes contributors, redistributed under the same license. See [LICENSE](LICENSE).
