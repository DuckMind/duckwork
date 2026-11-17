// Stacked fan-out card must expand to per-item cards and collapse back (item #11).
// Drives the real GraphView/FanStack/ItemCard from desktop/plugin.js with the
// stub-React harness (same grab() style as test_edge_routing.mjs), including the
// live-append case: items arriving mid-run keep index keys and never reorder.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const src = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  assert.ok(i >= 0, `missing ${name}`)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
const constGrab = name => {
  const i = src.indexOf(`const ${name} =`)
  assert.ok(i >= 0, `missing const ${name}`)
  let depth = 0, j = src.indexOf('{', i)
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}

const jsx = (type, props, key) => ({ type, props, key })
const jsxs = jsx
const box = (className, ...kids) => jsx('div', { className, children: kids.length === 1 ? kids[0] : kids })
// walk materialises function components (jsx(FanStack,…)/jsx(ItemCard,…) are lazy
// nodes until their type is called), so inner buttons/chips become visible.
const walk = node => Array.isArray(node) ? node.flatMap(walk)
  : node && typeof node === 'object'
    ? typeof node.type === 'function' ? walk(node.type(node.props || {}))
      : [node, ...Object.values(node.props || {}).flatMap(walk)]
    : []

// Atom recorder: expansion/pick flow through these three plugin atoms.
const calls = []
const atom = name => ({ set: v => calls.push([name, v]) })
const $selNode = atom('selNode'), $fanItem = atom('fanItem'), $fanExpanded = atom('fanExpanded')
const state = { selNode: null, fanItem: null, expanded: null }
const useValue = a => a === $selNode ? state.selNode : a === $fanItem ? state.fanItem : state.expanded

const fanItemsFn = new Function(`${grab('fanItems')}\n${grab('itemLabel')}\n${grab('renderGoal')}\n${constGrab('fanCounts')}; return { fanItems, fanCounts }`)()
const EDGE_TONE = { done: 'teal', pending: 'gray', failed: 'red', running: 'blue', held: 'orange', skipped: 'gray' }
const cn = (...xs) => xs.filter(Boolean).join(' ')

const { columnGroups: columnGroupsFn, bandRows: bandRowsFn } = new Function(
  `${grab('columnGroups')}\n${grab('bandRows')}; return { columnGroups, bandRows }`)()

// GraphView composes FanStack/ItemCard/NodeCard/Edges — instantiate all together.
const { GraphView } = new Function(
  'jsx', 'jsxs', 'box', 'cn', 'Dot', 'Vitals', 'statusLabel', 'fmtDur', 'EDGE_TONE',
  'useValue', 'useRef', 'useState', 'useCardRects', 'Edges', 'EmptyState', 'NodeCard',
  'fanItems', 'fanCounts', 'depthMap', '$selNode', '$fanItem', '$fanExpanded',
  'useCanvasWidth', 'columnGroups', 'bandRows', 'CARD_W', 'NODE_TONE', 'edgeFlowPolicy',
  `${['depthMap', 'columnGroups', 'bandRows', 'FanStack', 'ItemCard', 'GraphView'].map(grab).join('\n')}\nreturn { GraphView }`
)(jsx, jsxs, box, cn, 'Dot', 'Vitals', s => s || 'unknown', ms => (ms ? `${Math.round(ms / 1000)}s` : ''), EDGE_TONE,
   useValue, () => ({ current: null }), () => [null, () => {}], () => ({}), 'Edges', 'EmptyState',
   props => jsx('div', { 'data-node-stub': props.def.id }),
   fanItemsFn.fanItems, fanItemsFn.fanCounts,
   nodes => new Map(nodes.map(n => [n.id, (n.after || []).length ? 1 : 0])),
   $selNode, $fanItem, $fanExpanded,
   () => 4000, columnGroupsFn, bandRowsFn, 168,
   // #48: FanStack reads the ONE tone table; derive NODE_TONE from the same
   // stub palette (same shim pattern as test_canvas_wrap).
   Object.fromEntries(Object.entries(EDGE_TONE).map(([k, v]) => [k, { color: v, borderColor: v, shadow: null, shadowHover: null, pulseMs: null, calm: true, ui: 'muted', gate: null, breathe: null }])),
   // F5 (#48 deep review): FanStack now consumes the ONE exported flow policy —
   // thread the REAL one from the source, not a second decision.
   new Function(`${grab('edgeFlowPolicy')}\nreturn edgeFlowPolicy`)())

const def = { id: 'f', after: ['prep'], fanout: { goal: 'g {index}', items: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] } }
const nodes = [{ id: 'prep' }, def]
const starts = [0, 1].map(index => ({ node: 'f', index, event: 'item.started' }))
const detail = events => ({
  id: 'r', graph: { nodes }, gate: null,
  nodes: { prep: { status: 'done' }, f: { status: 'running', item_metrics: { 0: { api_calls: 2, tokens_out: 50 }, 1: { api_calls: 1 } }, output: null } },
  events
})
const view = (expanded, events) => { state.expanded = expanded; return GraphView({ detail: events }) }
const badgeOf = tree => walk(tree).find(x => x.type === 'button' && String(x.props?.['aria-label'] || '').includes('fan-out items'))
const itemBtns = tree => walk(tree).filter(x => x.type === 'button' && typeof x.key === 'number')
const click = (el, arg) => { calls.length = 0; el.props.onClick({ stopPropagation: () => {} }, arg) }

// 1. ⌘K law: the plugin never traps keys — nothing can eat the app's ⌘K while expanded.
assert.ok(!/addEventListener\(['"]keydown/.test(src), 'no global keydown handlers: ⌘K stays app-owned, expanded or not')

// 2. COLLAPSED (default): stacked card, count badge is an expand button, no item cards.
const coll = view(null, detail(starts))
const badge0 = badgeOf(coll)
assert.ok(badge0, 'stacked card renders an expand/collapse affordance')
assert.equal(badge0.props['aria-expanded'], false, 'collapsed by default')
assert.match(String(badge0.props.children[0]), /(×3|\/3)/, 'badge keeps the N/M count text')
assert.equal(itemBtns(coll).length, 0, 'collapsed: no per-item cards')

// 3. EXPAND via the badge.
click(badge0)
assert.deepEqual(calls.find(c => c[0] === 'fanExpanded')?.[1], { runId: 'r', nodeId: 'f' }, 'badge click expands this fan-out')
const opened = view({ runId: 'r', nodeId: 'f' }, detail(starts))
const badge1 = badgeOf(opened)
assert.equal(badge1.props['aria-expanded'], true, 'badge reports expanded')
assert.match(String(badge1.props.children[1] || ''), /▴/, 'chevron flips when expanded')
const items = itemBtns(opened)
assert.deepEqual(items.map(b => b.key), [0, 1, 2], 'expanded: compact card per item, keyed by item index')
assert.ok(items.every(b => /running|pending|done/.test(JSON.stringify(b.props.children))), 'each item card reads status from the same rows')
const nodeDiv = walk(opened).find(x => x.props?.['data-node'] === 'f')
assert.ok(nodeDiv, 'stack keeps the measured data-node wrapper')
assert.equal(itemBtns(nodeDiv).length, 0, 'item cards are siblings below the stack, not inside the measured rect')

// 4. Item card click picks the item (same $fanItem vocabulary as the chips).
click(items[1])
assert.deepEqual(calls.find(c => c[0] === 'fanItem')?.[1], { runId: 'r', nodeId: 'f', index: 1 }, 'item card click picks item 1')
assert.ok(calls.some(c => c[0] === 'selNode'), 'pick also selects the node so the report panel opens')

// 5. COLLAPSE back clears expansion and the pick.
click(badge1)
assert.deepEqual(calls.filter(c => c[1] === null).map(c => c[0]), ['fanExpanded', 'fanItem'], 'collapse clears expansion and pick')
assert.equal(itemBtns(view(null, detail(starts))).length, 0, 'collapsed again: item cards gone')

// 6. LIVE-APPEND while expanded: rows exist from the graph def; mid-run events
//    (third start, then finishes) must re-render in place — keys stable, unique,
//    existing positions never move.
const keysFor = events => itemBtns(view({ runId: 'r', nodeId: 'f' }, detail(events))).map(b => b.key)
assert.deepEqual(keysFor(starts), [0, 1, 2], 'def-backed rows keep index keys')
assert.deepEqual(keysFor([...starts, { node: 'f', index: 2, event: 'item.started' }]), [0, 1, 2], 'item.started for index 2 does not reorder')
const settled = itemBtns(view({ runId: 'r', nodeId: 'f' }, detail([...starts, { node: 'f', index: 1, event: 'item.finished', status: 'done', ms: 2000 }])))
assert.deepEqual(settled.map(b => b.key), [0, 1, 2], 'finish event re-renders in place')
assert.equal(new Set(settled.map(b => b.key)).size, 3, 'no thrash: one card per index')
assert.match(JSON.stringify(settled[1].props.children), /done/, 'item 1 status moved in place (key unchanged)')

console.log('fan-out expand PASS: badge toggle, per-item cards keyed by index, pick, collapse, live stability, ⌘K-safe')
