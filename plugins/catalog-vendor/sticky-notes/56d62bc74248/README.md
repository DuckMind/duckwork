# Duckwork Sticky Notes

Sticky / post-it notes **inside the Duckwork Desktop window**. Disk plugin, no app fork, no build step.

One **stack** on the glass. **Break out** notes when they need space. **Drag floats together** to pile them. **Stack all** when the desk gets loud.

Notes live in Duckwork Desktop, not as OS always-on-top stickies.

v0.2 is packaged for the Duckwork plugin catalog (`plugin.yaml` + `desktop/plugin.js`). Stickies are **global** by default. Session pin is an optional per-note toggle.

## Install

Requires **Duckwork Desktop**. CLI/gateway alone will not load this.

Until the catalog entry lands:

```bash
duckwork plugins install VGFreakXBL/duckwork-sticky-notes
```

Then in Desktop: **Capabilities → Plugins** → enable **Sticky Notes** (Desktop column). Catalog and git installs copy `desktop/plugin.js` into `~/.duckwork/desktop-plugins/sticky-notes/`.

After a catalog merge, the same enable step follows:

```bash
duckwork plugins install sticky-notes
```

Manual disk drop (no `duckwork plugins`):

```bash
mkdir -p ~/.duckwork/desktop-plugins/sticky-notes
curl -fsSL -o ~/.duckwork/desktop-plugins/sticky-notes/plugin.js \
  https://github.com/DuckMind/duckwork
```

Then **⌘K → Reload desktop plugins**. New installs stay off until you enable **Sticky Notes** (`defaultEnabled: false`). Existing enable/disable choices are remembered.

## How to use

| Action | How |
|--------|-----|
| New sticky | Status chip, stack **New**, palette **Sticky: New (stack)**, or `⌘⇧N` |
| Edit | Select a row in the stack; body autosaves |
| Break out | **↗** on a stack row or **Break out** in the editor |
| Pile | Drag free breakout windows until they **overlap ~40%**, then **release** |
| Flip inside a pile | Click a row in the pile list |
| Split from pile | **↗** on a pile row |
| Return one to stack | **↙ stack** on a breakout, or **↙** in a pile |
| Stack everything | **Stack all** / `⌘⇧S` / palette |
| Clear all | Palette **Sticky: Clear all** (asks to confirm) |

Notes persist in plugin-scoped storage (`ctx.storage`), profile-aware. No filesystem access.

## Design notes

- One stack card by default (not one float per note)
- Overlap-merge only after a real drag (not on plain clicks)
- Short grace after split so notes are not immediately re-piled
- Themes: app CSS variables, no hardcoded colors
- Disk plugin rules: `jsx()` / `jsxs()` only; imports limited to `@duckwork/plugin-sdk`, `react`, `react/jsx-runtime`

## Agent markers (experimental)

Create-only, explicit markers in a gateway event payload. There is no `/sticky clear` (or any other command) from events.

```text
[[sticky]]
Half-baked idea
body here
[[/sticky]]
```

```text
<!-- sticky: title | body -->
```

Do not lead with this. Demo the manual UX first.

## Customize with Duckwork

See [PROMPT.md](./PROMPT.md) for a rebuild / fork prompt.

## License

MIT — see [LICENSE](./LICENSE).

Built against the Duckwork Desktop Plugin SDK. Not affiliated with Fordex beyond using the public plugin surface.
