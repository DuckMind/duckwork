// Lane D (v11/D-desktop) — desktop law gates + F2/F4 behaviour, per RATIFY
// (Attack R5 + gate §5d).
//
//   1. Import baseline: PARSE the actual import statements of desktop/plugin.js
//      (regex over the ESM source, not a grep of quoted strings) and assert the
//      module sources are EXACTLY the frozen baseline
//      { '@duckwork/plugin-sdk', 'react', 'react/jsx-runtime' } — ZERO NEW.
//   2. SDK-only law: no window.duckworkDesktop / localStorage / document / eval /
//      dynamic import() calls in the code (comments excluded).
//   3. Solo snapshot equality: extract the ACTUAL NodeCard + NodePanel from
//      plugin.js and render them with tiny JSX stubs twice — once with the team
//      metadata (node def carries `profile`), once WITHOUT (no-team run). The
//      no-team trees must be structurally IDENTICAL to the 1.0.15 baseline
//      (the extracted source with the F2 badge lines stripped), proving a solo
//      user sees nothing new.
//   4. F2: the `as @<profile>` badge appears in NodeCard AND NodePanel ONLY when
//      def.profile is set, as plain text.
//   5. F4 precondition: the failed-node error string (`precondition unmet:
//      fix.pr_url`) already surfaces via the existing error paths — stacked
//      ItemCard title and the NodePanel error <pre> — and needs no new field.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// ---- 1. import baseline: PARSED, not grepped ---------------------------------
// Parse every static import statement the ESM file actually carries, including
// bare `import 'x'`, namespace/default/named forms, and `export ... from 'x'`.
const IMPORT_RE =
  /(?:^|[\s;])import\s+(?:[\w*{}\s,]+?\s*from\s*)?['"]([^'"]+)['"]/g
const REEXPORT_RE = /(?:^|[\s;])export\s+[\w*{}\s,]*?\s*from\s*['"]([^'"]+)['"]/g
const importSources = new Set()
for (const m of src.matchAll(IMPORT_RE)) importSources.add(m[1])
for (const m of src.matchAll(REEXPORT_RE)) importSources.add(m[1])
assert.ok(importSources.size >= 3, `parser found ${importSources.size} import sources — the file must carry at least the 3 baseline ones`)

const FROZEN_BASELINE = ['@duckwork/plugin-sdk', 'react', 'react/jsx-runtime']
const actual = [...importSources].sort()
assert.deepEqual(
  actual,
  [...FROZEN_BASELINE].sort(),
  `desktop imports are FROZEN to {${FROZEN_BASELINE.join(', ')}} — zero new. Parsed: ${JSON.stringify(actual)}`
)
// Sanity: the named imports the baseline carries really parsed (a regex that
// matched zero named forms would vacuously pass the set check above).
{
  const sdkNames = /import\s*\{([\s\S]*?)\}\s*from\s*['"]@duckwork\/plugin-sdk['"]/.exec(src)
  assert.ok(sdkNames && /atom/.test(sdkNames[1]) && /useQuery/.test(sdkNames[1]), 'plugin-sdk named imports parsed')
  const reactNames = /import\s*\{([^}]*)\}\s*from\s*['"]react['"]/.exec(src)
  assert.ok(reactNames && /useState/.test(reactNames[1]), 'react named imports parsed')
  const rtNames = /import\s*\{([^}]*)\}\s*from\s*['"]react\/jsx-runtime['"]/.exec(src)
  assert.ok(rtNames && /jsxs/.test(rtNames[1]), 'react/jsx-runtime named imports parsed')
}

// ---- 2. SDK-only law (comments stripped so law-explaining comments pass) ----
const codeOnly = src
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
for (const forbidden of ['window.duckworkDesktop', 'localStorage', 'document.', 'eval(']) {
  assert.ok(!codeOnly.includes(forbidden), `SDK-only law: no ${forbidden} in code (found in a string or call position)`)
}
assert.ok(!codeOnly.includes('new Function'), 'no runtime code generation (Function constructor)')
// Dynamic import(): an import( that is not preceded by `.` (import.meta).
assert.ok(!/(^|[^.\w])import\s*\(/.test(codeOnly), 'no dynamic import()')

// ---- extraction harness (same grab shape the ratified node_panel test uses) --
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  assert.ok(i >= 0, `plugin.js must define ${name}`)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
const constGrab = name => {
  const i = src.indexOf(`const ${name} =`)
  assert.ok(i >= 0, `plugin.js must define const ${name}`)
  const rest = src.slice(i + 1)
  const nx = Math.min(...['\nconst ', '\nfunction ', '\n\n'].map(p => { const j = rest.indexOf(p); return j < 0 ? rest.length : j }))
  return src.slice(i, i + 1 + nx)
}

// ---- component stubs (no React, no SDK) --------------------------------------
const jsx = (type, props) => ({ type, props })
const jsxs = jsx
const walk = node => Array.isArray(node)
  ? node.flatMap(walk)
  : node && typeof node === 'object' ? [node, ...Object.values(node.props || {}).flatMap(walk)] : []
const texts = node => walk(node).flatMap(n =>
  typeof n === 'string' ? [n] : typeof n.props?.children === 'string' ? [n.props.children] : [])
// React-semantic snapshot: null/undefined children render as NOTHING (React
// drops them), so equality of the RENDER means children arrays are compared
// after dropping nulls — the same tree the desktop app paints. Keys excluded
// (positionally assigned by the jsx() call sites, never user-visible).
const dropNulls = v => Array.isArray(v)
  ? v.map(dropNulls).filter(x => x !== null && x !== undefined)
  : v && typeof v === 'object'
    ? Object.fromEntries(Object.entries(v).filter(([k]) => k !== 'key').map(([k, x]) => [k, dropNulls(x)]))
    : v
const strip = t => JSON.stringify(dropNulls(t))

const EDGE_TONE = { done: 'D', running: 'R', held: 'H', failed: 'F', skipped: 'S', pending: 'P' }
// #48: NodeCard reads the ONE tone table; derive NODE_TONE from the same stub
// palette (same shim pattern as test_node_click_expand).
const NODE_TONE = Object.fromEntries(Object.entries(EDGE_TONE).map(([k, v]) => [k, {
  color: v, borderColor: v, shadow: null, shadowHover: null, pulseMs: null,
  calm: true, ui: 'muted', gate: null, breathe: null,
}]))
NODE_TONE.waiting = NODE_TONE.pending
const sharedConsts = [
  constGrab('EDGE_TONE'), constGrab('FACT_TONE'), constGrab('UNKNOWN'), constGrab('TAIL_BYTES'),
  constGrab('defaultTabFor'), constGrab('unk'), constGrab('factText'), constGrab('logBase'), constGrab('attemptNo'),
  constGrab('CARD_W'), constGrab('modelTag'),
  grab('fmtDur'), grab('fanItems'), grab('itemLabel'), grab('renderGoal'),
  constGrab('fanCounts'), constGrab('fanSummary'),
  grab('useNodeLogTail')
]

function makeNodeCard(srcCode) {
  return new Function(
    'useTick', 'box', 'label', 'Dot', 'Codicon', 'Vitals', 'GateActions', 'cn',
    'statusLabel', 'fmtDur', 'modelTag', 'fanItems', 'fanCounts', 'fanSummary',
    'CARD_W', 'Fragment', 'jsx', 'jsxs', 'NODE_TONE',
    srcCode + '; return NodeCard'
  )(
    () => {},
    (className, ...kids) => kids.length === 1 ? jsx('div', { className, children: kids[0] }) : jsxs('div', { className, children: kids }),
    text => jsx('div', { children: text }),
    'Dot', 'Codicon', 'Vitals', 'GateActions',
    (...parts) => parts.filter(Boolean).join(' '),
    s => s || 'unknown',
    ms => `${Math.round(ms / 1000)}s`,
    (d, t) => d.tier || (d.model ? String(d.model).split('/').pop() : ''),
    (def, st, events) => null, // fanItems: no fanout under test
    rows => ({ total: 0, terminal: 0, skipped: 0, stopped: 0, running: 0, failed: 0 }),
    c => '',
    168, 'Fragment', jsx, jsxs, NODE_TONE
  )
}

let queries = []
function makeNodePanel(srcCode) {
  return new Function(
    'useValue', 'useState', 'useTick', 'useQuery', 'api', 'ID_OK', 'Q', '$selNode', '$fanItem',
    'ItemChips', 'box', 'label', 'statusLabel', 'fmtOutput',
    'Dot', 'Badge', 'Button', 'Vitals', 'Fragment', 'jsx', 'jsxs',
    sharedConsts.join('\n') + '\n' + srcCode + '; return NodePanel'
  )(
    a => (a === $selNode ? $selNodeHolder.v : null),
    () => [panelTab, () => {}],
    () => {},
    cfg => { queries.push(cfg); return { data: cfg.enabled ? { content: 'TAIL' } : null, isPending: false } },
    async path => ({ content: 'TAIL', path }),
    /^[\w.-]+$/,
    ['wf'],
    $selNode, $fanItem,
    'ItemChips',
    (className, ...kids) => kids.length === 1 ? jsx('div', { className, children: kids[0] }) : jsxs('div', { className, children: kids }),
    text => jsx('div', { children: text }),
    s => s || 'unknown',
    o => (o == null ? '' : typeof o === 'string' ? o : JSON.stringify(o, null, 2)),
    'Dot', 'Badge', 'Button', 'Vitals', 'Fragment', jsx, jsxs
  )
}

// ---- the F2 badge lines, exactly as they appear in NodeCard / NodePanel -------
const CARD_BADGE = "def.profile ? jsx('span', { title: `as @${def.profile}`, children: `as @${def.profile}` }) : null,"
const PANEL_BADGE = "def.profile ? jsx('span', { title: `as @${def.profile}`, className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: `as @${def.profile}` }) : null,"
assert.ok(src.includes(CARD_BADGE), 'NodeCard carries the as-@-profile badge (F2)')
assert.ok(src.includes(PANEL_BADGE), 'NodePanel carries the as-@-profile badge (F2)')

const nodeCardSrc = grab('NodeCard')
const nodePanelSrc = grab('NodePanel')
// Baseline (the 1.0.15 bytes): same code with the badge lines removed.
const cardBaseline = nodeCardSrc.split(CARD_BADGE).join('')
const panelBaseline = nodePanelSrc.split(PANEL_BADGE).join('')
assert.ok(cardBaseline !== nodeCardSrc && panelBaseline !== nodePanelSrc)
assert.ok(cardBaseline.match(/\bnull\b/) !== null)

// ---- 3. solo snapshot equality + 4. profile badge ----------------------------
let $selNodeHolder = { v: null }
let $selNode = { get: () => $selNodeHolder.v, set() {} }
let $fanItem = { get: () => null, set() {} }
let panelTab = null

const detailFor = (def, shown) => ({ id: 'r1', status: shown.status, graph: { nodes: [def] }, nodes: { a: shown }, events: [] })
const selNode = { runId: 'r1', nodeId: 'a' }
const baseShown = { status: 'done', type: 'agent', output: { ok: true }, attempts: 1, ms: 1200, error_class: null, error: null }
const baseDef = extra => ({ id: 'a', type: 'agent', goal: 'do work', model: 'm', provider: 'p', reasoning: 'medium', after: [], ...extra })

// NodeCard solo: with the CURRENT code, a no-profile def must serialize exactly
// like the BASELINE code — byte-for-byte on the tree.
{
  const cur = makeNodeCard(nodeCardSrc)
  const base = makeNodeCard(cardBaseline)
  const t = cur({ runId: 'r1', def: baseDef({}), st: baseShown, gate: null, selected: false, owner: 'o', events: [] })
  const b = base({ runId: 'r1', def: baseDef({}), st: baseShown, gate: null, selected: false, owner: 'o', events: [] })
  assert.equal(strip(t), strip(b), 'solo NodeCard (no team metadata) renders IDENTICAL to the 1.0.15 baseline')
  const solo = texts(t).join('|')
  assert.ok(!/as @/.test(solo), 'no as-@ badge in a solo card')
}
{
  const cur = makeNodeCard(nodeCardSrc)
  const def = baseDef({ profile: 'demo-profile' })
  const t = cur({ runId: 'r1', def, st: baseShown, gate: null, selected: false, owner: 'o', events: [] })
  const solo = texts(t).join('|')
  assert.ok(solo.includes('as @demo-profile'), 'NodeCard shows `as @<profile>` when def.profile set')
  const badge = walk(t).find(n => typeof n.props?.children === 'string' && n.props.children === 'as @demo-profile')
  assert.ok(badge, 'badge is a single span element')
  assert.equal(badge.props.title, 'as @demo-profile', 'tooltip title = as @<profile>')
}

// NodePanel solo: same equality, no-team def under the CURRENT code vs BASELINE code.
{
  $selNodeHolder.v = selNode
  panelTab = null
  const cur = makeNodePanel(nodePanelSrc)
  queries = []
  const t = cur({ detail: detailFor(baseDef({}), baseShown) })
  $selNodeHolder.v = selNode
  const bp = makeNodePanel(panelBaseline)
  const b = bp({ detail: detailFor(baseDef({}), baseShown) })
  assert.equal(strip(t), strip(b), 'solo NodePanel (no team metadata) renders IDENTICAL to the 1.0.15 baseline')
  assert.ok(!/as @/.test(texts(t).join('|')), 'no as-@ badge in a solo panel')
}
{
  $selNodeHolder.v = selNode
  panelTab = null
  const cur = makeNodePanel(nodePanelSrc)
  const t = cur({ detail: detailFor(baseDef({ profile: 'incident-operator' }), baseShown) })
  const s = texts(t).join('|')
  assert.ok(s.includes('as @incident-operator'), 'NodePanel shows `as @<profile>` when def.profile set')
}

// ---- 5. F4: the precondition error string rides the EXISTING error paths -----
{
  // Stacked fan-out ItemCard: title already carries the row error (RATIFY:
  // tooltip shows the error string it already shows for failed nodes).
  assert.ok(/title:\s*row\.error\s*\|\|\s*row\.goal\s*\|\|\s*undefined/.test(src), 'ItemCard title = row.error (failed-node error string already surfaced)')
  // NodePanel left column: the error <pre> renders facts.error verbatim —
  // including `precondition unmet: fix.pr_url`. No new field is needed.
  assert.ok(/pre\('error',\s*facts\s*&&\s*facts\.error\s*!==\s*UNKNOWN\s*\?\s*facts\.error\s*:\s*shown\.error/.test(nodePanelSrc), 'NodePanel error pre reads facts.error/shown.error verbatim')
  $selNodeHolder.v = { runId: 'r1', nodeId: 'review' }
  panelTab = null
  const cur = makeNodePanel(nodePanelSrc)
  const def = { id: 'review', type: 'agent', goal: 'review', after: ['fix'], requires: { fix: ['pr_url'] } }
  const shown = {
    status: 'failed', type: 'agent', error_class: 'precondition',
    error: 'precondition unmet: fix.pr_url', output: { missing: ['fix.pr_url'] },
    attempts: 1, log_path: '/run/logs/review.a1.log'
  }
  const t = cur({ detail: { id: 'r1', status: 'failed', graph: { nodes: [def] }, nodes: { review: shown }, events: [] } })
  const s = texts(t).join('|')
  assert.ok(s.includes('precondition unmet: fix.pr_url'), 'failed-node tooltip shows the precondition error string')
  assert.ok(s.includes('precondition'), 'error_class renders')
}
// NodeCard gate: def.profile must never leak a fabricated badge for a falsy name.
{
  const cur = makeNodeCard(nodeCardSrc)
  for (const falsy of [undefined, null, '', false]) {
    const t = cur({ runId: 'r1', def: baseDef({ profile: falsy }), st: baseShown, gate: null, selected: false, owner: 'o', events: [] })
    assert.ok(!/as @/.test(texts(t).join('|')), `falsy profile ${JSON.stringify(falsy)} draws no badge`)
  }
}

console.log('ALL PASS: test_11_ui_imports — frozen import baseline (parsed), SDK-only law, solo snapshot equality, as-@profile badge, precondition error string')
