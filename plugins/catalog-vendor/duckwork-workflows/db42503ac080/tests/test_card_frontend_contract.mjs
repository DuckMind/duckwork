// Exercise the actual Mac desktop directive parser plus this plugin's contribution
// adapter and skipped/terminal UI logic. Parser source is SHA-pinned in lane evidence.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const testsDir = dirname(fileURLToPath(import.meta.url))
const root = join(testsDir, '..')
const plugin = readFileSync(join(root, 'desktop', 'plugin.js'), 'utf8')
const macEvidence = readFileSync(join(testsDir, 'fixtures', 'mac-source.txt'), 'utf8').replaceAll('\r\n', '\n')
const between = (text, start, end) => {
  const a = text.indexOf(start)
  const b = text.indexOf(end, a + start.length)
  assert.notEqual(a, -1, `missing evidence marker ${start}`)
  assert.notEqual(b, -1, `missing evidence marker ${end}`)
  return text.slice(a + start.length, b)
}
const parserSource = between(macEvidence, '===== parser =====\n', '===== parser tests =====\n')
const expectedParserSha = '48cdf5a1083c0c6b9b2c815719942b6071c1e6291d697c55e2f2814e714aa9da'
assert.equal(createHash('sha256').update(parserSource).digest('hex'), expectedParserSha, 'captured parser bytes must match the Mac SHA-256')

const temp = mkdtempSync(join(testsDir, '.workflow-parser-'))
try {
  const parserPath = join(temp, 'transcript-directives.ts')
  writeFileSync(parserPath, parserSource)
  const parser = await import(pathToFileURL(parserPath).href)

  // The product parser consumes the literal syntax emitted by the workflow tool.
  const emitted = '::workflow{id="wf-123"}'
  const parsed = parser.parseTranscriptDirective(emitted)
  assert.deepEqual(parsed, { name: 'workflow', attrs: { id: 'wf-123' }, source: emitted })
  assert.equal(parser.TRANSCRIPT_DIRECTIVE_AREA, 'transcript.directives')
  assert.equal(parser.parseTranscriptDirective(''), null)
  assert.equal(parser.parseTranscriptDirective('::workflow{id=wf-123}')?.attrs && Object.keys(parser.parseTranscriptDirective('::workflow{id=wf-123}').attrs).length, 0)
  assert.equal(parser.parseTranscriptDirective('text ::workflow{id="wf-123"}'), null)
  assert.deepEqual(parser.segmentTranscriptDirectives(`started ${emitted}`)?.at(-1), {
    kind: 'directive', directive: { name: 'workflow', attrs: { id: 'wf-123' }, source: emitted }
  })

  // Match the plugin's exact registered contribution name/area and run the
  // product's actual registry lookup (`claimFor`) by that parsed name.
  const rendererSource = between(macEvidence, '===== renderer =====\n', '===== contribution lookup =====\n')
  assert.match(macEvidence, /TRANSCRIPT_DIRECTIVE_AREA,\n\s+type TranscriptDirectiveContribution/)
  assert.match(rendererSource, /useContributions\(TRANSCRIPT_DIRECTIVE_AREA\)/)
  const claimStart = rendererSource.indexOf('function claimFor(')
  assert.notEqual(claimStart, -1)
  let brace = rendererSource.indexOf('{', claimStart), depth = 0, end = brace
  for (; end < rendererSource.length; end++) {
    if (rendererSource[end] === '{') depth++
    else if (rendererSource[end] === '}' && --depth === 0) break
  }
  const claimSource = `export ${rendererSource.slice(claimStart, end + 1)}`
  const claimPath = join(temp, 'claim.ts')
  writeFileSync(claimPath, claimSource)
  const { claimFor } = await import(pathToFileURL(claimPath).href)

  const directiveBlockStart = plugin.indexOf("ctx.register({\n      id: 'directive',")
  assert.notEqual(directiveBlockStart, -1, 'plugin registers a transcript directive')
  const directiveBlockEnd = plugin.indexOf('\n    })', directiveBlockStart)
  assert.notEqual(directiveBlockEnd, -1)
  const directiveBlock = plugin.slice(directiveBlockStart, directiveBlockEnd)
  assert.match(directiveBlock, /area: TRANSCRIPT_DIRECTIVE_AREA/)
  assert.match(directiveBlock, /name: 'workflow'/)
  const renderExpr = directiveBlock.match(/render: (\(\{ attrs \}\) => jsx\(DirectiveCard, \{ id: String\(attrs\?\.id \?\? ''\) \}\))/)?.[1]
  assert.ok(renderExpr, 'registered renderer maps parsed attrs.id into DirectiveCard')
  const DirectiveCard = Symbol('DirectiveCard')
  const render = new Function('jsx', 'DirectiveCard', `return (${renderExpr})`)((type, props) => ({ type, props }), DirectiveCard)
  const contribution = { id: 'duckwork-workflows.directive', area: parser.TRANSCRIPT_DIRECTIVE_AREA, data: { name: 'workflow', render } }
  assert.equal(claimFor([contribution], parsed.name), contribution)
  const card = render({ attrs: parsed.attrs, source: parsed.source, streaming: false })
  assert.equal(card.type, DirectiveCard)
  assert.equal(card.props.id, 'wf-123')

  // The actual run-query helper must use that same id for the read-model lookup.
  const queryStart = plugin.indexOf('function runQuery(')
  assert.notEqual(queryStart, -1)
  let qbrace = plugin.indexOf('{', queryStart), qdepth = 0, qend = qbrace
  for (; qend < plugin.length; qend++) {
    if (plugin[qend] === '{') qdepth++
    else if (plugin[qend] === '}' && --qdepth === 0) break
  }
  const runQuerySource = plugin.slice(queryStart, qend + 1)
  let requestedPath
  const runQuery = new Function('Q', 'ID_OK', 'api', `${runQuerySource}; return runQuery`)(['duckwork-workflows'], /^[\w.-]+$/, async path => { requestedPath = path; return { id: 'wf-123' } })
  assert.deepEqual(runQuery(card.props.id).queryKey, ['duckwork-workflows', 'run', 'wf-123'])
  assert.deepEqual(await runQuery(card.props.id).queryFn(), { id: 'wf-123' })
  assert.equal(requestedPath, '/runs/wf-123')

  // Fan-out counters/rendering must treat skipped items as terminal and name
  // skipped state instead of folding it into pending or running.
  const fanCountsMatch = plugin.match(/const fanCounts = rows => \{[\s\S]*?\n\}/)
  assert.ok(fanCountsMatch, 'fanCounts helper exists')
  const fanCounts = new Function(`${fanCountsMatch[0]}; return fanCounts`)()
  const rows = [
    { status: 'done' }, { status: 'failed' }, { status: 'skipped' },
    { status: 'running' }, { status: 'pending' }
  ]
  assert.deepEqual(fanCounts(rows), { total: 5, done: 1, failed: 1, running: 1, skipped: 1, stopped: 0, pending: 1, terminal: 3 })

  const fanSummaryStart = plugin.indexOf('const fanSummary =')
  assert.notEqual(fanSummaryStart, -1)
  const fanSummarySource = plugin.slice(fanSummaryStart, plugin.indexOf('\n', fanSummaryStart))
  const fanSummary = new Function(`${fanSummarySource}; return fanSummary`)()
  assert.equal(fanSummary(fanCounts(rows)), '3/5 terminal ·1 skipped ·1▶, 1 failed')

  const fnStart = plugin.indexOf('function FanStrip(')
  assert.notEqual(fnStart, -1)
  let fbrace = plugin.indexOf(') {', fnStart) + 2, fdepth = 0, fend = fbrace
  for (; fend < plugin.length; fend++) {
    if (plugin[fend] === '{') fdepth++
    else if (plugin[fend] === '}' && --fdepth === 0) break
  }
  const fanStripSource = plugin.slice(fnStart, fend + 1)
  const jsx = (type, props, key) => ({ type, props, key })
  const jsxs = jsx
  const box = (className, ...children) => jsx('div', { className, children: children.length === 1 ? children[0] : children })
  const label = text => jsx('label', { children: text })
  const ItemChips = Symbol('ItemChips')
  const FanStrip = new Function('jsxs', 'jsx', 'box', 'label', 'fanCounts', 'fanSummary', 'ItemChips', `${fanStripSource}; return FanStrip`)(jsxs, jsx, box, label, fanCounts, fanSummary, ItemChips)
  const tree = FanStrip({ runId: 'wf-123', def: { id: 'f' }, rows, picked: null })
  const collectText = (value, out = []) => {
    if (typeof value === 'string') out.push(value)
    else if (Array.isArray(value)) value.forEach(v => collectText(v, out))
    else if (value && typeof value === 'object') collectText(value.props?.children, out)
    return out
  }
  assert.ok(collectText(tree).some(text => text === '3/5 terminal ·1 skipped ·1▶, 1 failed'), collectText(tree).join(' | '))

  const itemStart = plugin.indexOf('function ItemChips(')
  let ibrace = plugin.indexOf(') {', itemStart) + 2, idepth = 0, iend = ibrace
  for (; iend < plugin.length; iend++) {
    if (plugin[iend] === '{') idepth++
    else if (plugin[iend] === '}' && --idepth === 0) break
  }
  const ItemChipsFn = new Function('jsxs', 'jsx', '$fanItem', 'Dot', 'EDGE_TONE', 'idleTone', 'idleS', 'kfmt', `${plugin.slice(itemStart, iend + 1)}; return ItemChips`)(
    jsxs, jsx, { set() {} }, Symbol('Dot'), { done: 'done', failed: 'failed', running: 'running', skipped: 'skipped', pending: 'pending' }, () => '', () => null, String
  )
  const skippedChip = ItemChipsFn({ runId: 'wf-123', nodeId: 'f', rows: [{ index: 2, status: 'skipped', label: 'pruned' }], picked: null, size: 'sm' }).props.children[0]
  assert.match(skippedChip.props.style.border, /skipped/)
  assert.equal(skippedChip.props.style.textDecoration, 'line-through')

  const timelineStart = plugin.indexOf('const timelineTone =')
  const timelineEnd = plugin.indexOf('\n\n// Tier name', timelineStart)
  // #48: timelineTone reads the ONE tone table; derive NODE_TONE from the
  // same stub palette (same shim pattern as test_canvas_wrap).
  const timelineTone = new Function('EDGE_TONE', 'NODE_TONE', `${plugin.slice(timelineStart, timelineEnd)}; return timelineTone`)(
    { held: 'held', failed: 'failed', done: 'done', skipped: 'skipped', running: 'running' },
    Object.fromEntries(['pending', 'running', 'held', 'done', 'failed', 'stopped', 'skipped'].map(s =>
      [s, { color: s, borderColor: s, shadow: null, shadowHover: null, pulseMs: null, calm: s === 'done' || s === 'failed' || s === 'stopped', ui: 'muted', gate: null, breathe: null }]))
  )
  assert.equal(timelineTone({ kind: 'node', status: 'skipped' }), 'skipped')
  assert.equal(timelineTone({ kind: 'gate', status: 'skipped' }), 'skipped')
  assert.equal(timelineTone({ kind: 'gate', status: 'held' }), 'held')
  assert.equal(timelineTone({ kind: 'gate', status: 'done' }), 'done')
  assert.equal(plugin.includes("title: 'Terminal fan-out items'"), true)
  const nodesCountStart = plugin.indexOf('const nodesCount =')
  const nodesCountSource = plugin.slice(nodesCountStart, plugin.indexOf('\n', nodesCountStart))
  const nodesCount = new Function(nodesCountSource + '; return nodesCount')()
  assert.equal(nodesCount({ nodes_done: 3, nodes_total: 5 }), '3/5 terminal')
} finally {
  rmSync(temp, { recursive: true, force: true })
}

console.log('ALL PASS: Mac parser contract, workflow contribution lookup, run id, skipped terminal display')
