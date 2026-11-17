// Pin test: agent-first pane model (owner directive 2026-10-03, desktop review).
// Law: the WORKFLOWS pane is a human EXPLORER's index, agent-forward. RUNNING
// rows on top (any owner — a human viewer has no "mine"; they never launch
// runs); The Rest descend by last action (updated). The pane NEVER renders
// "needs you" framing and never caps foreign runs. The originator is visible
// on every row: owner_profile (resolved bot name), owner.session_id fallback,
// 'cron' for a cron-shaped session, 'platform' for a platform run, 'unknown'
// when nothing rides — the last is never fabricated. Pure functions, no DOM.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')
// stub-SDK pattern of test_register_surface: the plugin imports the SDK/react.
const tmp = mkdtempSync(join(tmpdir(), 'wf-pane-'))
const jsxPath = join(tmp, 'jsx-stub.mjs')
writeFileSync(jsxPath, `
export const jsx = (type, props, key) => ({ type, props: props || {}, key })
export const jsxs = jsx
export const Fragment = 'Fragment'
`)
const reactPath = join(tmp, 'react-stub.mjs')
writeFileSync(reactPath, `
export const useEffect = () => {}, useId = () => 't-0', useRef = () => ({ current: null }), useState = i => [typeof i === 'function' ? i() : i, () => {}]
export default { useEffect, useId, useRef, useState }
`)
const sdkPath = join(tmp, 'sdk-stub.mjs')
writeFileSync(sdkPath, `
const atom = v => { let x = v; return { get: () => x, set: n => { x = n } } }
export { atom }
export const atom0 = atom
export const Badge = 'Badge', Button = 'Button', cn = (...a) => a.filter(Boolean).join(' ')
export const Codicon = 'Codicon', EmptyState = 'EmptyState', ScrollArea = 'ScrollArea'
export const StatusDot = 'StatusDot', PanelListRow = 'PanelListRow', PanelPill = 'PanelPill'
export const PanelSectionLabel = 'PanelSectionLabel'
export const host = { state: { focusedStoredSessionId: atom(''), focusedSessionId: atom('') }, navigate: () => {} }
export const useValue = a => (a && typeof a.get === 'function' ? a.get() : null)
export const useQuery = () => ({ data: undefined })
export const ROUTES_AREA = 'routes', PANES_AREA = 'panes', TRANSCRIPT_DIRECTIVE_AREA = 'transcript.directives'
export const COMPOSER_AREAS = { top: 'composer.top' }
export const useMutation = () => ({})
export const useQueryClient = () => ({})
`)
const modPath = join(tmp, 'plugin-under-test.mjs')
writeFileSync(modPath, src
  .replaceAll("'@duckwork/plugin-sdk'", JSON.stringify(pathToFileURL(sdkPath).href))
  .replaceAll("'react'", JSON.stringify(pathToFileURL(reactPath).href))
  .replaceAll("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxPath).href)))
const mod = await import(pathToFileURL(modPath).href)
const { paneModel, originLabel } = mod

const run = (id, status, updated, owner = null, extra = {}) =>
  ({ id, status, updated, owner, name: id, ...extra })

// originLabel: every source of truth, in priority order, never invented.
assert.equal(originLabel({ session_id: '20260101_000000_fa11e1' }, 'alpha-bot'), 'alpha-bot',
  'resolved profile wins')
assert.equal(originLabel({ session_id: '20260101_000000_fa11e1' }, null), '20260101_000000_fa11e1',
  'session id fallback')
assert.equal(originLabel({ session_id: 'cron_95bb2ef2ef4d_20261002_191640' }, null), 'cron',
  'cron-shaped session')
assert.equal(originLabel({ platform: 'discord' }, null), 'discord',
  'platform run')
assert.equal(originLabel(null, null), 'unknown', 'absent owner is never fabricated')

// paneModel: RUNNING first regardless of owner; everyone else by updated desc.
const now = Date.now()
const iso = min => new Date(now - min * 60000).toISOString()
const rows = [
  run('old-done', 'done', iso(5), { session_id: 's1' }),
  run('slow-run', 'running', iso(50), { session_id: 's2' }),
  run('fast-run', 'running', iso(1), { session_id: 's3' }),
  run('held-gate', 'held', iso(2), { session_id: 's1' }),
  run('husk', 'pending', iso(3), { session_id: 's1' }),
  run('dead', 'failed', iso(10), { session_id: 's4' })
]
const m = paneModel(rows, { 's1': 'beta-bot', 's3': 'alpha-bot' })
assert.deepEqual(m.running.map(r => r.id), ['fast-run', 'slow-run'], 'running on top, newest action first')
assert.deepEqual(m.rest.map(r => r.id), ['held-gate', 'old-done', 'dead'],
  'The Rest descend by last action — held/done/failed interleaved by updated, no queue framing')
assert.deepEqual(Object.fromEntries([...m.running, ...m.rest].map(r => [r.id, r.origin])),
  { 'fast-run': 'alpha-bot', 'slow-run': 's2', 'held-gate': 'beta-bot', 'old-done': 'beta-bot', 'dead': 's4' },
  'every row carries its resolved-or-fallback origin')
assert.equal(m.running.find(r => r.id === 'husk'), undefined, 'never-started husks stay unrendered')
assert.equal(m.rest.find(r => r.id === 'husk'), undefined, 'husks are absent from The Rest too')

// Absent profiles map entirely: every row falls back honestly, nothing thrown.
const bare = paneModel(rows, null)
assert.equal(bare.running.length, 2)
assert.equal(bare.running[0].origin, 's3', 'unknown profile -> raw session id')
assert.equal(bare.rest.find(r => r.id === 'held-gate').origin, 's1',
  'unresolved sessions fall back to the raw id, never a guess')

// Empty input is not a crash and not a lie.
const none = paneModel([], {})
assert.deepEqual([none.running.length, none.rest.length], [0, 0])
console.log('pane model pins: OK')
