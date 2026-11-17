# Changelog

## 1.0.0

First public release.

- A window over every session, opened with `Cmd+Option+F`, from `Cmd+K`, or from
  the search glyph in the bottom bar, whose hover shows the chord.
- Keyword search over message text, tool output and tool arguments, with typed
  filters (`in:`, `-in:`, `after:`, `before:`, `me:`, `repo:`, quoted phrases)
  mirrored as chips.
- Meaning search when a `session-find` service answers on `127.0.0.1:8474` or
  `SESSION_FIND_URL`; the backend's own `/status` decides which halves the window
  offers, so a machine with no service gets a working window instead of an error.
- Preview pane with the matching message and its neighbours.
- Pinned and recent sessions on the empty box, row ages, and the round trip in
  the footer in whole milliseconds.

### Notes on the release

- The two retrieval toggles are glyphs with the explanation on hover, and Meaning
  is on while Keywords is off by default. Turning Keywords on adds the exact word
  half; on a backend with no service the window switches to Keywords by itself.
- The native backend reads the gateway's own SQLite full text index read only. It
  never writes, and there is no self-updater: this plugin is installed at a pinned
  commit, and updates arrive as a catalog SHA bump.
