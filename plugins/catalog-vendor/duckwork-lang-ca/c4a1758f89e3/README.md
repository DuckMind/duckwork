# Duckwork Catalan language pack · Català

Catalan (`ca`) UI translations for [Duckwork Agent](https://github.com/DuckMind/duckwork):
CLI, gateway, TUI and Desktop.

## Install

Requires Duckwork Agent **0.21.6 or later** with language-pack support.

```bash
duckwork plugins install https://github.com/DuckMind/duckwork
duckwork config set display.language ca
```

Restart Duckwork to load the pack. If needed, check whether `DUCKWORK_LANGUAGE` overrides the setting.
To switch back: `duckwork config set display.language en`.

The pack translates UI text. To get replies in Catalan, ask the agent in your instructions.
Some built-in branding and non-text Desktop entries remain in English.

## Contributing

Edit values in `locales/`, preserving keys, placeholders, line breaks and command syntax.
Validate before submitting:

```bash
duckwork plugins validate /path/to/duckwork-lang-ca
```

## License

MIT. Derived from Duckwork Agent's English UI catalogs. See [LICENSE](LICENSE).
