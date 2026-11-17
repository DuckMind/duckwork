// Pill rail expansion (#22 item 4): clicking a pill in the session strip opens
// a mini node-strip (the run's existing MiniGraph) ABOVE the rail; clicking the
// open pill again, pressing Esc, or switching the focused chat collapses it;
// clicking outside the rail collapses it. Open state is the in-memory
// $railOpen atom — never localStorage. toggleRail is the exported pure
// transition core; the render section drives the REAL SessionStrip against
// stubs and walks the produced tree: MiniGraph appears for the OPEN run only.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// -- 0. static laws --------------------------------------------------------------
// The rail's open state is an in-memory plugin atom (same law as $stripFold):
// a reload must never resurrect an expanded panel, and it never reaches
// localStorage.
assert.match(src, /const \$railOpen = atom\(null\)/,
  '$railOpen must be an in-memory atom(null) holding {sid, runId} — never localStorage')
assert.doesNotMatch(src, /localStorage\s*\.\s*(setItem|getItem|removeItem)/,
  'the desktop half never persists state to localStorage (comments may name it)')
assert.doesNotMatch(src, /\$[A-Za-z0-9_]+\.get\(\)/,
  'atoms are set/useValue only — a .get() call throws inside click handlers')

// -- 1. load the real module against stub SDK/react/jsx ---------------------------
const stubSdk = `
const created = []
export const atom = v => {
  let x = v
  const a = { get: () => x, set: n => { x = n } }
  created.push(a)
  return a
}
export const atom0 = atom
export const stubAtoms = created
export const Badge = 'Badge', Button = 'Button', cn = (...a) => a.filter(Boolean).join(' ')
export const Codicon = 'Codicon', EmptyState = 'EmptyState', ScrollArea = 'ScrollArea'
export const StatusDot = 'StatusDot', PanelListRow = 'PanelListRow', PanelPill = 'PanelPill'
export const PanelSectionLabel = 'PanelSectionLabel'
export const host = { state: { focusedSessionId: atom(''), focusedStoredSessionId: atom('') }, navigate: () => {}, notify: () => {} }
export const ROUTES_AREA = 'routes', PANES_AREA = 'panes', TRANSCRIPT_DIRECTIVE_AREA = 'transcript.directives'
export const COMPOSER_AREAS = { top: 'composer.top' }
export const Tip = 'Tip'
export const SIDEBAR_NAV_AREA = 'sidebar.nav', STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const useMutation = () => ({ isPending: false, mutate: () => {} })
export const useQueryClient = () => ({ invalidateQueries: () => {} })
export const useQuery = q => {
  const key = q && q.queryKey
  if (key && key[1] === 'run') { globalThis.__stubLastRunId = key[2]; return { data: globalThis.__stubDetail } }
  return { data: globalThis.__stubRuns ? { runs: globalThis.__stubRuns } : undefined }
}
export const useValue = a => {
  if (!a || typeof a.get !== 'function') return null
  if (globalThis.__stubOverrides && globalThis.__stubOverrides.has(a)) return globalThis.__stubOverrides.get(a)
  return a.get()
}
export const ctxRestStub = () => Promise.reject(new Error('no backend in test'))
`
const stubReact = `
export const useEffect = () => {}, useId = () => 't-0', useRef = () => ({ current: null }), useState = i => [typeof i === 'function' ? i() : i, () => {}]
export default { useEffect, useId, useRef, useState }
`
const stubJsx = `
export const jsx = (type, props, key) => ({ type, props: props || {}, key })
export const jsxs = jsx
export const Fragment = 'Fragment'
`
const tmp = mkdtempSync(join(tmpdir(), 'wf-railx-'))
const sdkPath = join(tmp, 'sdk-stub.mjs'); writeFileSync(sdkPath, stubSdk)
const reactPath = join(tmp, 'react-stub.mjs'); writeFileSync(reactPath, stubReact)
const jsxPath = join(tmp, 'jsx-stub.mjs'); writeFileSync(jsxPath, stubJsx)
const modPath = join(tmp, 'plugin-under-test.mjs')
writeFileSync(modPath, src
  .replaceAll("'@duckwork/plugin-sdk'", JSON.stringify(pathToFileURL(sdkPath).href))
  .replaceAll("'react'", JSON.stringify(pathToFileURL(reactPath).href))
  .replaceAll("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxPath).href)))
const mod = await import(pathToFileURL(modPath).href)
const sdkMod = await import(pathToFileURL(sdkPath).href)

// -- 2. toggleRail: the exported pure transition table ----------------------------
const { toggleRail, SessionStrip } = mod
assert.equal(typeof toggleRail, 'function', 'toggleRail is exported (pure, testable without a DOM)')
assert.deepEqual(toggleRail(null, 'S1', 'a'), { sid: 'S1', runId: 'a' }, 'null → open {sid, runId}')
assert.equal(toggleRail({ sid: 'S1', runId: 'a' }, 'S1', 'a'), null, 'clicking the OPEN pill collapses')
assert.deepEqual(toggleRail({ sid: 'S1', runId: 'a' }, 'S1', 'b'), { sid: 'S1', runId: 'b' }, 'clicking another pill switches')
assert.deepEqual(toggleRail({ sid: 'S1', runId: 'a' }, 'S2', 'a'), { sid: 'S2', runId: 'a' },
  'the same runId under a different sid opens fresh — never treated as the open pill')
// Esc / sid-change / click-away collapse are effects — locked at source (the
// click toggle itself is exercised behaviorally through the rendered pill).
// Esc is SCOPED (onKeyDown on the rail div): the ratified ⌘K law
// (test_fanout_expand.mjs) forbids global keydown listeners. A pill click
// leaves focus on the pill (F7: the label is tabIndex:0 — asserted in
// test_pill_rail §7b), so Escape bubbles through the rail handler. Anchor on
// the Escape handler itself (the pill label carries its own onKeyDown since
// F7, so "first onKeyDown" is no longer the rail's).
const escIdx = src.indexOf("e.key === 'Escape'")
assert.ok(escIdx >= 0, 'the rail installs a SCOPED onKeyDown handler for the Esc collapse')
const escBlock = src.slice(escIdx, escIdx + 200)
assert.ok(src.lastIndexOf('onKeyDown', escIdx) > src.lastIndexOf('\n', Math.max(0, escIdx - 120)),
  'the Escape check rides on an onKeyDown prop (scoped, not a global listener)')
assert.match(escBlock, /['"]Escape['"]/, "the keydown handler checks event.key === 'Escape'")
assert.match(escBlock, /\$railOpen\.set\(null\)/, 'Escape collapses the rail via $railOpen.set(null)')
assert.doesNotMatch(src, /addEventListener\(['"]keydown/,
  '⌘K law: no global keydown listeners anywhere in the plugin')
const clickIdx = src.indexOf("addEventListener('click'")
assert.ok(clickIdx >= 0, "the rail installs a document click listener for click-away collapse")
assert.match(src.slice(Math.max(0, clickIdx - 400), clickIdx + 400), /\$railOpen\.set\(null\)/,
  'a click outside the rail collapses it')
const stripBlock = src.slice(src.indexOf('export function SessionStrip'))
assert.match(stripBlock.slice(0, 5000), /useEffect\(\(\) => \{\s*\$railOpen\.set\(null\)\s*\}, \[pairKey\]\)/,
  'a focused-sid change (pairKey) collapses the rail via $railOpen.set(null)')

// -- 3. the REAL SessionStrip: MiniGraph for the OPEN run only --------------------
const mk = (id, status, sid, extra = {}) => ({
  id, name: id, status, owner: { session_id: sid },
  started: '2026-09-29T04:00:00Z', updated: '2026-09-29T04:05:00Z', ...extra
})
globalThis.__stubRuns = [
  mk('a', 'running', 'S1', { nodes_done: 3, nodes_total: 7 }),
  mk('b', 'held', 'S1', { held_gate: { id: 'g1', question: 'q', options: ['yes', 'no'] } }),
  mk('c', 'running', 'S2'),
]
const detailFor = id => ({
  id, name: id, status: id === 'b' ? 'held' : 'running', owner: { session_id: 'S1' },
  started: '2026-09-29T04:00:00Z', updated: '2026-09-29T04:05:00Z',
  graph: { nodes: [{ id: `${id}n1`, after: [] }, { id: `${id}n2`, after: [`${id}n1`] }] },
  nodes: { [`${id}n1`]: { status: 'done' }, [`${id}n2`]: { status: 'running' } }
})
globalThis.__stubDetail = detailFor('a')
globalThis.__stubOverrides = new Map()
sdkMod.host.state.focusedSessionId.set('S1')
sdkMod.host.state.focusedStoredSessionId.set('U1')

assert.equal(typeof SessionStrip, 'function', 'SessionStrip is exported for the composer registration')
// Walk the jsx tree RENDERING function components on the way down, collecting
// every node (including a function-type node itself, BEFORE its render) so
// MiniGraph — which only ever appears as a child produced at render time — is
// visible to the assertion below.
const walk = node => {
  const out = []
  const rec = n => {
    if (Array.isArray(n)) { n.forEach(rec); return }
    if (!n || typeof n !== 'object') return
    out.push(n)
    if (typeof n.type === 'function') { rec(n.type(n.props || {})); return }
    Object.values(n.props || {}).forEach(rec)
  }
  rec(node)
  return out
}
const hasMini = tree => walk(tree).some(n => typeof n.type === 'function' && n.type.name === 'MiniGraph')

// closed: the strip renders and shows NO MiniGraph
const closed = SessionStrip()
assert.ok(closed, 'strip renders for the focused chat that owns runs')
assert.ok(!hasMini(closed), 'collapsed rail shows no MiniGraph — the node-strip appears only on pill click')

// click probe: instrument every atom the module created; the pill click is the
// handler that SETS an atom to a {sid, runId} payload.
const atoms = sdkMod.stubAtoms
const sets = []
for (const a of atoms) {
  const orig = a.set.bind(a)
  a.set = v => { sets.push({ a, v }); return orig(v) }
}
const clickables = walk(closed).filter(n => typeof n.props?.onClick === 'function')
assert.ok(clickables.length >= 2, 'pills/actions render as clickables')
let railAtom = null, openPayload = null
for (const c of clickables) {
  sets.length = 0
  try { c.props.onClick({ stopPropagation: () => {} }) } catch { /* gate stubs */ }
  const hit = sets.find(s => s.v && typeof s.v === 'object' && 'sid' in s.v && 'runId' in s.v)
  if (hit) { railAtom = hit.a; openPayload = hit.v; break }
}
assert.ok(openPayload, 'a pill click sets the rail atom to {sid, runId} (opens the panel above the rail)')
assert.equal(openPayload.sid, 'S1', 'the open payload carries the focused sid')
assert.ok(['a', 'b'].includes(openPayload.runId), 'the open payload carries one of the pill runIds')

// re-render OPEN: the rail atom reports the payload → MiniGraph appears, and it
// is tied to the OPEN run through runQuery(runId).
globalThis.__stubOverrides.set(railAtom, openPayload)
globalThis.__stubDetail = detailFor(openPayload.runId)
const open = SessionStrip()
assert.ok(hasMini(open), 'expanded rail renders the run’s MiniGraph above the pills')
assert.equal(globalThis.__stubLastRunId, openPayload.runId,
  'the panel queries runQuery for the OPEN run only')

// switch pills: another {sid, runId} opens the OTHER run's strip.
const other = openPayload.runId === 'a' ? 'b' : 'a'
let switched = null
for (const c of clickables) {
  sets.length = 0
  try { c.props.onClick({ stopPropagation: () => {} }) } catch { /* gate stubs */ }
  const hit = sets.find(s => s.a === railAtom && s.v && s.v.runId === other)
  if (hit) { switched = hit.v; break }
}
assert.ok(switched, 'clicking the other pill switches the rail to that run')
globalThis.__stubOverrides.set(railAtom, switched)
globalThis.__stubDetail = detailFor(other)
assert.ok(hasMini(SessionStrip()), 'switched rail renders the newly open run’s MiniGraph')
assert.equal(globalThis.__stubLastRunId, other, 'the panel now queries the switched-to run')

// toggle closed: clicking the OPEN pill sets null. Handlers are re-walked from a
// FRESH render while the rail atom is open — with the open state riding as a
// PROP (F2), the toggle closes over the render's railOpen; handlers captured
// from the old closed render would carry railOpen=null and re-open, not close.
// Scoping (feat/run-tray, #22): the strip now also mounts the live-run tray,
// whose row buttons ('open ↗', '×') are clickables too — probes are scoped to
// the PillRail subtree so the rail contract never collides with tray actions.
const railNodes = walk(SessionStrip()).filter(n => typeof n.type === 'function' && n.type.name === 'PillRail')
assert.equal(railNodes.length, 1, 'the strip mounts exactly one PillRail')
const railClickables = walk(railNodes[0].type(railNodes[0].props)).filter(n => typeof n.props?.onClick === 'function')
assert.ok(railClickables.length >= 2, 'pills render as clickables inside the rail subtree')
let closedAgain = false
for (const c of railClickables) {
  sets.length = 0
  try { c.props.onClick({ stopPropagation: () => {} }) } catch { /* gate stubs */ }
  if (sets.some(s => s.a === railAtom && s.v === null)) { closedAgain = true; break }
}
assert.ok(closedAgain, 'clicking the OPEN pill sets the rail atom back to null')
globalThis.__stubOverrides.set(railAtom, null)
assert.ok(!hasMini(SessionStrip()), 'collapsed rail includes NO MiniGraph node — only the OPEN run gets one')

rmSync(tmp, { recursive: true, force: true })
console.log('ALL PASS test_pill_rail_expand (toggleRail table, $railOpen law, Esc+sid+click-away collapse wired, MiniGraph for the open run only)')
