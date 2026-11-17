---
name: reading-buddy
description: "Use when the user wants their local WeRead (微信读书) reading companion: sync or browse the bookshelf, reading stats and notes; find what to continue reading; turn selected notes into private reading cards; write weekly/monthly reading reviews. All data is local; a demo mode with fictional data is available for previews."
---

# Reading Buddy (读书搭子)

Local-first WeRead companion served over MCP (server key `rb`). The engine is
pinned to an immutable git commit and launched via npx; data lives only in the
plugin data directory (`READING_DATA_DIR` / `READING_CONFIG_DIR`). Source:
https://github.com/harrylabsj/reading-buddy

## Safety rules (hard boundaries)

- Data stays on the user's machine. Never publish, post, comment, or share to
  WeRead or anywhere else; cards and reviews are local files.
- Never ask for, repeat, or print `WEREAD_API_KEY` or any credential. The
  server reads it from the environment or its own 0600-permission config file.
- Distinguish quotes (原文), the user's own thoughts, and AI suggestions. When
  the user provides no personal reflection, produce excerpt compilations only —
  never fabricate insights.
- `reading_save_card` is the explicit write: save only cards/reviews the user
  has seen and confirmed.
- Every tool takes `mode`: `live` is the user's real data, `demo` is a
  fictional standalone dataset — use `demo` for previews and examples.

## Workflow

1. Check state first: `reading_ui_state` (live mode) shows sync state, goal,
   and today's reading time.
2. Find books: `reading_search_books` with a query or status filter
   (e.g. status=reading) — returns book ids.
3. Notes: `reading_get_notes` with a book id; it returns the loaded portion —
   if the note set is partial, say so; missing durations show as unavailable,
   never back-filled with zero.
4. Cards: `reading_prepare_card` drafts a card from selected note ids plus the
   user's own reflection; show the draft; only after the user confirms, save
   with `reading_save_card`.
5. Reviews: `reading_prepare_review` (period weekly/monthly) drafts the
   review; confirm, then save via `reading_save_card`.
6. `reading_open_dashboard` / `reading_ui_action` drive an MCP-App dashboard
   in hosts that render `ui://` resources; in plain MCP hosts they simply
   return data — prefer the other tools for answers.

## Setup note

Live sync needs a WeRead API key: the user can set `WEREAD_API_KEY` in the
environment (inherited by the MCP server process) or import it once with the
engine's CLI auth command. Without a key, demo mode still works.
