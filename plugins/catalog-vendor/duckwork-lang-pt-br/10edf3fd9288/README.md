# duckwork-lang-pt-br

Brazilian Portuguese (**Português do Brasil**) language pack for Duckwork Agent — the core
CLI/gateway, the Ink TUI and the Desktop app, in `pt-br`.

Text-only plugin: no Python, no `desktop/plugin.js`, no network, no permissions. Just catalogs.

## Install

```bash
duckwork plugins install StudioCodeAI/duckwork-lang-pt-br
duckwork plugins enable duckwork-lang-pt-br
```

Then pick the language in Desktop settings, or set it in config:

```bash
duckwork config set display.language pt-br
```

Restart the Desktop app (or start a new session) so the catalogs are picked up.

## What's covered

| Surface | File | Keys | Coverage |
|---|---|---|---|
| Core (CLI, gateway, approvals, tips) | `locales/pt-br.yaml` | 3,477 | **100%** of the English core catalog |
| TUI (`duckwork --tui`) | `locales/pt-br.tui.yaml` | 1,356 | **100%** of the English TUI catalog |
| Desktop (app) | `locales/pt-br.desktop.yaml` | 5,172 | **100%** of the translatable desktop catalog (4 non-text keys upstream) |

The core and TUI catalogs mirror the `pt` locale already bundled upstream; `pt-br` is registered as a
real variant so it always wins over the `pt`/`pt-BR` alias. The Desktop catalog is the original
contribution — before this pack the Desktop app had no Portuguese at all.

The catalogs track `Fordex/duckwork-agent@main`, so they are complete for the current English
source: every translatable key exists and every value is translated (array- and function-valued
entries stay in TypeScript; a text pack cannot carry them). On a *release* older than the latest `main`,
`duckwork plugins validate` lists the keys upstream added since that release as "not in the English
catalog (ignored at runtime)" — those are warnings, never errors, and the strings are simply not
reached until the release that introduces them. Building against an older release instead would carry
keys upstream has since deleted, which is worse.


## Where the translations come from

Ported from the renderer-only `pt` catalog in
[StudioCodeAI/duckwork-agent `feature/i18n-pt-br`](https://github.com/DuckMind/duckwork)
(PR [Fordex/duckwork-agent#92590](https://github.com/DuckMind/duckwork)).

`apps/desktop/src/i18n/pt_*.ts` was bundled with esbuild, composed exactly like `pt.ts` does, flattened
to dotted keys, and intersected with the English key export of `upstream/main`
(`locales/_keys.desktop.json`). Keys upstream has since removed are dropped, so the pack never carries
dead strings; the 38 dropped keys are listed when the build script runs.

## Credits and timeline

The **Desktop** catalog is this pack's original contribution, and it started with StudioCodeAI:

| Date | What |
|---|---|
| 2026-08-23 | StudioCodeAI opens [PR #92590](https://github.com/DuckMind/duckwork) — the first Desktop pt-BR proposal |
| 2026-09-16 | commit `0bbc800f55e` **creates** `apps/desktop/src/i18n/pt.ts`; before it the Desktop app had no Portuguese at all |
| 2026-09-28 | [#126296](https://github.com/DuckMind/duckwork) moves i18n to pluggable, layered language packs — an in-tree TS catalog stops being the supported shape |
| 2026-10-13 | the catalog is ported here, in the layout the loader and `duckwork plugins validate` expect |

The core and TUI catalogs mirror the `pt` locale Duckwork already bundles upstream (added by other
contributors); they are re-registered here under the real `pt-br` id so it wins over the `pt` / `pt-BR`
alias.

Credit where it is due: [henrickgu/duckwork-lang-pt-br](https://github.com/DuckMind/duckwork)
independently reused the keys from PR #92590 — "every valid key from this PR plus 1,501 new
translations". His upstream proposal for the same surface
([#98933](https://github.com/DuckMind/duckwork)) was opened after #92590 and closed
unmerged; **this** repository is the catalogue entry and the only one that ships versioned releases.
The full provenance record — including who wrote each surface — is in [AUTHORS.md](AUTHORS.md).

> **Note:** both repos register the `pt-br` id, and when two packs cover the same key the last one
> loaded wins. Install **one** of them, not both.

## Staying in sync

Duckwork moves fast. `.github/workflows/drift.yml` runs weekly (and on demand) and reports how far the
pack is from `main` and from the latest release, opening a single issue when `main` has keys we do not
translate yet or no longer has keys we carry.

```bash
python tools/drift.py            # the same report, locally
python tools/drift.py --drift    # non-zero exit when something drifted
```

The routine when it fires:

1. `node tools/build-desktop-pack.mjs` — refresh `pt-br.desktop.yaml` against the current English export.
2. Translate the newly missing keys (the report lists them).
3. `python tools/verify_pack.py --ref main` and `duckwork plugins validate .` — both must pass.
4. Commit, then open a **SHA-bump PR** for `plugin-catalog/duckwork-lang-pt-br.yaml` in
   `Fordex/duckwork-agent` (catalogue rule 4: a SHA bump is a new PR).

Nothing updates an installed copy on its own — by design, a listed plugin may not self-update
(catalogue rule 3), so users pick the new pin up with `duckwork plugins update duckwork-lang-pt-br`.

## Requirements

Duckwork ≥ 0.21 — language packs as plugins (`provides_locales`) landed there. Nothing else.

## Validating

```bash
duckwork plugins validate .
```

Checks the manifest, the `provides_locales` declaration against the shipped files, text-only leaves,
and every key against the English reference catalogs.

`tools/verify_pack.py` is the standalone twin, and CI runs it on every push and pull request
(`.github/workflows/verify.yml`). It needs no Duckwork install and no clone — it fetches the reference
files from `Fordex/duckwork-agent` over HTTPS and checks, per surface:

1. every catalog parses and every leaf is text;
2. every key exists in the English reference for that surface;
3. core values keep the English `{placeholder}` set exactly;
4. braces are balanced in every value;
5. no duplicate keys.

```bash
python tools/verify_pack.py                        # against duckwork-agent@main
python tools/verify_pack.py --ref v0.21.6          # against a release tag
python tools/verify_pack.py --json                 # machine-readable report
python tools/verify_pack.py --min-desktop-coverage 0.80
```

Current result against `main`: **PASS**, 0 warnings, 0 errors.

```
- core     locales/pt-br.yaml:         3477 key(s), 100.0% of the English catalog, 0 unknown, 0 placeholder mismatch(es)
- tui      locales/pt-br.tui.yaml:     1356 key(s), 100.0% of the English catalog, 0 unknown, 0 placeholder mismatch(es)
- desktop  locales/pt-br.desktop.yaml: 5172 key(s),  99.9% of the English catalog, 0 unknown, 0 placeholder mismatch(es)
```

Verified against `upstream/main`: **0 placeholder/key divergences** on all three surfaces
(core 3,477/3,477 · TUI 1,356/1,356 · Desktop 5,172/5,176 present in the English key export; the four
remaining desktop keys are arrays/structured values a text pack cannot carry).

The two `caution` hits from the install scanner are false positives on translated prose: a
`… install.sh | sh` URL inside a translated error message, and an "update AGENTS.md" string.

## Placeholders

Entries whose English value is a *function* are written here as strings with positional `{0}`, `{1}`, …
placeholders in argument order. Core (Python) strings keep their **named** placeholders exactly as
English does. Both are substituted at runtime and never reach the screen.

## License

MIT. The core and TUI catalogs mirror Duckwork Agent's bundled `pt` locale (MIT, © Fordex);
the Desktop catalog is © StudioCodeAI.
