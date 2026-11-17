# Session Find

A search window over your Duckwork session history. Press `Cmd+Option+F`, type what
you remember, and the sessions that talked about it come back as a list you can
walk with the arrow keys.

```
Find a session
Type what you remember. Arrow keys move, Enter opens, Tab switches Best match and Newest.
```

It is a window, not a page: it gets no sidebar row, and it opens from three doors,
the keybind, `Cmd+K` ("Find a session"), and the search glyph in the bottom bar
whose hover shows the chord.

## What it does

- **Searches everything you have ever said to Duckwork**, not just titles: message
  text, tool output and tool arguments are all in the index.
- **Matches words or meanings.** Keywords finds an exact word, identifier or
  phrase. Meaning finds a session by what it was about, which is how you find the
  conversation where you discussed something whose name you have forgotten.
- **Typed filters**, mirrored as chips under the box: `in:source`, `-in:source`,
  `after:`, `before:`, `me:`, `repo:`, and `"an exact phrase"` in quotes.
- **A preview pane** with the matching message and its neighbours, so you can tell
  two similar sessions apart before opening one.
- **Pinned and recent sessions** on the empty box, and the age of every row.
- **The wait, in the footer**: `30 sessions · 27 ms`, the round trip for the list
  on screen, coloured by how quick it was.

## Requirements

None. No credentials, no environment variables, no network access. It reads the
session database the gateway already keeps, read only.

The window answers from one of two backends, and `/status` decides which:

| backend | when | can do |
|---|---|---|
| **service** | a `session-find` service answers on `127.0.0.1:8474` (or `SESSION_FIND_URL`) | keywords and meanings |
| **native** | no service is running | keywords only |

The native backend is the gateway's own SQLite full text index over messages, so
a fresh install has a working window with nothing else to run. When a service is
not there, the window keeps Keywords on, greys the Meaning glyph and says on its
hover why, rather than failing your first search. Point `SESSION_FIND_URL` at a
service to get the meaning half as well; `SESSION_FIND_STATE_DB` overrides the
database the native backend reads.

## Install

```
duckwork plugins install djmango/session-find
duckwork plugins enable session-find
```

The window half ships **off by default**, because it draws inside the app. Switch
it on in the app's plugin inventory (Capabilities, then Plugins), and the glyph
appears in the bottom bar. Then press `Cmd+Option+F`.

By hand, if you prefer: copy this directory to `<duckwork home>/plugins/session-find`
and the window to `<duckwork home>/desktop-plugins/session-find/plugin.js`, then
reload desktop plugins from `Cmd+K`.

## Keys

| key | what it does |
|---|---|
| `Cmd+Option+F` | open the window |
| `Up` / `Down` | move the highlight |
| `Cmd+J` / `Cmd+K` | move the highlight, on macOS |
| `Enter` | open the highlighted session |
| `Cmd+Enter` | open it in a new tab, `Cmd+Shift+Enter` in a new window |
| `Tab` | switch Best match and Newest |
| `Cmd+R` | cycle the scope: all sessions, this profile, this repo |
| `Escape` | close the window |

A move never opens anything: only `Enter` or a click does.

## What it does not do

- **No vector search without a service.** The native backend has no model, so
  Meaning needs a session-find service. Keywords works everywhere.
- **No writes.** The session database is opened read only; the only thing the
  plugin stores is your two toggle choices and the sort order, in plugin storage.
- **No network calls.** The window talks to the gateway it already has a session
  with, and the gateway talks to `127.0.0.1` when a service is configured.
- **No agent tools, hooks or middleware.** It registers none, and declares none.

## Develop

The window is `desktop/plugin.js`, plain ESM loaded uncompiled by the app, so
nothing typechecks it. Its tests guard what a compiler would not:

```
node --test tests/plugin.test.mjs
```

They check that no `jsx()` call carries a third argument (that slot is the element
key, and children put there vanish), that only `@duckwork/plugin-sdk`, `react` and
`react/jsx-runtime` are imported, that no em dash or emoji reached the file, that
the keybind does not collide with a built-in one, and that the pure helpers behind
the chips, the keys, the rows and the footer behave.

## License

MIT. See `LICENSE`.
