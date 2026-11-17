# duckwork-boot-screen

A boot animation plugin for the Duckwork desktop client: a six-act cinematic startup sequence that unveils from a black title card all the way to the app UI.

Adapted from [dsh-startup-screen](https://github.com/6shenhonghong9/dsh-startup-screen) (the DeepSeek Harness client boot animation by Honghong Shen, MIT). The logo was replaced with the official Duckwork icon, all copy was rebranded for Duckwork, and it runs as a Duckwork Desktop on-disk plugin.

## Six-Act Structure

| Act | Content |
|---|---|
| 1 | Black screen + icon stroke drawing itself in (one stroke, then ink drop) / DUCKWORK · DUCKWORK · DUCKWORK DESKTOP |
| 2 | Overexposed wash-out to a warm-white technical-dossier backdrop (corner ticks, grid, timestamp, segmented progress bar) |
| 3 | Brand lockup lands: DUCKWORK / AGENTIC INTELLIGENCE / DESKTOP APP, footer POWERED BY FORDEX |
| 4 | Interactive access-grant in five steps: grant access → confirm identity → open session channel → read permissions → verification passed (recorded voice lines with word-by-word subtitles) |
| 5 | Scatter/crosshair animation for the permission read |
| 6 | WELCOME TO / [DUCKWORK DESKTOP] final curtain, unveiled after a cyan-red chromatic glitch, scroll lock released and control handed to the app |

Sound effects (prompts, confirmations, step ticks) and English narration run throughout. If the recorded assets are missing it falls back to browser TTS automatically, and if TTS is unavailable the animation still plays (it never blocks).

## Requirements

- Duckwork Desktop v0.21.x or a compatible desktop client (relies on the on-disk plugin mechanism and the `appearance.extra` / `palette` contribution areas)
- No Node, no network: the runtime is a single self-contained file

## Installation

### Step 1: Get plugin.js

Download `plugin.js` from [Releases](../../releases), or just copy `plugin.js` from the repository (the repo root is the final artifact — one file, about 457 KB, with all assets embedded).

### Step 2: Drop it into the plugin directory

In the Duckwork desktop client, open the **Skills & Tools → Plugins** tab and click the **folder icon** in the title bar ("Open plugin directory") — this opens the plugin root that belongs to your machine. The path varies by platform and configuration, so trust whatever this button opens.

In the directory it opens, create a subfolder and put the file inside:

```
<plugin root>/
└── duckwork-boot-screen/
    └── plugin.js
```

Default plugin root locations (when `DUCKWORK_HOME` is not set):

| Platform | Default path |
|---|---|
| Windows | `%LOCALAPPDATA%\duckwork\desktop-plugins` |
| macOS / Linux | `~/.duckwork/desktop-plugins` |

> If the `DUCKWORK_HOME` environment variable is set (or `DuckworkHome` exists in the Windows registry), the plugin root is `<DUCKWORK_HOME>/desktop-plugins` — again, trust the path opened by the folder button on the plugins page.

### Step 3: Load it

Go back to the **Skills & Tools → Plugins** page and click the **refresh button** in the title bar (rescan). Or just restart Duckwork.

**Two signs that it loaded**:

1. A toast appears in the bottom-right: `🚀 Boot animation plugin loaded · Settings entry: "Boot Animation" in the sidebar`
2. A **Boot Animation** entry shows up in the plugin list (green toggle, on by default)

> Note: modifying an existing `plugin.js` does **not** trigger an automatic reload (the file watcher is only established after the first load). Click refresh on the plugins page after editing the file.

## Usage

### When it plays

Default `session` mode: **once per app session** (it will not interrupt again during the same Duckwork run). The other modes are selectable on the settings page:

- `always` — plays on every registration (including hot reloads)
- `session` — once per app session (default)
- `daily` — once on the first launch of each day

Enable/disable: the **Boot Animation** toggle on the plugins page. Takes effect after the app restarts.

### Skipping

Press **Esc** or click **SKIP** in the top-right during the animation to jump straight to the reveal. Advance the access-grant steps with **Enter / Space** or by clicking the buttons.

### Preview it now (without waiting for the next launch)

Two entry points:

- **"Boot Animation" in the sidebar** (play icon, a standalone page in the same style as "Kanban") → "Play Now" inside the page. This is the main configuration entry: all 33 settings live on this one page.
- **Command palette**: click the chat input box once to focus it, then press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>K</kbd> — "Boot Animation: Play Now" starts it directly, "Boot Animation: Open Settings" goes to the page above.

### Settings (on the "Boot Animation" sidebar page)

- **Playback**: enable toggle, play trigger, playback speed (0.35–3×), whether interaction is mandatory, whether skipping is allowed
- **Visual**: theme (warm white / dark), accent colour, chromatic-aberration duo, noise/scanline decoration toggles
- **Sound**: master SFX volume, SFX source (embedded assets / synthesised tones), narration toggle, speech rate, volume, start delay
- **Copy**: identity name (the `ID CONFIRMED : XXX` shown on the access panel, defaults to `OPERATOR`, change it to your own name or callsign), the three brand lines, the footer, and 14 text fields in total

Changes are written to plugin storage immediately and take effect on the next playback; "Restore defaults" puts everything back in one click.

## Directory Layout (developers)

```
duckwork-boot-screen/
├── plugin.js            # Final artifact (single file, this is what you install)
├── build.py             # Build script: src + assets + glyph → plugin.js / preview
├── src/
│   ├── shell.js         # Plugin shell: register, contribution areas, playback lifecycle, settings UI
│   ├── splash.js        # Six-act runtime (from the original project, rebranded for Duckwork)
│   ├── splash.css       # All animation styles (selectors renamed on inject)
│   ├── glyph.txt        # Duckwork icon path data
│   └── assets/*.mp3     # Voice-line and SFX assets
├── preview/index.html   # Offline preview page (mock UI + replay/skip buttons)
└── test/smoke.mjs       # Smoke test: config bounds / playback gating / register structure
```

Rebuild and verify:

```bash
python build.py        # each string surgery is asserted; a syntax error writes no artifact
node test/smoke.mjs    # requires Node 18+
```

Preview: just open `preview/index.html` in a browser (it is generated at build time) and you get the full six acts.

## Privacy

- Single self-contained file that **makes no network requests**: audio, icon and styles are all embedded as data URIs
- Voice narration uses the browser's local `speechSynthesis`; the recorded assets are decoded and played locally; nothing is uploaded
- Settings are stored in the Duckwork desktop client's local storage, never written to the repo or the cloud

## Credits

- [dsh-startup-screen](https://github.com/6shenhonghong9/dsh-startup-screen) — the creative concept and implementation basis of the boot animation, plus the audio voice-line assets, © 2026 Honghong Shen, MIT
- Duckwork desktop plugin SDK — contribution areas, on-disk plugin loading and development docs
- The Duckwork icon is © [Fordex](https://fordex.com); it is used here solely as the product mark on the boot screen

## License

[MIT](./LICENSE) (including the original project's copyright notice)
