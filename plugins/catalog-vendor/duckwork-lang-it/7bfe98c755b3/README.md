# duckwork-lang-it — Italian language pack (Desktop)

Full Italian translation of the **Duckwork Desktop** UI catalog, packaged as a
manifest-only Duckwork language pack.

## What it ships

- `locales/it.yaml` — 3437 keys, the core (Python-side) catalog.
- `locales/it.tui.yaml` — 1259 keys, the `duckwork --tui` catalog.
- `locales/it.desktop.yaml` — 5030 keys, the desktop catalog
  (`apps/desktop/src/i18n/en.ts` as of the pinned build).

The core and TUI catalogs mirror the in-tree `it.yaml` / `it.tui.yaml` so
the pack stands alone; the desktop catalog is the new piece — it does not
exist in-tree yet. When Duckwork ships a desktop `it.desktop.yaml`, the pack
still wins (packs are loaded before the bundled layer) — that is intended,
the community translation stays in the pack until the core one is reviewed.

## Install

```sh
duckwork plugins install <this-repo-url>
```

or clone into your Duckwork home plugin dir:

```sh
git clone <this-repo-url> ~/.duckwork/plugins/duckwork-lang-it
```

Then choose the language (the pack never switches it for you):

```sh
duckwork config set display.language it
```

or pick **Italiano** in the Desktop / TUI language switcher. Restart running
gateways/TUI/desktop sessions so they pick the pack up.

## Verification

Built and checked against the English desktop catalog:

- 100% key coverage (no missing or extra keys);
- placeholders (`{name}`, `{{x}}`), URLs and CLI flags preserved verbatim;
- hard-parsed UI tokens (menu brackets, `[Y/n]` prompts) kept verbatim;
- parsed round-trip with Duckwork' own `i18n_layers.parse_locale_file()` →
  4378 dotted keys, 0 missing / 0 extra / 0 divergent.

## Disclosure

- **Manifest-only**: `provides_locales` is the entire manifest. No Python,
  no code execution, no network access, no environment variables.
- Registering the pack **never changes** `display.language`; opting in is
  always the user's choice via config or the language switcher.
- The catalog contains static UI strings only — agent responses, tool output
  and logs are not affected (as with any Duckwork language pack).

## License

MIT — see [LICENSE](LICENSE).
