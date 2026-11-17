# Portable workflow files (publish = put the file on git)

There is no index, service, or marketplace: a workflow is published when someone commits the file to a repo and shares the path. The convention:

1. One graph per file, named `<name>.workflow.json` — plain UTF-8 JSON, a regular file of at most 1 MiB with no final symlink, holding the same `{name, nodes, …}` object the `workflow` tool's `run` action accepts inline.
2. State the dialect at the top: `"grammar": "wf/1"`. Absent means `wf/1` (every file written before the tag existed is a `wf/1` file); a value this reader does not know is refused before any write or spawn, with the supported list in the error — a newer dialect is never misrun.
3. Add a `provenance` block (encouraged, optional): `owner` (who maintains it), `source` (where the canonical copy lives, ≤ 200 chars), `source_digest` (sha256 of the canonical `nodes` JSON — `wfcommon.source_digest(graph)`). Attribution only; nothing reads it to allow or deny.
4. Drop the file anywhere on disk and run it: `workflow{action:"run", graph_path:"/abs/path/<name>.workflow.json"}`; `save` with `graph_path` shelves it in the library for `run from:<name>`.
5. Keep it self-contained: no absolute paths of your machine, no secrets, no profile names — `{run.KEY}` inputs and `profile` are the receiver's to bind. A file that uses the graph-level `include` key (shipped in v1.3.0) is not portable as published: the aliases name graphs in the author's own library, which the receiver does not have. Inline the included graphs (or publish them alongside as their own portable files and say so) before sharing.
6. Budgets (`max_turns`, `timeout`, `shape`) travel with the file but are policy, not work: a receiver may raise them without changing any node's fingerprint.
7. Pin what you publish: record the file's sha256 next to the link so a reader can check `sha256sum <file>` before running it.
8. A `wf/1` file carries NO code. Nodes are goals, schemas, edges and gates; every action is performed by the receiver's own Duckwork with the receiver's own tools and consent. Contrast Anthropic-style `.js` workflow files, which DO carry executable code — that is the dialect line, and the reason `grammar` exists.
9. Validate before sharing: `python3 -c 'import json,wfcommon; print(wfcommon.validate_graph_errors(json.load(open("<file>")), admission=True))'` from the plugin root must print `[]`. Pass `admission=True` so the check runs the same door-side rules the run door applies — without it a portable graph baked with `fanout.items: []` prints `[]` here and only trips at the run door (est-73vk).
10. `grammar` and `provenance` are top-level annotations: they never enter `def_hash`, the effective fingerprint (`efp`), `graph_fingerprint` or `source_digest`, so adding them to an existing file changes no committed node.

## Walk-in example

`examples/review/portable-review.workflow.json` — recon → two-way fan-out review → summary, `grammar: "wf/1"` with a provenance block. Supply `run_context: {"target_dir": "/abs/path/to/files-to-review"}`; the target must contain at least two readable files. Pinned:

- file sha256 (`sha256sum examples/review/portable-review.workflow.json`): `f57677e344ea051b2f087a5673319c6865d8b863e2dd5d73bcf921b493b00483`
- `source_digest` (canonical `nodes` JSON): `d3c024d89563d84cf8af104752e22741350533a1977b843f382a51aeee436634`

`tests/test_portable_32.py` asserts the example validates and that both digests still match this page; editing the example means re-pinning here in the same commit.

## The js dialect seam: `wf_dialect.py`

Anthropic-style `.claude/workflows/<name>.js` files are the other dialect of the same graph shape ([dialect](dialect.md) is the mapping table; `tests/fixtures/dialect/` is its executable form). `wf_dialect.py` is a standalone stdlib module at the plugin root — deliberately NOT a `workflow` tool action: interop is an authoring-time file conversion, and the tool's action set stays closed. Two commands, run from the plugin root:

- Import: `python3 wf_dialect.py import <script.js>` prints `{"ok": true, "graph": {…wf/1…}, "warnings": […]}` (exit 0) or `{"ok": false, "refuse": "<construct> at line N"}` (exit 1). Only the [§3 subset](dialect.md#3-the-importable-subset-stated-once) imports: literal `meta`, sequential `const x = await agent(template, {schema, label, model, phase})`, a static `parallel([...])` of agent calls/thunks, `pipeline(<const>.<field> | [literal], stage…)` with every stage a direct `agent(...)`, `phase()`/`log()` literals (dropped, reported), a bare `return <const>` or `return <pipeline>.filter(Boolean)`. Everything else is refused with the construct and its line named — never approximated. Save the `graph` to `<name>.workflow.json` and run it with `graph_path`.
- Export: `python3 wf_dialect.py export <graph.json> [--name N] [--out <dir>/<name>.js]` writes their shape (static `meta`, `await agent(...)` in wave order, `parallel([...])` for a static fan-out, `pipeline(...)` for `items_from` and chained fan-outs, `{run.KEY}` → `${args.KEY}`, `phase('Wave n')` from `after` depth). `--out` never creates the directory. Output is byte-stable for equal input.

Lossy-export warning rule: every wf/1 key with no counterpart on their side is emitted as a `// LOSSY: <key> = <value>` comment line AT the node and listed again in the header `// LOSSY SUMMARY`, and printed once per key on stderr; nothing is dropped silently. The keys that can surface:

| Scope | Keys reported lossy |
| --- | --- |
| agent node | `provider`, `toolsets`, `max_turns`, `timeout`, `run_budget`, `reasoning`, `tier`, `shape`, `repo`, `require_route`, `route_verified`, `profile`, `requires` |
| gate node | `hold_timeout`, `on_skip`, `requires`, `context`, `wait`, `when` |
| fan-out | per-item `schema` (when not carried by the parallel form), `{index}` in a pipeline template |
| graph | `model_policy`, any `defaults` key with no js counterpart |

A human gate becomes a `// HOLD: <question> [options]` stub whose const carries `default_option`. A graph whose semantics have no representation at all is REFUSED by name, mirroring the importer: a fan-out `quorum` (race), a human gate with no `default_option`, a `when` gate that prunes descendants, an `inputs` ref inside a fan-out's `{items, all_results}` object other than `.items`. The optional `node --check` syntax gate runs when `node` is on PATH; when it is absent the result carries `node_check: skipped` plus one warning and the importer's own scanner is the only gate (never a crash). Library use: `import wf_dialect; wf_dialect.js_import(source)` / `wf_dialect.export_report(graph)` (`js_export` raises `DialectRefusal`).
