---
name: prompt-tray
description: >
  Use when the user asks about their saved Prompt Tray snippets, or wants a
  stored Review / Plan / Explain prompt. Load with skill_view("prompt-tray:prompt-tray").
---

# prompt-tray

The user keeps reusable chat prompts on the Desktop **Prompt Tray** pane.
Clicking one inserts it into the composer. It does not send the message.

## When to use

- User: "kayıtlı prompt'larım", "saved prompts", "review prompt"
- Call `prompt_tray_list` and quote titles/bodies
- Do not invent prompts that are not in the tray
