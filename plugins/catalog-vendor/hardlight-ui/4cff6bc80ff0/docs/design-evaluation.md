# Review a fixed brief without inventing a benchmark

Use the checked-in [print-room](../examples/briefs/print-room.json), [incident-desk](../examples/briefs/incident-desk.json) and [field-journal](../examples/briefs/field-journal.json) briefs to keep tasks and constraints stable while assessing changes. All content is illustrative. The two product briefs intentionally share a surface: they should make a host author different concepts even though the deterministic candidate grammars can be identical.

```sh
python -m hardlight direction --input examples/briefs/print-room.json
python -m hardlight reference layout
python -m hardlight reference platform
python -m hardlight reference performance
```

## Inspect a completed design contract

The returned worksheet starts uncompleted. A reviewer should identify the actual artifact and answer:

- Does the premise belong to the supplied subject, with a real proof artifact or content model?
- For the new incident desk, do alternatives differ in structure and task tradeoffs? For Set and the journal, are incumbent identity and working routes preserved?
- Do visual rules connect the initial view, utility controls, error/empty states and narrow view?
- Does one signature help a user do something, and is its no-motion/no-support equivalent complete?
- Would substituting another subject force meaningful changes to composition, assets or interaction?
- Are facts, budgets and test status explicit, with unknowns left unknown?

Record observation, consequence, evidence, severity and proposed correction. Use blocker, material improvement or deliberate tradeoff. Do not average these into a beauty score or treat a list of detected CSS properties as proof of design quality.

## Exercise tasks, not only screenshots

For Set: select a job, reach its jacket at 320/390/768/1440 widths and inside a narrow embedded container, filter to zero results, recover, update a note, navigate Back and reload. Reload must reset session changes. Check keyboard, enlarged text, forced colors, long input, JavaScript-off content and the CSS-enhancement fallback.

For the journal: find a passage, open its direct fragment, clear the filter and return using Back. Inspect captions and difficult text at narrow widths and with fallback fonts. For a future incident-desk implementation: follow one event, preserve the incident context, reach its evidence and recover from an unavailable item. That implementation does not exist in this repository; its task script is a proposed evaluation, not recorded success.

Capture the initial and relevant engaged states with browser/build/viewport information. Keep generated artifacts and judge notes if an explicitly authorized model comparison is later performed; use the same briefs and tools, independent reviewers and a stated sample/method. This change ran no model-generation benchmark, paid inference or user study. Source tests prove context/schema behavior; browser tests prove bounded example behavior. Neither establishes superior generated design.
