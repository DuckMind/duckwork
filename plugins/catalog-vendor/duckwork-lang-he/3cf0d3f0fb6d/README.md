<div align="center">

  <a href="https://github.com/DuckMind/duckwork">
    <img src="https://github.com/user-attachments/assets/ac2f5702-c842-4b2e-9340-737481fa0ece" width="96" height="96" alt="Fordex Duckwork mark" />
  </a>

  # Duckwork in Hebrew · עברית

  **Duckwork, right to left.**

  A Hebrew language pack for Duckwork Agent: the CLI, the messaging gateway, the TUI and Duckwork Desktop.
  Desktop flips to a right-to-left layout; prompts, replies and tips come back in Hebrew.

  <sub>POWERED BY <a href="https://github.com/DuckMind/duckwork">DUCKWORK AGENT</a> &nbsp;·&nbsp; COMMUNITY PLUGIN &nbsp;·&nbsp; VERSION 0.1.0</sub>

  <br /><br />

  [What it covers](#what-it-covers) &nbsp;·&nbsp; [Install it](#install) &nbsp;·&nbsp; [What it does on your machine](#what-it-does-on-your-machine)

</div>

![A marble Duckwork reads a mirrored, right-to-left window of dithered glyphs](assets/catalog-banner.png)

## What it covers

Duckwork does not ship Hebrew, so this pack brings all three catalogs:

| Surface | File | Translated | Covers |
| --- | --- | --- | --- |
| Core | `locales/he.yaml` | 3,396 of 3,486 | CLI prompts and messages, approval prompts, gateway replies, platform messages, tips |
| TUI | `locales/he.tui.yaml` | 1,331 of 1,356 | `duckwork --tui`: status bar, composer, hotkey help, prompts |
| Desktop | `locales/he.desktop.yaml` | 5,153 of 5,245 | Duckwork Desktop, with the layout flipped to right-to-left |

Counts are against Duckwork `main` at the commit named in each file's header. Anything the pack does not translate falls back to English, so a newer Duckwork never shows a blank label.

What stays in English:

- What the agent itself writes. Ask it to answer in Hebrew in your prompt or in `SOUL.md`.
- Commands, flags, config keys, environment variables, file paths and product names, so they still match what you type.
- Answer letters the code matches on (`[o]`, `[s]`, `[a]`, `[d]` in approval prompts), and markers Duckwork reads back.
- A handful of Desktop and TUI labels whose English wording changes with an argument (Show/Hide, on/off). The pack format carries one wording per label, so those keep the correct English text instead of a Hebrew one that would be wrong half the time.

## Install

```sh
duckwork plugins install Adolanium/duckwork-lang-he
duckwork config set display.language he
```

Restart a running gateway or TUI so it picks up the pack. In Desktop, pick **עברית** in the language switcher.

The pack needs Duckwork Agent 0.21.6 or later.

## What it does on your machine

Nothing beyond adding text.

- Three YAML catalogs and a manifest. No network calls, no files read outside its own folder, no shell commands, no background processes, no telemetry.
- `__init__.py` exists only so Desktop's "Install from Git" accepts the pack ([duckwork-agent#138118](https://github.com/DuckMind/duckwork)); its `register()` does nothing.
- Installing the pack never changes your language. You opt in with `display.language`.

## Translation notes

- Gender-neutral wording throughout: impersonal forms ("יש ל…", "אפשר ל…") and verbal nouns for buttons ("שמירה", "סגירה").
- Terms: session = סשן, skill = מיומנות, plugin = תוסף, profile = פרופיל, provider = ספק, agent = סוכן, subagent = סוכן משנה.
- Product names stay in Latin script, joined with a hyphen when Hebrew adds a prefix ("ה-backend", "ב-Stripe").
- The Desktop catalog started from the Hebrew translation proposed in [duckwork-agent#124840](https://github.com/DuckMind/duckwork), brought up to date with current Duckwork.

Corrections are welcome as issues or pull requests.

## Keeping it current

Duckwork adds and renames strings often. To see what changed against a duckwork-agent checkout:

```sh
python tools/sync_keys.py ../duckwork-agent
python tools/sync_keys.py ../duckwork-agent --missing missing.txt   # list untranslated keys
python tools/sync_keys.py ../duckwork-agent --fix                   # drop keys Duckwork no longer has
```

Then check the pack the same way the catalog does:

```sh
duckwork plugins validate .
```

<br />

<div align="center">
  <strong>Duckwork in Hebrew</strong><br />
  <sub>The same agent, right to left.</sub>
</div>

<br />

## License

[MIT](LICENSE).

> **Community project**
>
> Duckwork in Hebrew is an independent community plugin. It is not affiliated with, endorsed by, sponsored by, or officially associated with [Fordex](https://github.com/DuckMind/duckwork) or the [Duckwork Agent project](https://github.com/DuckMind/duckwork). Duckwork, Duckwork Agent and Fordex are names and marks belonging to their respective owners.
