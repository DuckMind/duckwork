---
name: done-bell
description: >
  Use when the user asks whether Duckwork finished, if the bell is muted, or
  about Done Bell notifications. Load with skill_view("done-bell:done-bell").
---

# done-bell

The user wants a notify when a Duckwork turn finishes so they can leave the window.
It does not send chat, write code, or read user files.

## When to use

- User: "bitti mi", "done bell", "notify when finished", "mute the bell"
- Call `done_bell_status` and quote muted / needs_you / recent kinds
- Do not invent events that are not in the tool result
