# Next: configure Vector

This is a **user-installed platform plugin**. Duckwork will not load it until
it is on `plugins.enabled` (the installer asks `Enable 'vector-platform' now?`
— choose yes, or run `duckwork plugins enable vector-platform`).

Then create the bot identity and allowlist **your** Vector npub:

```bash
duckwork gateway setup
# pick Vector → create or import identity → enter YOUR npub
duckwork gateway restart
```

Setup downloads `vector-bridge` on Linux/macOS (or cargo-builds it). After
gateway start the bot DMs **your** Vector account a hello. Reply there. Share
the printed **bot** npub with anyone else who should reach it.

Do not put an `nsec` or mnemonic in `~/.duckwork/.env`. Full reference:
https://github.com/DuckMind/duckwork
