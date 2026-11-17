// Live-run tray (#22, design contract on issue #22): the PillRail (the #28 sticky
// shape) is SUPERSEDED for live runs by a collapsible situational tray stacked
// as a sibling of the native task-list/subagents/queued-messages family at the
// SAME composer mount — SessionStrip stays the mount owner (register-surface
// test locks the 'session-strip' registration). This test drives the exported
// pure models with fake run ledgers, plus the REAL SessionStrip render against
// stubs (R6: fake ledgers, no behaviour-by-source-text; atom/state laws are
// asserted at source per the repo's established precedent).
//
// Contract (accepted design):
//  - collapsed = one thicker tray row: pulse glyph ⌬, aggregate label
//    `N runs · X building · Y held` (held segment amber, failed red),
//    micro node-sparkline, ▾.
//  - expanded = one row per live run owned by this session (owner.session_id),
//    INCLUDING dispatch/cron-shaped launches whose owner.session_id matches
//    the chat (closes the auto-cards half of #22); ordering held → building →
//    queued → finished (held pinned top); finished rows ack-away (× per row,
//    cap 10); row click accordion-expands MiniGraph; 'open ↗' escalates to the
//    pane. Click-away collapses; Esc collapses.
//  - zero live runs -> tray hidden; last completion shows
//    `last run done · n/n nodes` for 60 s then retracts.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// -- 0. static laws ---------------------------------------------------------------
// The tray's open state is an in-memory plugin atom (same law as $stripFold):
// a reload never resurrects an expanded tray, and state never hits localStorage.
assert.match(src, /const \$trayOpen = atom\(null\)/,
  '$trayOpen must be an in-memory atom(null) — never localStorage')
assert.doesNotMatch(src, /localStorage\s*\.\s*(setItem|getItem|removeItem)/,
  'the desktop half never persists state to localStorage (comments may name it)')
assert.doesNotMatch(src, /\$[A-Za-z0-9_]+\.get\(\)/,
  'atoms are set/useValue only — a .get() call throws inside click handlers')

// -- 1. load the real module against stub SDK/react/jsx ---------------------------
const stubSdk = `
export const atom = v => { let x = v; return { get: () => x, set: n => { x = n } } }
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
const tmp = mkdtempSync(join(tmpdir(), 'wf-tray-'))
const sdkPath = join(tmp, 'sdk-stub.mjs'); writeFileSync(sdkPath, stubSdk)
const reactPath = join(tmp, 'react-stub.mjs'); writeFileSync(reactPath, stubReact)
const jsxPath = join(tmp, 'jsx-stub.mjs'); writeFileSync(jsxPath, stubJsx)
const modPath = join(tmp, 'plugin-under-test.mjs')
writeFileSync(modPath, src
  .replaceAll("'@duckwork/plugin-sdk'", JSON.stringify(pathToFileURL(sdkPath).href))
  .replaceAll("'react'", JSON.stringify(pathToFileURL(reactPath).href))
  .replaceAll("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxPath).href)))
const mod = await import(pathToFileURL(modPath).href)

// -- helpers ----------------------------------------------------------------------
const mk = (id, status, sid, extra = {}) => ({
  id, name: id, status, owner: { session_id: sid },
  started: '2026-10-05T04:00:00Z', updated: '2026-10-05T04:05:00Z', ...extra
})
const textOf = node => {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string') return node
  if (Array.isArray(node)) return node.map(textOf).join(' ')
  if (typeof node.type === 'function') return textOf(node.type(node.props))
  return textOf(node.props?.children)
}
const findBy = (node, pred, out = []) => {
  if (node == null || typeof node === 'boolean' || typeof node === 'string') return out
  if (Array.isArray(node)) { node.forEach(n => findBy(n, pred, out)); return out }
  if (pred(node)) out.push(node)
  if (typeof node.type === 'function') { findBy(node.type(node.props), pred, out); return out }
  findBy(node.props?.children, pred, out)
  return out
}

const { trayModel, trayAggregateLabel, trayRecap, ackFinished, toggleTray, SessionStrip } = mod
assert.equal(typeof trayModel, 'function', 'trayModel is an exported pure model')
assert.equal(typeof trayAggregateLabel, 'function', 'trayAggregateLabel is exported')
assert.equal(typeof trayRecap, 'function', 'trayRecap is exported')
assert.equal(typeof ackFinished, 'function', 'ackFinished is exported')
assert.equal(typeof toggleTray, 'function', 'toggleTray is exported')

// -- 2. owner.session_id scoping, INCLUDING dispatch/cron-shaped launches ----------
{
  // The tray keys on the owner.session_id VALUE, not the launch surface: a
  // dispatch-launched run (and even a cron_-shaped session id) whose
  // owner.session_id matches the focused chat belongs in the tray — this is
  // the auto-cards half of #22. A run owned by a DIFFERENT session never
  // appears. The blank-session cron launch (owner.session_id '') stays
  // honest-absent, pane-only — the same law ownedRuns already enforces.
  const runs = [
    mk('chat-launched', 'running', 'S1'),
    mk('dispatch-launched', 'running', 'S1', { launched_by: 'dispatch' }),
    mk('cron-owned', 'running', 'cron_daily_report'),
    mk('other', 'running', 'S2'),
    mk('blank', 'running', ''),
  ]
  const scoped = mod.trayScoping(runs, 'S1', '', 'S1')
  assert.deepEqual(scoped.map(r => r.id).sort(),
    ['chat-launched', 'cron-owned', 'dispatch-launched'],
    'tray scoping keeps every run whose owner.session_id === sid (dispatch/cron-shaped launches join); other sessions and blank-owner runs never do')
}

// -- 3. ordering: held -> building -> queued -> finished (held pinned top) ---------
{
  const runs = [
    mk('q1', 'pending', 'S1', { started: '2026-10-05T04:04:00Z' }),
    mk('f1', 'done', 'S1', { updated: '2026-10-05T04:10:00Z' }),
    mk('b2', 'running', 'S1', { started: '2026-10-05T04:03:00Z' }),
    mk('h1', 'held', 'S1', { started: '2026-10-05T03:50:00Z', held_gate: { id: 'go', question: 'Ship?', options: ['ship', 'hold'] } }),
    mk('b1', 'running', 'S1', { started: '2026-10-05T04:01:00Z' }),
    mk('f2', 'failed', 'S1', { updated: '2026-10-05T04:12:00Z' }),
    mk('q2', 'pending', 'S1', { started: '2026-10-05T04:02:00Z' }),
  ]
  const m = trayModel(runs, [])
  assert.deepEqual(m.rows.map(r => r.id), ['h1', 'b2', 'b1', 'q1', 'q2', 'f2', 'f1'],
    'held pinned top, then building by started desc, then queued by started desc, then finished by updated desc')
  assert.deepEqual(m.rows.map(r => r.band), ['held', 'building', 'building', 'queued', 'queued', 'finished', 'finished'],
    'every row carries its band')
}

// -- 4. aggregate label -------------------------------------------------------------
{
  const runs = [
    mk('h1', 'held', 'S1'),
    mk('b1', 'running', 'S1'),
    mk('b2', 'running', 'S1'),
    mk('f1', 'failed', 'S1'),
  ]
  const label = trayAggregateLabel(runs, [])
  assert.equal(label.total, 4, 'aggregate counts every tray row (live + un-acked finished)')
  assert.equal(label.building, 2)
  assert.equal(label.held, 1)
  assert.equal(label.failed, 1)
  assert.ok(/4 runs · 2 building · 1 held/.test(label.line), `line is 'N runs · X building · Y held', got: ${label.line}`)
  // held tone is amber via the ONE tone table; failed red — the row reads
  // NODE_TONE entries, never a forked palette.
  const seg = k => (label.segments.find(s => s.key === k) || {}).color
  assert.equal(seg('held'), mod.NODE_TONE.held.color, 'held segment colour reads NODE_TONE.held (amber)')
  assert.equal(seg('failed'), mod.NODE_TONE.failed.color, 'failed segment colour reads NODE_TONE.failed (red)')
  assert.equal(trayAggregateLabel([], []).total, 0, 'empty ledger aggregates to 0, never throws')
}

// -- 5. ack-away: finished rows only, ledger caps at 10 -----------------------------
{
  const done = Array.from({ length: 13 }, (_, i) =>
    mk(`f${i}`, 'done', 'S1', { updated: `2026-10-05T05:${String(i).padStart(2, '0')}:00Z` }))
  assert.equal(trayModel(done, []).rows.length, 13, 'no acks -> every finished row is ledger')

  let acked = []
  for (const r of trayModel(done, acked).rows.filter(x => x.band === 'finished')) {
    acked = ackFinished(acked, r.id)
  }
  assert.equal(acked.length, 10, 'the ack-away ledger caps at 10 (the newest 10 acks)')
  assert.equal(acked[0], 'f12', 'the newest ack is kept')
  assert.equal(acked[9], 'f3', 'the 11th-newest ack was dropped by the cap')

  const m1 = trayModel(done, acked)
  assert.deepEqual(m1.rows.map(r => r.id), ['f2', 'f1', 'f0'], 'acked rows leave the tray; un-acked stay')
  // acking a LIVE run is a no-op on visibility — only finished rows ack away
  const live = [mk('b1', 'running', 'S1')]
  assert.deepEqual(trayModel(live, ackFinished(acked, 'b1')).rows.map(r => r.id), ['b1'],
    'acking a live run never hides it from the tray')
}

// -- 6. recap: `last run done · n/n nodes` for 60 s, then retracts ------------------
{
  const T = Date.parse('2026-10-05T06:00:00Z')
  const doneRuns = [mk('last', 'done', 'S1', { nodes_done: 4, nodes_total: 4, updated: '2026-10-05T05:59:30Z' })]
  const early = trayRecap(trayModel(doneRuns, []), T)
  assert.ok(early, 'inside the 60 s window the recap row shows')
  assert.ok(/^last run done · 4\/4 nodes$/.test(early.line), `recap line, got: ${early.line}`)
  const late = trayRecap(trayModel(doneRuns, []), T + 61_000)
  assert.equal(late, null, 'after 60 s the recap retracts (queued-messages parity)')
  assert.equal(trayRecap(trayModel([], []), T), null, 'no runs at all -> no recap')
  const liveNow = [mk('b1', 'running', 'S1'), doneRuns[0]]
  assert.equal(trayRecap(trayModel(liveNow, []), T), null, 'while anything is live the tray row itself shows, never a recap')
  const partial = [mk('p', 'failed', 'S1', { nodes_done: 2, nodes_total: 5, updated: '2026-10-05T05:59:59Z' })]
  const r2 = trayRecap(trayModel(partial, []), T)
  assert.ok(r2 && /· 2\/5 nodes$/.test(r2.line), 'recap speaks the last run\'s real counts, never fabricates n/n')
  const countsMissing = [mk('n', 'done', 'S1', { updated: '2026-10-05T05:59:59Z' })]
  const r3 = trayRecap(trayModel(countsMissing, []), T)
  assert.ok(r3 && r3.line.includes('?'), 'absent counts read ? — never 0/0')
}

// -- 7. toggleTray: the tray row + in-tray row accordion ---------------------------
{
  assert.deepEqual(toggleTray(null, 'a'), { expanded: true, openRun: null },
    'collapsed tray -> expanding the tray opens no single row')
  assert.deepEqual(toggleTray({ expanded: true, openRun: null }, 'a'), { expanded: true, openRun: 'a' },
    'open tray: row click accordion-opens that row')
  assert.deepEqual(toggleTray({ expanded: true, openRun: 'a' }, 'a'), { expanded: true, openRun: null },
    'clicking the OPEN row again closes just the row')
  assert.deepEqual(toggleTray({ expanded: true, openRun: 'a' }, 'b'), { expanded: true, openRun: 'b' },
    'another row switches')
}

// -- 8. the REAL SessionStrip: mount/hide rules -------------------------------------
{
  const sdkMod = await import(pathToFileURL(sdkPath).href)
  sdkMod.host.state.focusedSessionId.set('S1')
  sdkMod.host.state.focusedStoredSessionId.set('')

  // zero live runs -> tray hidden
  globalThis.__stubRuns = []
  globalThis.__stubOverrides = null
  assert.equal(SessionStrip(), null, 'zero runs -> tray hidden')

  // live runs -> collapsed tray row: pulse glyph + aggregate + chevron
  globalThis.__stubRuns = [
    mk('h1', 'held', 'S1', { started: '2026-10-05T03:50:00Z', held_gate: { id: 'go', question: 'Ship?', options: ['ship', 'hold'] } }),
    mk('b1', 'running', 'S1', { nodes_done: 2, nodes_total: 5 }),
    mk('d1', 'done', 'S1', { nodes_done: 3, nodes_total: 3, updated: '2026-10-05T04:04:50Z' }),
  ]
  const tree = SessionStrip()
  assert.ok(tree, 'live runs -> tray renders')
  const txt = textOf(tree)
  assert.ok(txt.includes('⌬'), 'collapsed row leads with the pulse glyph ⌬')
  assert.ok(/3 runs · 1 building · 1 held/.test(txt), 'collapsed row carries the aggregate label over live + finished rows')
  assert.ok(/▾|▴/.test(txt), 'collapsed row has the disclosure chevron')

  // expanded: one row per run, MiniGraph for the opened row only, gate release
  // reuses the existing GateActions surface, and the steer/stop buttons are
  // ABSENT (the plugin ships no steer/stop action surface today — graceful
  // degrade, recorded as a gap in the PR body, no new server endpoint).
  globalThis.__stubOverrides = new Map([[mod.$trayOpen, { expanded: true, openRun: 'b1' }]])
  globalThis.__stubDetail = { id: 'b1', name: 'b1', status: 'running', nodes: { a: { status: 'done' }, b: { status: 'running' }, c: { status: 'pending' } } }
  const open = SessionStrip()
  const openTxt = textOf(open)
  assert.ok(openTxt.includes('b1'), 'expanded tray names each run')
  assert.ok(openTxt.includes('2/5'), 'row shows node progress x/y')
  assert.ok(openTxt.includes('open ↗'), 'row offers the bigger-pane escalation')
  const mini = findBy(open, n => typeof n.type === 'function' && n.type.name === 'MiniGraph')
  assert.equal(mini.length, 1, 'exactly one accordion-opened row renders the shared MiniGraph')
  assert.equal(globalThis.__stubLastRunId, 'b1', 'MiniGraph is fed by the opened run only')
  const ga = findBy(open, n => typeof n.type === 'function' && n.type.name === 'GateActions')
  assert.equal(ga.length, 1, 'held row keeps the existing gate-release surface (no new server surface)')
  assert.ok(!/steer/.test(openTxt) && !/⏹/.test(openTxt),
    'steer/stop buttons are ABSENT — no such plugin surface exists today (degrade, do not invent one)')
  globalThis.__stubOverrides = null
}

// -- 9. visibility rule + collapse laws ('states at a glance' + item 4 parity) ----
{
  // Pure mount/hide rule: hidden at zero rows; visible while ANY row is live;
  // finished-only shows inside the 60 s recap window, hidden past it.
  const T = Date.parse('2026-10-05T06:00:00Z')
  const liveRuns = [mk('b1', 'running', 'S1')]
  const doneRuns = [mk('d1', 'done', 'S1', { nodes_done: 4, nodes_total: 4, updated: '2026-10-05T05:59:30Z' })]
  assert.equal(mod.trayShouldShow(trayModel([], []), T), false, 'zero rows -> tray hidden')
  assert.equal(mod.trayShouldShow(trayModel(liveRuns, []), T), true, 'live rows -> tray visible')
  assert.equal(mod.trayShouldShow(trayModel(doneRuns, []), T), true, 'the last completion keeps the row through the recap window')
  assert.equal(mod.trayShouldShow(trayModel(doneRuns, []), T + 61_000), false, '60 s after the last run ends the tray retracts')
  assert.equal(mod.trayShouldShow(trayModel(doneRuns, ['d1']), T), false, 'acking the recap run empties the ledger -> hidden immediately')
  // Scoping guards: no session -> nothing; the tray never leaks another chat's runs.
  assert.deepEqual(mod.trayScoping([mk('a', 'running', 'S1')], ''), [], 'no focused session -> no tray rows')
  assert.deepEqual(mod.trayScoping(null, 'S1'), [], 'null ledger is a clean empty, never a throw')
}
// Click-away / Esc collapse (scoped-listener laws, asserted at source per
// precedent): Esc collapses the tray FIRST ($trayOpen -> null), the rail
// panel only after; click-away excludes clicks inside the tray via trayRef
// (never a DOM-node listener, the window listener stays the plugin's ONE —
// test_tab_polish_48 locks the budget).
assert.match(src, /if \(e\.key === 'Escape'\)\s*\{\s*if \(trayExpanded\) \$trayOpen\.set\(null\)/,
  "Esc collapses the expanded tray to the collapsed-row state BEFORE the rail panel")
assert.match(src, /trayExpanded && trayRef\.current && trayRef\.current\.contains\(e\.target\)/,
  'click-away excludes clicks inside the open tray (trayRef contains check)')
assert.match(src, /window\.addEventListener\('click', onDocClick\)/,
  'click-away rides the single window-level listener (no DOM-node listeners)')

rmSync(tmp, { recursive: true, force: true })
console.log('ALL PASS test_run_tray (trayScoping, trayModel ordering/bands, aggregate label, ack cap 10, 60s recap, toggleTray, SessionStrip mount/hide, visibility rule, collapse laws)')
