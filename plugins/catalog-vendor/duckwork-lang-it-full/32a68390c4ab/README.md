# duckwork-lang-it-full — Italian Desktop language pack

Italian UI translation for the **Duckwork Agent desktop app**, generated from the
hand-reviewed typed catalog maintained in
[gradia64/duckwork-agent](https://github.com/DuckMind/duckwork)
(branch `gradia-desktop-it`).

- `locales/it.desktop.yaml` — 5,082 of 5,085 desktop keys (the 3 the pack format
  cannot carry — two composer placeholder rotations and `intro.custom` — fall
  back to English). Includes the newest sections (`firstRun`, `themePicker`,
  plugin `installModal` rework).
- Core (CLI/gateway) and TUI Italian are **already bundled with Duckwork** and are
  intentionally not shipped here; this pack only fills the Desktop gap.
- Functions (plurals, ETAs, conditional tips) ship as positional `{0}` templates
  — a pack-format constraint; the fork's bundled locale renders them natively.

## Regenerating

The YAML is an artifact — never edit it by hand. From a checkout of the fork:

```sh
DUCKWORK_SRC=/path/to/duckwork-agent node scripts/generate-desktop-pack.mjs
```

Then validate against the same rules as `duckwork plugins validate`
(text-only leaves; keys ⊆ `locales/_keys.desktop.json`):

```sh
python3 scripts/validate.py
```

## Why `-full` and not `duckwork-lang-it`

The catalog id `duckwork-lang-it` is taken by
[Lazzdaycod/duckwork-lang-it](https://github.com/DuckMind/duckwork), an
independent community translation. This pack is generated from the typed
catalog of [gradia64/duckwork-agent](https://github.com/DuckMind/duckwork)
(`gradia-desktop-it` branch) and tracks upstream main closely — it carried
`firstRun`, `themePicker`, connector accounts and the update-channel picker
from day one. Both packs can be installed; the last registered one wins for
overlapping keys.

License: MIT.
