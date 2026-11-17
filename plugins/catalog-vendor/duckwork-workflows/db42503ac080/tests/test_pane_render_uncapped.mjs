// Render-level pin: THE REST renders EVERY foreign row (deep review #156, A4).
// paneModel has always been uncapped — the bug lived in the CONSUMER: the pane
// sliced to 10 and offered a "show all" fold, so a registered pane with 12
// foreign held/done rows rendered 10 + a button, contradicting the PR body and
// the paneModel doc-comment ("no caps on foreign runs"). Model-only pins could
// not see this; this harness mounts the ACTUAL pane component and walks the
// emitted tree. Law: every row appears as a PaneRow, the group label carries
// the full count, and no show-all affordance exists at any row count.
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const here = dirname(new URL(import.meta.url).pathname)
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// The pane reads data via useQuery(listQuery()); the stub answers with a fixed
// census: 2 running (foreign) + 12 done/held foreign rows — >10 is the point.
const now = Date.now()
const iso = min => new Date(now - min * 60000).toISOString()
const run = (id, status) => ({ id, status, updated: iso(3), name: id,
  owner: { session_id: `20260101_000000_${id}` } })
const FLEET = [
  run('run-a', 'running'), run('run-b', 'running'),
  ...Array.from({ length: 10 }, (_, i) => run(`done-${i}`, 'done')),
  ...Array.from({ length: 2 }, (_, i) => run(`held-${i}`, 'held'))
]

const tmp = mkdtempSync(join(tmpdir(), 'wf-render-'))
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
export const useQuery = () => ({ data: ${JSON.stringify({ runs: FLEET, counts: { total: 14, running: 2, held: 2, failed: 0 } })} })
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

const tree = mod.WorkflowsPane()
const walk = (node, fn) => {
  if (node == null) return
  if (Array.isArray(node)) return node.forEach(n => walk(n, fn))
  if (typeof node !== 'object') return
  fn(node)
  walk(node.props?.children, fn)
}
const rows = []
const labels = []
let showAll = 0
walk(tree, el => {
  const t = el.type
  if (typeof t === 'function' && t.name === 'PaneRow') rows.push(el)
  if (t === 'PanelSectionLabel') labels.push(String(el.props.children))
  if (t === 'Button' && /show all/i.test(String(el.props?.children))) showAll++
})

// The whole census renders: 2 RUNNING + 12 THE REST, nothing folded away.
assert.equal(rows.length, 14, `every row renders — saw ${rows.length}`)
assert.ok(labels.includes('RUNNING · 2'), `running group intact: ${labels}`)
assert.ok(labels.includes('THE REST · 12'), `rest group uncapped: ${labels}`)
assert.equal(showAll, 0, 'no show-all affordance may exist at any count')

// The row keys survive the render: the fold's key ('show-all') must not return,
// and every foreign id appears exactly once as a PaneRow key.
const keys = rows.map(r => r.key)
for (const r of FLEET) assert.equal(keys.filter(k => k === r.id).length, 1, `${r.id} exactly once`)
assert.ok(!keys.includes('show-all'), 'fold key is gone')

console.log('OK — pane renders all 12 foreign rows + 2 running, no cap, no fold')
