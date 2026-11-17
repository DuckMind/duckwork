// Regression (item #12): card/list update with metrics MISSING entirely must
// render 'unknown', never throw and never fabricate 0. Renders the actual
// affected components from desktop/plugin.js (MiniGraph pill, ItemChips,
// ItemDetail, Timeline vitals rail, WorkflowsPage run header) with tiny stubs.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'desktop', 'plugin.js'), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  assert.ok(i >= 0, name)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
const jsx = (type, props) => ({ type, props })
const jsxs = jsx
const walk = node => Array.isArray(node)
  ? node.flatMap(walk)
  : node && typeof node === 'object' ? [node, ...Object.values(node.props || {}).flatMap(walk)] : []
const texts = node => walk(node).flatMap(n => typeof n === 'string' ? [n] : typeof n.props?.children === 'string' ? [n.props.children] : [])

// -- ItemChips: running chip with metrics missing entirely + read-once -------
const $fanItem = { set() {} }
const EDGE_TONE = { done: 'D', failed: 'F', running: 'R', held: 'H', skipped: 'S', pending: 'P' }
const idleS = m => (m && m.last_activity ? 5 : null)
const { ItemChips } = new Function('jsx', 'jsxs', '$fanItem', 'Dot', 'EDGE_TONE', 'idleTone', 'idleS', 'kfmt',
  `${grab('ItemChips')}; return { ItemChips }`)(jsx, jsxs, $fanItem, 'Dot', EDGE_TONE, () => 'TONE', idleS, String)
{
  let reads = 0
  const row = { index: 0, status: 'running', label: 'a', goal: 'g' }
  Object.defineProperty(row, 'metrics', { get() { reads++; return undefined } })
  const chip = ItemChips({ runId: 'r', nodeId: 'a', rows: [row], picked: null, size: 'sm' }).props.children[0]
  assert.equal(reads, 1, 'ItemChips must read row.metrics exactly once (guard and deref share one binding)')
  assert.equal(chip.props.children[2], null, 'running chip without metrics renders no spend span, no throw')
  const doneRow = { index: 1, status: 'done', label: 'b', metrics: undefined }
  assert.equal(ItemChips({ runId: 'r', nodeId: 'a', rows: [doneRow], picked: null, size: 'sm' }).props.children[0].props.children[2], null,
    'done chip without metrics renders no token span')
  // metrics row present but no api_calls field => unknown '?', never fabricated 0
  const empty = { index: 2, status: 'running', label: 'c', goal: 'g', metrics: {} }
  const txt = texts(ItemChips({ runId: 'r', nodeId: 'a', rows: [empty], picked: null, size: 'sm' })).join('|')
  assert.ok(txt.includes('?⚡'), `missing api_calls must render unknown: ${txt}`)
  assert.ok(!txt.includes('0⚡'), `missing api_calls must never render as 0: ${txt}`)
  const withCalls = { index: 3, status: 'running', label: 'd', goal: 'g', metrics: { api_calls: 3 } }
  assert.ok(texts(ItemChips({ runId: 'r', nodeId: 'a', rows: [withCalls], picked: null, size: 'sm' })).join('|').includes('3⚡'),
    'positive control: real api_calls still render')
}

// -- ItemDetail: metrics missing entirely -------------------------------------
{
  const { ItemDetail } = new Function('jsx', 'box', 'label', 'Dot', 'Badge', 'Vitals', 'fmtDur', 'fmtOutput', 'EDGE_TONE',
    `${grab('ItemDetail')}; return { ItemDetail }`)(jsx, t => jsx('div', { children: t }), () => 'lbl', 'Dot', 'Badge', 'Vitals', () => '1s', x => x, EDGE_TONE)
  const nodes = walk(ItemDetail({ row: { index: 0, status: 'running', label: 'a', goal: 'g' }, compact: true }))
  assert.ok(!nodes.some(n => n.type === 'Vitals'), 'no Vitals when metrics missing')
  assert.ok(!texts(nodes).some(t => t.startsWith('last:')), 'no last: line when metrics missing')
}

// -- MiniGraph pill: running node whose state row has no metrics --------------
{
  const { columnGroups: cgM, bandRows: brM } = new Function(
    `${grab('columnGroups')}\n${grab('bandRows')}; return { columnGroups, bandRows }`)()
  const { MiniGraph } = new Function('jsx', 'jsxs', 'useRef', 'useValue', '$fanOpen', 'Dot', 'EDGE_TONE', 'NODE_TONE', 'nodeState',
    'depthMap', 'useCardRects', 'Edges', 'MINI', 'useCanvasWidth', 'columnGroups', 'bandRows',
    `${grab('MiniGraph')}; return { MiniGraph }`)(
    jsx, jsxs, () => null, () => null, {}, 'Dot', EDGE_TONE,
    Object.fromEntries(Object.entries(EDGE_TONE).map(([k, v]) => [k, { color: v, borderColor: v, shadow: null, shadowHover: null, pulseMs: null, calm: true, ui: 'muted', gate: null, breathe: null }])),
    (def, states) => states[def.id]?.status || 'pending',
    nodes => new Map(nodes.map(n => [n.id, 0])), () => ({}), 'Edges',
    { pillH: 20, pillW: 84, colGap: 34, rowGap: 6, pad: 4 },
    () => 4000, cgM, brM)
  const render = state => MiniGraph({ detail: { id: 'r', graph: { nodes: [{ id: 'a' }] }, nodes: { a: state } } })
  let reads = 0
  const bare = { status: 'running' }
  Object.defineProperty(bare, 'metrics', { get() { reads++; return undefined } })
  const nodes = walk(render(bare))
  assert.equal(reads, 1, 'MiniGraph pill must read state.metrics exactly once')
  assert.ok(!nodes.some(n => n.props?.title === 'api calls'), 'running pill without metrics renders no api_calls span, no throw')
  const hit = texts(render({ status: 'running', metrics: { api_calls: 4 } })).join('|')
  assert.ok(hit.includes('4⚡'), 'positive control: pill shows api_calls when the row exists')
}

// -- Timeline rail: node row present with NO metrics row ----------------------
{
  const { Timeline } = new Function('useValue', 'useTick', 'parseTime', 'jsx', 'jsxs', 'box', 'timelineTone', 'fmtDur', 'cn',
    '$selNode', '$fanItem', 'Vitals', `${grab('Timeline')}; return { Timeline }`)(
    () => null, () => {}, x => Date.parse(x), jsx, jsxs, (t, ...k) => jsx('div', { children: k }),
    () => 'TONE', () => '1s', (...xs) => xs.join(' '), {}, { set() {} }, 'Vitals')
  const render = nodes => Timeline({
    detail: { id: 'r', status: 'running', nodes, events: [
      { event: 'run.started', ts: '2026-01-01T00:00:00Z' },
      { event: 'node.started', node: 'a', ts: '2026-01-01T00:00:01Z' }
    ] }
  })
  let reads = 0
  const bare = { status: 'running' }
  Object.defineProperty(bare, 'metrics', { get() { reads++; return undefined } })
  const nodes = walk(render({ a: bare }))
  assert.equal(reads, 1, 'Timeline must read node.metrics exactly once (no torn re-deref)')
  assert.ok(!nodes.some(n => n.type === 'Vitals'), 'no Vitals rail entry when metrics missing')
  const hit = render({ a: { status: 'running', metrics: { tokens_out: 12 } } })
  assert.ok(walk(hit).some(n => n.type === 'Vitals'), 'positive control: Vitals renders when metrics present')
}

// -- WorkflowsPage run header: detail WITHOUT a metrics row at all ------------
{
  const detail = { id: 'r1', status: 'running', graph: { nodes: [{ id: 'a' }] }, nodes: { a: { status: 'running' } } }
  // #48: the run header renders through runHeaderModel (the ONE tone table);
  // build the real one with the same NODE_TONE shim pattern as test_canvas_wrap.
  const EDGE_TONE_H = { done: 'D', failed: 'F', running: 'R', held: 'H', skipped: 'S', pending: 'P' }
  const NODE_TONE_H = Object.fromEntries(Object.entries(EDGE_TONE_H).map(([k, v]) => [k, { color: v, borderColor: v, shadow: null, shadowHover: null, pulseMs: null, calm: true, ui: 'muted', gate: null, breathe: null }]))
  const runHeaderModel = new Function('NODE_TONE', 'TERMINAL', 'parseTime', 'fmtDur',
    `${grab('runHeaderModel')}; return runHeaderModel`)(
    NODE_TONE_H, new Set(['done', 'failed', 'stopped']),
    v => (typeof v === 'number' ? v : v ? Date.parse(v) || null : null), ms => `${Math.round(ms / 1000)}s`)
  // agent-first (2026-10-03): the header names the launching agent; originLabel
  // rides the injected deps (grab the exported function verbatim).
  const oi = src.indexOf('export function originLabel(')
  assert.ok(oi >= 0, 'plugin exports originLabel (agent-first header)')
  const oend = src.indexOf('\n}', oi)
  assert.ok(oend > oi, 'originLabel body located')
  const originLabel = new Function(`${src.slice(oi, oend + 2).replace('export function', 'function')}; return originLabel`)()
  const { WorkflowsPage } = new Function('useQuery', 'useValue', '$selRun', 'listQuery', 'runQuery', 'box', 'Dot', 'statusLabel',
    'Vitals', 'Badge', 'GraphView', 'Drawer', 'Timeline', 'EmptyState', 'ScrollArea', 'RunRow', 'Fragment', 'jsx', 'jsxs', 'runHeaderModel', 'PolishStyles', 'originLabel',
    `${grab('WorkflowsPage')}; return { WorkflowsPage }`)(
    q => (q.queryKey?.[2] === 'run' ? { data: detail } : { data: { runs: [{ id: 'r1', status: 'running' }] } }),
    () => null, { get() { return null }, set() {} }, () => ({ queryKey: ['x', 'runs'] }), id => ({ queryKey: ['x', 'run', id] }),
    (t, ...k) => jsx('div', { children: k }), 'Dot', s => s, 'Vitals', 'Badge', 'GraphView', 'Drawer', 'Timeline',
    'EmptyState', 'ScrollArea', 'RunRow', 'Fragment', jsx, jsxs, runHeaderModel, 'PolishStyles', originLabel)
  const nodes0 = walk(WorkflowsPage())
  // Deep review #156 A2 flip: "originator on every row" is the law — an
  // unattributable run shows the honest word, never silence and never a
  // fabricated name.
  assert.ok(texts(nodes0).some(t => t === '@unknown'), 'explicit @unknown chip when owner is absent (never fabricated, never silent)')
  const chips0 = texts(nodes0).filter(t => /^@/.test(t))
  assert.ok(chips0.length >= 1, 'at least one origin chip renders')
  assert.ok(chips0.every(t => t === '@unknown'),
            `every origin chip is the honest word, none invented: ${chips0}`)
  const nodes = walk(WorkflowsPage())
  assert.ok(!nodes.some(n => n.type === 'Vitals'), 'header shows no Vitals when run.metrics is absent')
  assert.ok(!texts(nodes).some(t => / live$/.test(t)), 'header shows no live count when metrics absent')
}

console.log('ALL PASS: metrics-missing renders unknown, never throws, never fabricates 0')
