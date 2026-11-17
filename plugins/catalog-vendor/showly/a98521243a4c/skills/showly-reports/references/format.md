# Report draft format

Adapted from Answer me with HTML; attribution and license are in
`../THIRD_PARTY_LICENSES.txt`.

````markdown
---
title: Cache options
lang: en
template: sheet
theme: shadcn
---

The conclusion and its scope go here.

## Recommendation

```callout info Decision
Choose based on the workload and operational requirements below.
```

## Request path

```flow LR
Client -> Cache: lookup
Cache -> Database: miss
```

## Trade-offs

| Option       | Benefit      | Cost                     |
| ------------ | ------------ | ------------------------ |
| Local cache  | Low latency  | Per-process invalidation |
| Shared cache | Shared state | Network dependency       |
````

Each `##` heading creates a panel. `template: doc` creates a linear reading page
with a table of contents; `sheet` uses a panel layout. `theme: auto` selects a
theme for the content; built-ins are `blueprint`, `shadcn` and `paper`.
`lang: zh-CN` or another language tag sets page labels and language. Write the
draft itself in the user's language.

| Information            | Component fence      | Example syntax                           |
| ---------------------- | -------------------- | ---------------------------------------- |
| Flow or architecture   | `flow LR`            | `Client -> API: request`                 |
| Messages in time order | `sequence`           | `Client -> Server: SYN`                  |
| Hierarchy              | `tree`               | Indented lines                           |
| History                | `timeline`           | `2026-01 \| Milestone`                   |
| Value and limit        | `limits`             | `Storage \| 13 / 20 \| GB`               |
| Text annotations       | `annot`              | `[word]{explanation}`                    |
| Metadata               | `kv`                 | `Owner: Platform team`                   |
| Conclusion or caveat   | `callout info Title` | Markdown body                            |
| Comparison             | Markdown table       | `ok`, `no`, `warn` become status symbols |

For exact syntax, run `node <skill-dir>/scripts/report.mjs help <component>`.
Use `help format` for panel spans and frontmatter. Use ordinary Markdown links
for citations. A raw `html` or `svg` fence is available when no component fits;
do not render untrusted executable markup without inspecting it.

The writing check supports English and Chinese rules such as short sentences,
active wording and consistent terms. Warnings do not block rendering by default.
Use `lint draft.md --style strict` when strict checking is wanted. Keep intentional
technical terms and quotations accurate rather than changing their meaning to
satisfy a writing warning.
