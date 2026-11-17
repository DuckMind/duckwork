# All Pets — a Duckwork desktop plugin

Browse **every** pet installed for your Duckwork profile in its own workspace pane, with
thumbnails, a search box, a live count, and click-to-adopt.

## Why

The built-in picker (Settings ▸ Appearance ▸ Pet) renders at most **60 rows**
(`RENDER_CAP` in `apps/desktop/src/app/settings/pet-settings.tsx`) and the command-palette
page slices to 50. A store with a couple of hundred pets is browse-only by typing a search
term. This plugin reads the same local store with no cap.

## Large libraries

The pane renders **240 pets at a time** and offers *Load more* for the rest. Some community
packs run past a thousand entries; painting every tile at once stalls the renderer, so the
page size is fixed and a new search resets it.

## Requirements

- Duckwork desktop `>=0.19`. `host.openWorkspace` is used for the pane; on a desktop without it
  the plugin falls back to a `/pets` page so the feature still exists.
- No API keys, no environment variables, no network access beyond your own local gateway.

## Install

**From the catalog** — `duckwork plugins install duckwork-pets-all`, or Capabilities ▸ Plugins in
the app. Catalog installs check out the exact commit the listing pins.

**From Git** — `Cmd/Ctrl+K` ▸ **Capabilities** ▸ **Plugins** ▸ *Install from Git*, then paste
this repository's URL. The app detects `desktop/plugin.js` and installs it into
`~/.duckwork/desktop-plugins/<repo-name>/`.

**By file** — copy `desktop/plugin.js` to `~/.duckwork/desktop-plugins/pets-all/plugin.js`.
Runtime plugins are discovered within a few seconds and hot-reload on save.

## Open the pane

Three doors, all equivalent:

1. Click the **🐾 pets** chip in the app's status bar.
2. Press `Ctrl+Alt+P` (`mod+alt+p`).
3. `Cmd/Ctrl+K` and run **Pets: Open the pet gallery pane**.

The pane docks to the right of the workspace and keeps its own tab; re-running any door
fronts the existing pane instead of opening a second one.

## How it works

| Step | Call | Notes |
|---|---|---|
| List | `pet.gallery` with `localOnly: true` | Installed pets only; skips the network manifest |
| Thumbnails | `pet.thumb` per slug | Batched 6 at a time; idle frame, cached on disk by the backend |
| Adopt | `pet.select` on tile click | Same call the built-in picker makes |

Everything is read-only until you click a tile. Nothing is uploaded, and the plugin never
touches your config except through `pet.select`.

The agent half adds one read-only tool, `list_pets`, which reports what pets exist and which
one is active.

## Catalog listing

This plugin is listed in the Fordex plugin catalog. Listed installs check out exactly the commit
the entry pins, and updates reach users only through a reviewed re-pin PR — after which
`duckwork plugins update duckwork-pets-all` moves an installed copy forward. The pin is the trust
model, so there is no in-app self-updater.

## Compatibility notes

- A contributed full-page route lands inside the workspace zone, so on a layout parked on a
  session tile the navigation can look dead (the tile stays in front). That is why this plugin
  opens a **pane** instead.
- Runtime desktop plugins live outside the Tailwind content scan, so this plugin styles with
  inline styles and the app's CSS variables rather than utility classes.

## License

MIT. See `LICENSE`.
