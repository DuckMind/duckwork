// L3 acceptance: the registration surface is exactly {transcript.directives,
// routes, panes, one composer area}; the pane docks {pane:'sessions', pos:'center',
// enforce:true}; paneModel puts every RUNNING row on top and The Rest by
// last action (agent-first, owner 2026-10-03 — no NEEDS YOU framing);
// SMIL <animate> rides ONLY paths leaving running nodes; the MiniGraph ghost
// stack is gone (one FanStack — grep 'inset: 4px 0 0 4px' must be 0).
//
// The composer slot is FEATURE-DETECTED (issue #22 item 3): register() uses
// COMPOSER_AREAS.underside ?? COMPOSER_AREAS.top. `composer.underside` is the
// floating strip BELOW the composer dock (core >= v2026.7.30): bottom-anchored,
// grows upward over the thread, and is NOT inside the composer-fade div, so it
// does not dim when the thread scrolls up (composer/index.tsx:1558-1560).
// Older SDKs keep today's composer.top slot. This file loads the module
// against BOTH stub shapes and asserts each one's registered area set.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// -- load the real module against a stub SDK -----------------------------------
// Stub '@duckwork/plugin-sdk', 'react', and 'react/jsx-runtime' (no node_modules
// in this repo); everything else is the real module. The sdk stub is
// parameterized on COMPOSER_AREAS so the SAME module can be loaded against an
// underside-aware core and an older core; the stub also COUNTS useValue/useQuery
// calls for the hook-order assertion below.
const stubReact = `
export const useEffect = () => {}, useId = () => 't-0', useRef = () => ({ current: null }), useState = i => [typeof i === 'function' ? i() : i, () => {}]
export default { useEffect, useId, useRef, useState }
`
const stubJsx = `
export const jsx = (type, props, key) => ({ type, props: props || {}, key })
export const jsxs = jsx
export const Fragment = 'Fragment'
`
const sdkStub = composerAreas => `
const atom = v => { let x = v; return { get: () => x, set: n => { x = n } } }
export { atom }
export const atom0 = atom
export const hookCounts = { useValue: 0, useQuery: 0 }
export const Badge = 'Badge', Button = 'Button', cn = (...a) => a.filter(Boolean).join(' ')
export const Codicon = 'Codicon', EmptyState = 'EmptyState', ScrollArea = 'ScrollArea'
export const StatusDot = 'StatusDot', PanelListRow = 'PanelListRow', PanelPill = 'PanelPill'
export const PanelSectionLabel = 'PanelSectionLabel'
// The SDK exposes the focused-chat atoms ONLY under host.state (sdk/index.ts);
// a top-level stub encoded bug #23 and kept the suite green while the strip
// never rendered.
export const host = { state: { focusedStoredSessionId: atom(''), focusedSessionId: atom('') }, navigate: () => {} }
export const q = { data: undefined }
export const useValue = a => { hookCounts.useValue++; return (a && typeof a.get === 'function' ? a.get() : null) }
export const useQuery = () => { hookCounts.useQuery++; return { data: q.data } }
export const ROUTES_AREA = 'routes', PANES_AREA = 'panes', TRANSCRIPT_DIRECTIVE_AREA = 'transcript.directives'
export const COMPOSER_AREAS = ${JSON.stringify(composerAreas)}
export const useMutation = () => ({})
export const useQueryClient = () => ({})
export const ctxRestStub = () => Promise.reject(new Error('no backend in test'))
`

const tmp = mkdtempSync(join(tmpdir(), 'wf-reg-'))
const reactPath = join(tmp, 'react-stub.mjs')
writeFileSync(reactPath, stubReact)
const jsxPath = join(tmp, 'jsx-stub.mjs')
writeFileSync(jsxPath, stubJsx)

// Each load gets its own sdk-stub + plugin-under-test file (distinct URLs ⇒
// distinct module instances), so one process can test both SDK shapes.
async function loadPlugin(tag, composerAreas) {
  const sdkPath = join(tmp, `sdk-stub-${tag}.mjs`)
  writeFileSync(sdkPath, sdkStub(composerAreas))
  const modPath = join(tmp, `plugin-under-test-${tag}.mjs`)
  writeFileSync(modPath, src
    .replaceAll("'@duckwork/plugin-sdk'", JSON.stringify(pathToFileURL(sdkPath).href))
    .replaceAll("'react'", JSON.stringify(pathToFileURL(reactPath).href))
    .replaceAll("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxPath).href)))
  const mod = await import(pathToFileURL(modPath).href)
  const stub = await import(pathToFileURL(sdkPath).href)
  const regs = []
  const ctx = { register: r => regs.push(r), rest: () => Promise.reject(new Error('no backend')) }
  await mod.default.register(ctx)
  return { mod, stub, regs }
}

// A: older SDK — COMPOSER_AREAS has no underside → today's slot.
const A = await loadPlugin('top', { top: 'composer.top' })
// B: core >= v2026.7.30 — underside offered.
const B = await loadPlugin('underside', { top: 'composer.top', underside: 'composer.underside' })

const { mod, regs } = A
const areas = [...new Set(regs.map(r => r.area))].sort()
assert.deepEqual(areas, ['composer.top', 'panes', 'routes', 'transcript.directives'],
  `fallback SDK: areas registered must be exactly the four, got ${JSON.stringify(areas)}`)

// -- 1b. the underside-bearing SDK mounts the strip BELOW the composer dock -----
{
  const bAreas = [...new Set(B.regs.map(r => r.area))]
  assert.ok(bAreas.includes('composer.underside'),
    `core >= v2026.7.30: the strip must register in 'composer.underside' (the floating strip below the composer dock), got ${JSON.stringify(bAreas)}`)
  assert.ok(!bAreas.includes('composer.top'),
    `with underside offered the strip must NOT also sit in 'composer.top' (one mount, not two), got ${JSON.stringify(bAreas)}`)
  assert.deepEqual(bAreas.slice().sort(), ['composer.underside', 'panes', 'routes', 'transcript.directives'],
    `underside SDK: exactly one composer area — the underside — plus the other three, got ${JSON.stringify(bAreas.slice().sort())}`)
  const strip = B.regs.find(r => r.id === 'session-strip')
  assert.equal(strip.area, 'composer.underside', 'the session-strip registration itself moved, not some other registration')
}

// -- 1c. hook-order safety: SessionStrip returns null for an empty owned set,
// but ONLY after every hook ran (a conditional hook call after an early return
// would crash the app on the next render with a different branch).
{
  const before = { ...B.stub.hookCounts }
  const tree = B.mod.SessionStrip()
  assert.equal(tree, null, 'no focused chat / no owned runs renders nothing')
  assert.ok(B.stub.hookCounts.useQuery > before.useQuery,
    'useQuery must be called BEFORE the null return (hooks may never sit behind an early return)')
  assert.ok(B.stub.hookCounts.useValue > before.useValue,
    'useValue must be called BEFORE the null return (hooks may never sit behind an early return)')
}

// -- 1d. RED ON BASE (bug #23): SessionStrip must render when the FOCUSED chat
// owns a run. The atoms live under host.state (sdk/index.ts:665-697); base read
// host.focusedSessionId -> undefined -> null forever. Also lock the pane call
// site to the same keys.
const sdkMod = A.stub
{
  sdkMod.q.data = { runs: [{ id: 'u1', name: 'u1', status: 'running', owner: { session_id: '', ui_session_id: 'STORED-1' }, started: '2026-09-26T04:00:00Z', updated: '2026-09-26T04:05:00Z' }] }
  sdkMod.host.state.focusedStoredSessionId.set('STORED-1')
  assert.ok(mod.SessionStrip() && typeof mod.SessionStrip() === 'object',
    'SessionStrip must render a tree when host.state.focusedStoredSessionId owns a run')
  sdkMod.host.state.focusedStoredSessionId.set('NOBODY')
  assert.equal(mod.SessionStrip(), null, 'null when no run is owned by the focused chat')
  sdkMod.host.state.focusedStoredSessionId.set('')
}
{
  const i = src.indexOf('function WorkflowsPane()')
  assert.ok(i >= 0, 'WorkflowsPane exists')
  const paneSrc = src.slice(i, i + 800)
  assert.match(paneSrc, /host\?\.state\?\.focusedSessionId/, 'pane reads host.state.focusedSessionId')
  assert.match(paneSrc, /host\?\.state\?\.focusedStoredSessionId/, 'pane reads host.state.focusedStoredSessionId')
}

// -- 2. the pane docks center into the sessions strip, enforced -----------------
const pane = regs.find(r => r.area === 'panes')
assert.ok(pane, 'a panes registration exists')
assert.equal(pane.id, 'pane')
assert.deepEqual(pane.data.dock, { pane: 'sessions', pos: 'center', enforce: true },
  'pane dock must be the BOTS-pattern center dock')
assert.equal(pane.data.placement, 'left')
assert.equal(pane.data.width, '260px')
assert.equal(pane.data.collapsible, true)
assert.equal(pane.data.hideOnly, true)
assert.equal(typeof pane.data.tabTitle, 'function', 'tabTitle renders WORKFLOWS · n')
assert.equal(typeof pane.data.tabTitleText, 'function')
assert.equal(typeof pane.render, 'function')

// -- 3. paneModel (agent-first, owner 2026-10-03): RUNNING runner-backed only;
// pending husks are never rendered; everything else (held/done/failed/stopped/
// interrupted) is THE REST, descending by last action — one index, no queue
// framing. Origin label resolves or falls back, never fabricates. ----------
const mk = (id, status, updated) => ({ id, status, updated, owner: {} })
const runs = [
  mk('h1', 'held', 1), mk('f1', 'failed', 2), mk('i1', 'interrupted', 3),
  mk('r1', 'running', 4), mk('p1', 'pending', 5),
  mk('d1', 'done', 6), mk('s1', 'stopped', 7)
]
const g = mod.paneModel(runs, {})
assert.deepEqual(g.running.map(r => r.id), ['r1'], 'RUNNING is runner-backed only; pending husk excluded')
assert.deepEqual(g.rest.map(r => r.id), ['s1', 'd1', 'i1', 'f1', 'h1'],
  'The Rest = held+done+failed+stopped+interrupted together, updated desc — held is not a section')

// -- 4. SMIL candy: <animate> ONLY on paths leaving running nodes ----------------
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  if (i < 0) throw new Error(`missing function ${name}`)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
let instance = 0
const jsx = (type, props, key) => ({ type, props, key })
const { Edges, depthMap } = new Function('jsx', 'jsxs', 'useId',
  `const EDGE_TONE = { done:'teal', pending:'gray', failed:'red', running:'blue', held:'orange', skipped:'gray' };\nconst NODE_TONE = Object.fromEntries(Object.entries(EDGE_TONE).map(([k,v]) => [k, { color:v, borderColor:v, shadow:null, shadowHover:null, pulseMs:null, calm:true, ui:'muted', gate:null, breathe:null }]));\nNODE_TONE.waiting = NODE_TONE.pending;\n${['depthMap', 'edgePath', 'routeEdge', 'edgeFlowPolicy', 'edgeTone', 'nodeState', 'Edges'].map(n => { try { return grab(n) } catch { return '' } }).join('\n')}\nreturn { Edges, depthMap }`)(jsx, jsx, () => `t-${++instance}`)
const nodes = [
  { id: 'a' }, { id: 'b', after: ['a'] }, { id: 'c', after: ['a'] }, { id: 'd', after: ['b'] },
  { id: 'e', after: ['c'] }
]
function rectsFor(defs) {
  const depths = depthMap(defs), rects = {}, cols = []
  for (const n of defs) (cols[depths.get(n.id)] ||= []).push(n)
  let x = 20
  cols.forEach(col => {
    let y = 80
    for (const n of col) { rects[n.id] = { x, y, w: 168, h: 74 }; y += 102 }
    x += 280
  })
  return rects
}
{
  const states = { a: { status: 'running' }, b: { status: 'pending' }, c: { status: 'failed' }, d: { status: 'pending' } }
  const svg = Edges({ nodes, rects: rectsFor(nodes), states, gate: null })
  const paths = svg.props.children.filter(x => x && x.type === 'path' && x.props.d)
  assert.equal(paths.length, 4, 'every edge renders')
  for (const p of paths) {
    const from = p.key.split('->')[0]
    const kids = (Array.isArray(p.props.children) ? p.props.children : [p.props.children]).filter(Boolean)
    const anims = kids.filter(k => k && k.type === 'animate')
    if (states[from].status === 'running') {
      assert.equal(anims.length, 1, `${p.key}: running source gets exactly one <animate>`)
      assert.equal(anims[0].props.attributeName, 'stroke-dashoffset')
    } else {
      assert.equal(anims.length, 0, `${p.key}: non-running source gets NO <animate>`)
    }
  }
}
{
  // all-terminal graph: zero animate children anywhere.
  const states = Object.fromEntries(nodes.map(n => [n.id, { status: 'done' }]))
  const svg = Edges({ nodes, rects: rectsFor(nodes), states, gate: null })
  const paths = svg.props.children.filter(x => x && x.type === 'path' && x.props.d)
  for (const p of paths) {
    const kids = (Array.isArray(p.props.children) ? p.props.children : [p.props.children]).filter(Boolean)
    assert.equal(kids.filter(k => k && k.type === 'animate').length, 0, `${p.key}: done source is still`)
  }
}

// -- 5. one fan-stack: the MiniGraph ghost-outline stack is deleted --------------
assert.equal(src.split("inset: '4px 0 0 4px'").length - 1, 0,
  "grep -c \"inset: '4px 0 0 4px'\" desktop/plugin.js must be 0 (FanStack is the only stack)")
assert.match(src, /function FanStack\(/, 'FanStack exists')
assert.match(src, /jsx\(FanStack, \{ count: \(items \?\? 1\) \+ 1, pill: true/,
  'MiniGraph pills reuse FanStack in pill mode')

// -- 6. deletions actually landed -------------------------------------------------
assert.doesNotMatch(src, /SIDEBAR_NAV_AREA/, 'sidebar nav import gone')
assert.doesNotMatch(src, /statusBar\.right/, 'statusbar chip registration gone')
assert.doesNotMatch(src, /function LiveChip\(/, 'LiveChip deleted')
assert.doesNotMatch(src, /function RunRow\(/, 'RunRow deleted')
assert.doesNotMatch(src, /w-60 shrink-0 flex-col border-r/, 'page runs column deleted')
// one global live count only: runningCount reads exclusively for the tab title.
const rcCalls = src.match(/runningCount\(/g).length
const rcDefs = src.match(/const runningCount =/g).length
assert.equal(rcCalls + rcDefs, 2, 'runningCount: definition + tabTitle call only')

console.log('ALL PASS: register surface, dock, agent-first pane model, SMIL-only-on-running, one fan-stack')
