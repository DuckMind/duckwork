# Dialect fixture corpus (issue #31 → contract for #33)

Each `<name>.js` is a Claude Code dynamic-workflow script in Anthropic's documented shape
(`export const meta`, top-level `await`, `agent()/parallel()/pipeline()/phase()/log()`,
`args` global, top-level `return`). Each `<name>.expected.json` is the verdict the
constrained-subset importer (#33) MUST produce: `{verdict: "importable" | "refuse",
reason, rows: [dialect.md table rows], ...}`. Importable fixtures carry a `graph_sketch`
(the expected `wf/1` shape, not a golden byte-for-byte); refusals carry
`refuse_construct` + `refuse_line` (1-based, the FIRST construct the importer must name).

`audit-routes.js` is the docs' canonical example verbatim; `pipeline-glue-stage.js` is
the cookbook's stage-2 idiom. The rest are hand-written to pin one row each of
`references/dialect.md`. Every `.js` passes `node --check` (a `.js` path — the same bytes
as `.mjs` or via stdin fail on the top-level `return`). The importer/exporter is
`wf_dialect.py` (#33); `tests/test_dialect_js_33.py` asserts every sidecar here. Edit fixtures
by hand and keep `refuse_line` in step. `golden-export.workflow.json` is the EXPORTER's golden
(our graph, every lossy family); its exported bytes are sha256-pinned in that test.
