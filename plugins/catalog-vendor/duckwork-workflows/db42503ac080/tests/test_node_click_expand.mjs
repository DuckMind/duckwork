// Non-stack node cards must open the NodePanel on click (owner report, 09-27:
// "non-stack nodes expand on click" — fan-stacks did, plain cards didn't).
// Root cause was NodeCard's toggle reading $selNode.get(): the SDK atom is
// set/useValue only, so the handler threw before .set() and the click died
// silently. Every working click path (ItemCard, item chips, timeline rows)
// uses bare .set(). This test renders the REAL NodeCard, clicks the head
// button, and asserts the exact $selNode payload — both directions.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// -- 0. static law: no atom reads via .get() anywhere in the desktop half -------
// (ItemCard/chips/rows all prove .set() is the only surface that works.)
assert.doesNotMatch(src, /\$[A-Za-z0-9_]+\.get\(\)/,
  'atoms are set/useValue only — a .get() call throws inside click handlers')
assert.match(src, /selected: sel\?\.runId === detail\.id && sel\?\.nodeId === def\.id/,
  'GraphView passes `selected` so NodeCard needs no atom read to toggle')

// -- 1. render the REAL NodeCard against strict stubs ---------------------------
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
  const rest = src.slice(i + 1)
  const nx = Math.min(...['\nconst ', '\nfunction ', '\n\n'].map(p => { const j = rest.indexOf(p); return j < 0 ? rest.length : j }))
  return src.slice(i, i + 1 + nx)
}

const jsx = (type, props, key) => ({ type, props: props || {}, key })
const jsxs = jsx
const box = (className, ...kids) => jsx('div', { className, children: kids.length === 1 ? kids[0] : kids })
const walk = node => Array.isArray(node) ? node.flatMap(walk)
  : node && typeof node === 'object'
    ? typeof node.type === 'function' ? walk(node.type(node.props || {}))
      : [node, ...Object.values(node.props || {}).flatMap(walk)]
    : []

// Local strict atom: records every set; there is NO get (real-SDK shape).
const sets = []
const $selNode = { set: v => sets.push(v) }

const fanItemsFn = new Function(`${grab('fanItems')}\n${grab('itemLabel')}\n${grab('renderGoal')}\n${constGrab('fanCounts')}; return { fanItems, fanCounts }`)()
const realFanSummary = new Function(`${constGrab('fanCounts')}\n${constGrab('fanSummary')}; return fanSummary`)()
const realModelTag = new Function(`${constGrab('modelTag')}; return modelTag`)()

// Instantiate the real NodeCard with the real helpers.
const { NodeCard: RealNodeCard } = new Function(
  'jsx', 'jsxs', 'box', 'cn', 'Dot', 'Codicon', 'Vitals', 'GateActions', 'useTick',
  'fanItems', 'fanCounts', 'fanSummary', 'modelTag', 'statusLabel', 'fmtDur',
  '$selNode', 'CARD_W', 'NODE_TONE',
  `${grab('NodeCard')}\nreturn { NodeCard }`
)(jsx, jsxs, box, (...a) => a.filter(Boolean).join(' '), 'Dot', 'Codicon', 'Vitals', 'GateActions', () => {},
   fanItemsFn.fanItems, fanItemsFn.fanCounts, realFanSummary, realModelTag, s => s || 'unknown',
   ms => (ms ? `${Math.round(ms / 1000)}s` : ''), $selNode, 168,
   Object.fromEntries(['pending', 'running', 'held', 'done', 'failed', 'stopped', 'skipped'].map(s =>
     [s, { color: s, borderColor: s, shadow: s === 'running' ? 'glow' : null, shadowHover: null,
           pulseMs: s === 'running' ? 900 : null, calm: s === 'done' || s === 'failed' || s === 'stopped',
           ui: 'muted', gate: null, breathe: null }])))

const def = { id: 'plain', after: [] }
const headButton = props => {
  const btn = walk(RealNodeCard(props)).find(n => n.type === 'button' && typeof n.props.onClick === 'function')
  assert.ok(btn, 'plain (non-stack) node card renders a clickable head button')
  return btn
}

// click on a non-selected plain node → selection opens with the exact payload
sets.length = 0
headButton({ runId: 'r', def, st: { status: 'done' }, gate: null, selected: false, owner: {}, events: [] })
  .props.onClick()
assert.deepEqual(sets, [{ runId: 'r', nodeId: 'plain' }],
  `first click selects the node, got ${JSON.stringify(sets)}`)

// re-click while selected → toggles closed (toggle from the prop, not an atom read)
sets.length = 0
headButton({ runId: 'r', def, st: { status: 'done' }, gate: null, selected: true, owner: {}, events: [] })
  .props.onClick()
assert.deepEqual(sets, [null],
  `second click clears the selection, got ${JSON.stringify(sets)}`)

// -- 2. the fan-stack path keeps working: its card body toggles the same way ----
const fanDef = { id: 'fan', after: [], fanout: { goal: 'g {index}', items: [{ id: 'a' }, { id: 'b' }] } }
sets.length = 0
headButton({ runId: 'r', def: fanDef, st: { status: 'done', output: null }, gate: null, selected: false, owner: {}, events: [] })
  .props.onClick()
assert.deepEqual(sets, [{ runId: 'r', nodeId: 'fan' }],
  `fan card body click selects too, got ${JSON.stringify(sets)}`)

console.log('ALL PASS: non-stack node click opens the panel (no atom .get, toggle from prop)')
