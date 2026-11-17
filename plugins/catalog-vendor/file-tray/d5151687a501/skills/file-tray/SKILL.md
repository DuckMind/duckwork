---
name: file-tray
description: >
  Use when the user asks which files the agent read or edited this session.
  Load with skill_view("file-tray:file-tray").
---

# file-tray

This plugin records file paths from `read_file`, `write_file`, and `patch` on
`post_tool_call`. It does not read or write user files itself.

## When to use

- User: "hangi dosyalara baktın", "what files did you touch", "list edits"
- Call `file_tray_list` with `markdown: true` and paste the list
- Do not invent paths that are not in the tray

## Clear

Only call `file_tray_clear` when the user asks to start a fresh file list.
