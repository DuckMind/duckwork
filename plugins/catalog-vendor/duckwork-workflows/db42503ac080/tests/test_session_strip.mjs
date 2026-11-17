// L1 acceptance (O1 desktop): ownedRuns keeps only the focused chat's runs and
// returns [] for an empty key; splitRuns caps active at 3 (held first) with an
// overflow count and folds terminal runs to <=5; the pill model is collapsed by
// default and its collapsed line carries name/status/progress. Pure-model
// asserts only: there is no DOM under node --experimental-strip-types.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// -- load the real module against a stub SDK -----------------------------------
// Stub '@duckwork/plugin-sdk', 'react', and 'react/jsx-runtime' (no node_modules
// in this repo); everything else is the real module.
const stubSdk = `
const atom = v => { let x = v; return { get: () => x, set: n => { x = n } } }
export { atom }
export const atom0 = atom
export const Badge = 'Badge', Button = 'Button', cn = (...a) => a.filter(Boolean).join(' ')
export const Codicon = 'Codicon', EmptyState = 'EmptyState', ScrollArea = 'ScrollArea'
export const StatusDot = 'StatusDot', PanelListRow = 'PanelListRow', PanelPill = 'PanelPill'
export const PanelSectionLabel = 'PanelSectionLabel'
// The SDK exposes the focused-chat atoms ONLY under host.state (sdk/index.ts
// stubs them there; a top-level stub encoded bug #23 and kept the suite green
// while the strip never rendered).
export const host = { state: { focusedStoredSessionId: atom(''), focusedSessionId: atom('') }, navigate: () => {} }
export const q = { data: undefined }
export const useValue = a => (a && typeof a.get === 'function' ? a.get() : null)
export const useQuery = () => ({ data: q.data })
export const ROUTES_AREA = 'routes', PANES_AREA = 'panes', TRANSCRIPT_DIRECTIVE_AREA = 'transcript.directives'
export const COMPOSER_AREAS = { top: 'composer.top' }
export const Tip = 'Tip'
export const SIDEBAR_NAV_AREA = 'sidebar.nav', STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const useMutation = () => ({})
export const useQueryClient = () => ({})
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
const tmp = mkdtempSync(join(tmpdir(), 'wf-reg-'))
const sdkPath = join(tmp, 'sdk-stub.mjs')
writeFileSync(sdkPath, stubSdk)
const reactPath = join(tmp, 'react-stub.mjs')
writeFileSync(reactPath, stubReact)
const jsxPath = join(tmp, 'jsx-stub.mjs')
writeFileSync(jsxPath, stubJsx)
const modPath = join(tmp, 'plugin-under-test.mjs')
writeFileSync(modPath, src
  .replaceAll("'@duckwork/plugin-sdk'", JSON.stringify(pathToFileURL(sdkPath).href))
  .replaceAll("'react'", JSON.stringify(pathToFileURL(reactPath).href))
  .replaceAll("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxPath).href)))
const mod = await import(pathToFileURL(modPath).href)


const { ownedRuns, splitRuns, pillModel, SessionStrip } = mod
assert.equal(typeof SessionStrip, 'function', 'SessionStrip is exported for L3 to register in composer.top')

// -- 1. ownedRuns ---------------------------------------------------------------
const mk = (id, status, sid, started, updated, extra = {}) => ({ id, name: id, status, owner: { session_id: sid }, started, updated, ...extra })
const runs = [
  mk('a', 'running', 'S1', '2026-09-26T04:00:00Z', '2026-09-26T04:05:00Z', { nodes_done: 3, nodes_total: 6 }),
  mk('b', 'held',    'S1', '2026-09-26T04:01:00Z', '2026-09-26T04:06:00Z'),
  mk('c', 'running', 'S2', '2026-09-26T04:02:00Z', '2026-09-26T04:07:00Z'),
  mk('d', 'done',    'S1', '2026-09-26T03:00:00Z', '2026-09-26T03:30:00Z'),
  mk('e', 'failed',  'S1', '2026-09-26T03:10:00Z', '2026-09-26T03:40:00Z'),
  mk('f', 'running', '',   '2026-09-26T04:03:00Z', '2026-09-26T04:08:00Z'),   // cron launch, no owner
]
assert.deepEqual(ownedRuns(runs, '').map(r => r.id), [], 'empty sid owns nothing (cron launches show only in the pane)')
assert.deepEqual(ownedRuns(runs, 'S1').map(r => r.id).sort(), ['a', 'b', 'd', 'e'], 'only owner.session_id===sid')
assert.deepEqual(ownedRuns(runs, 'S2').map(r => r.id), ['c'])
assert.deepEqual(ownedRuns(null, 'S1'), [], 'null list is []')

// -- 2. splitRuns: held first, active<=3 + overflow, terminal fold<=5 ------------
const many = [
  mk('r1', 'running', 'S', '2026-09-26T04:00:00Z', '2026-09-26T04:00:00Z'),
  mk('r2', 'running', 'S', '2026-09-26T04:03:00Z', '2026-09-26T04:00:00Z'),
  mk('h1', 'held',    'S', '2026-09-26T03:50:00Z', '2026-09-26T04:00:00Z'),
  mk('r3', 'pending', 'S', '2026-09-26T04:02:00Z', '2026-09-26T04:00:00Z'),
  mk('r4', 'running', 'S', '2026-09-26T04:01:00Z', '2026-09-26T04:00:00Z'),
  ...['t1','t2','t3','t4','t5','t6','t7'].map((id, i) => mk(id, i % 2 ? 'done' : 'failed', 'S', '2026-09-26T02:00:00Z', `2026-09-26T03:0${i}:00Z`)),
]
const s = splitRuns(many)
assert.equal(s.active.length, 3, 'active capped at 3')
assert.equal(s.active[0].id, 'h1', 'held run sorts first')
assert.deepEqual(s.active.slice(1).map(r => r.id), ['r2', 'r3'], 'then running/pending by started desc')
assert.equal(s.overflow, 2, 'overflow counts the active runs beyond 3')
assert.equal(s.terminalFold.length, 5, 'terminal fold shows at most 5')
assert.equal(s.terminalFold[0].id, 't7', 'fold is most-recently-updated first')
assert.equal(s.terminalTotal, 7, 'fold reports the true terminal count')
const empty = splitRuns([])
assert.deepEqual([empty.active, empty.overflow, empty.terminalFold, empty.terminalTotal], [[], 0, [], 0])

// -- 3. pillModel: collapsed by default, one line ---------------------------------
const pm = pillModel(runs[0])
assert.equal(pm.expanded, false, 'pill renders collapsed by default')
assert.equal(typeof pm.collapsedLine, 'string')
assert.ok(pm.collapsedLine.includes('a'), 'collapsed line names the run')
assert.ok(!pm.collapsedLine.includes('\n'), 'collapsed line is one line')
const pmUnknown = pillModel({})
assert.ok(pmUnknown.collapsedLine.length > 0, 'an empty record still renders a line, never throws')

// -- 4. the whole-card navigate is gone: DirectiveBody has no role=link ----------
assert.ok(!/role:\s*'link'/.test(src.slice(src.indexOf('function DirectiveBody'), src.indexOf('function DirectiveBody') + 4000)),
  'DirectiveBody must not keep the whole-card role=link navigate (one click cannot both expand and navigate)')

// -- 5. KEY PAIRING lock (measured): owner.session_id is the runtime id, so it
// pairs with host.state.focusedSessionId ($focusedRuntimeId, sdk index.ts:668);
// owner.ui_session_id pairs with host.state.focusedStoredSessionId. A swapped pair
// renders nothing forever — assert the source wires them same-shape.
const stripSrc = src.slice(src.indexOf('export function SessionStrip'), src.indexOf('export function SessionStrip') + 1200)
assert.ok(/const runtimeSid = useValue\(focusAtom\(host\?\.state\?\.focusedSessionId\)\)/.test(stripSrc),
  'owner.session_id (runtime shape) must pair with host.state.focusedSessionId (feature-detected)')
assert.ok(/ownedRuns\(data\?\.runs \|\| \[\], runtimeSid \|\| ''\, storedSid \|\| ''\)/.test(stripSrc),
  'ownedRuns args must be (runtime, stored), never (stored, runtime)')

// -- 6. RED ON BASE (bug #23): the SDK exposes the focused-chat atoms ONLY under
// host.state (sdk/index.ts:665-697). With the stub atoms under host.state and an
// owning sid in host.state.focusedStoredSessionId, SessionStrip() must render a
// tree — on base it reads host.focusedSessionId, sees undefined, and returns null
// forever. And with a focused chat that owns no run it must return null.
const sdkMod = await import(pathToFileURL(sdkPath).href)
{
  const ownedByStored = [
    { id: 'u1', name: 'u1', status: 'running', owner: { session_id: '', ui_session_id: 'STORED-1' }, started: '2026-09-26T04:00:00Z', updated: '2026-09-26T04:05:00Z' },
    { id: 'u2', name: 'u2', status: 'done', owner: { session_id: 'OTHER' }, started: '2026-09-26T03:00:00Z', updated: '2026-09-26T03:30:00Z' },
  ]
  sdkMod.q.data = { runs: ownedByStored }
  sdkMod.host.state.focusedStoredSessionId.set('STORED-1')
  const tree = mod.SessionStrip()
  assert.ok(tree && typeof tree === 'object',
    'SessionStrip must render a tree when host.state.focusedStoredSessionId owns a run (was null on base — the atoms are only under host.state)')
  // null when the focused chat owns nothing
  sdkMod.host.state.focusedStoredSessionId.set('NOBODY')
  assert.equal(mod.SessionStrip(), null, 'no owned run -> null (honest absence)')
  // null when there is no focused chat at all
  sdkMod.host.state.focusedStoredSessionId.set('')
  assert.equal(mod.SessionStrip(), null, 'no focused sid -> null')
}

rmSync(tmp, { recursive: true, force: true })
console.log('ALL PASS test_session_strip (ownedRuns, splitRuns, pillModel, SessionStrip export, no whole-card link, host.state atoms render)')
