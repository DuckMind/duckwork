# Completion Sound

A [Duckwork Desktop](https://github.com/DuckMind/duckwork) plugin that picks the sound played when a turn finishes:

- one of Duckwork' 14 built-in presets (Two-note comfort, Glass ping, Soft marimba, …), or
- your own audio file (mp3, wav, ogg, …), and
- optionally a different sound during night hours (the window may cross midnight).

Settings live under **Settings ▸ Plugins ▸ Completion Sound**, with a preview button next to each choice. The UI is in English and Korean and follows the app language.

## Install

In Duckwork Desktop, open **Capabilities ▸ Plugins ▸ Install from Git**, keep the Desktop target checked, and use this repository's URL:

```
https://github.com/DuckMind/duckwork
```

Then click **Rescan** (or restart) if it does not appear right away.

## Duckwork' own completion sound still plays

Duckwork has no setting to turn its built-in completion sound off yet, and the plugin SDK gives plugins no way to switch it off, so you will hear both sounds. This plugin does not patch the app to get around that. Open work in duckwork-agent that would fix it:

- [PR #140350](https://github.com/DuckMind/duckwork) adds a "None" option to the built-in sound picker. Once it ships, choose "None" there and this plugin's sound is the only one.
- [PR #78203](https://github.com/DuckMind/duckwork) adds a custom audio file and a volume control to the built-in picker. If it ships, the only thing this plugin adds is the night sound.

## Details

- **Trigger:** the gateway event `message.complete`, the same event Duckwork' built-in sound uses. Replayed events (after a reconnect) are ignored, and several chats finishing within 1.5 s play one sound.
- **Your files** are stored in the plugin's own storage as data URLs: up to 3 files, 1 MB each. They never leave your machine.
- **Volume** applies to your files. Presets play at Duckwork' own level.
- **Several windows:** Duckwork plays its built-in sound in one window only; a plugin cannot use that coordination, so with several windows open each may play.
- **Surfaces used:** `ctx.onEvent`, `ctx.storage`, `ctx.i18n`, `ctx.registerSettingsPage` only. No agent tools, hooks, middleware or environment variables.

## Build

`desktop/plugin.js` is committed, so installing needs no build. To rebuild after editing `src/`:

```
npm install
npm run build
```

The presets come from Duckwork' own synth code, vendored unchanged in `src/vendor/` (see `NOTICE`); `build.mjs` maps its app imports to small shims.

## License

MIT. Includes code from hermes-agent, Copyright (c) 2025 Nous Research, under the MIT license (`NOTICE`).
