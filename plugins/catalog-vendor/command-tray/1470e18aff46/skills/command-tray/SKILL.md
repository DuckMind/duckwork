---
name: command-tray
description: >
  Use when the user asks which shell commands the agent ran this session, or
  wants to reuse one. Load with skill_view("command-tray:command-tray").
---

# command-tray

This plugin records shell commands from the `terminal` tool on `post_tool_call`
(success and failure). It does not execute commands itself.

## When to use

- User: "hangi komutları çalıştırdın", "what commands did you run", "rerun that"
- Call `command_tray_list` with `markdown: true` and paste the list
- Do not invent commands that are not in the tray

## Clear

Only call `command_tray_clear` when the user asks to start a fresh command list.
