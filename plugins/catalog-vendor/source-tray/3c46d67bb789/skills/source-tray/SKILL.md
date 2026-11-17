---
name: source-tray
description: >
  Use when the user asks for sources, citations, or which URLs the agent opened
  this session. Load with skill_view("source-tray:source-tray").
---

# source-tray

This plugin records http(s) URLs from `web_search`, `web_extract`, and
`browser_navigate` on `post_tool_call`. It does not search the web.

## When to use

- User: "kaynakları ver", "what did you read", "cite that"
- Call `source_tray_list` with `markdown: true` and paste the list
- Do not invent URLs that are not in the tray

## Clear

Only call `source_tray_clear` when the user asks to start a fresh source list.
