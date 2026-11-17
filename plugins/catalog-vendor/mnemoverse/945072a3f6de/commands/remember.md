---
description: Save a durable fact, decision, or correction to long-term memory
argument-hint: <the fact to remember>
---

Save the following to long-term Mnemoverse memory: $ARGUMENTS

Rules for the write:

1. One memory, one fact. If the input contains several independent facts, save them as separate memories and say how many you saved.
2. Write it so it survives: state what was decided or observed in one sentence, why (the reason outlives the decision), and where it came from (a file, a conversation, a test run) when that is known from context.
3. Prefer the user's own words over your paraphrase.
4. Never store secrets, API keys, passwords, payment data, or personal identifiers. If the input contains any, refuse that part, say why in one sentence, and save the rest if anything remains.
5. If no memory tool is connected, say so and point at the /mnemoverse:setup instructions (the bundled setup skill) instead of failing silently.

After saving, confirm with the stored text verbatim, so the user sees exactly what future sessions will recall.
