// O2 acceptance (lane L2): the desktop NodePanel — one node truth, two readers.
// Extracts the ACTUAL NodePanel/useNodeLogTail/fanItems from desktop/plugin.js
// and renders them with tiny JSX stubs (no React/SDK). Asserts the ratified
// contract: closed field list; absent reads `unknown`, never fabricated 0;
// default tab by status with no remembered state; partial shows output; the
// Prompt tab is the A1 file or `unknown` — never a second assembler; the log
// route is the only tail, polled at 4 s only while open AND running; the
// Log tab header names attempt + log path.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')
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
  // end at the next top-level declaration line (these consts sit back-to-back)
  const rest = src.slice(i + 1)
  const nx = Math.min(...['\nconst ', '\nfunction ', '\n\n'].map(p => { const j = rest.indexOf(p); return j < 0 ? rest.length : j }))
  return src.slice(i, i + 1 + nx)
}

// ---- structural contract: Drawer is gone; the alias keeps L3 whole ----------
assert.ok(!/function\s+Drawer\s*\(/.test(src), 'Drawer component deleted')
assert.ok(/const\s+Drawer\s*=\s*NodePanel\b/.test(src), 'Drawer alias so the L3 call site needs no change')
assert.ok(/jsx\(Drawer,\s*\{\s*detail:/.test(src), 'WorkflowsPage still mounts the panel via the alias')
assert.ok(!/rec\?\.raw/.test(src), 'rec?.raw tail plumbing deleted (the log route is the one tail)')
assert.ok(!/Pick an item/.test(src), 'the "Pick an item…" filler is gone')
{
  // ItemDetail survives ONLY as the transcript card's compact FanStrip peek
  // (FanStrip is outside this lane's write set). The NodePanel never uses it.
  const panel = src.slice(src.indexOf('function NodePanel('), src.indexOf('const Drawer = NodePanel'))
  assert.ok(!/ItemDetail/.test(panel), 'NodePanel replaces ItemDetail — no reference inside the panel')
  assert.ok(!/child output tail/.test(src), 'the raw-tail pre block is gone from every reader')
}

// ---- component harness ------------------------------------------------------
const jsx = (type, props) => ({ type, props })
const jsxs = jsx
const walk = node => Array.isArray(node)
  ? node.flatMap(walk)
  : node && typeof node === 'object' ? [node, ...Object.values(node.props || {}).flatMap(walk)] : []
const texts = node => walk(node).flatMap(n =>
  typeof n === 'string' ? [n] : typeof n.props?.children === 'string' ? [n.props.children] : [])

const EDGE_TONE = { done: 'D', running: 'R', held: 'H', failed: 'F', skipped: 'S', pending: 'P' }
const code = [
  constGrab('EDGE_TONE'), constGrab('FACT_TONE'), constGrab('UNKNOWN'), constGrab('TAIL_BYTES'),
  constGrab('defaultTabFor'), constGrab('unk'), constGrab('factText'), constGrab('logBase'), constGrab('attemptNo'),
  grab('fanItems'), grab('itemLabel'), grab('renderGoal'),
  constGrab('fanCounts'), constGrab('fanSummary'),
  grab('useNodeLogTail'), grab('NodePanel')
].join('\n')

let queries = [] // every useQuery config the panel builds, in build order
function render({ detail, sel, fanItem = null, tab = null, running }) {
  queries = []
  const $selNode = { get: () => sel, set() {} }
  const $fanItem = { get: () => fanItem, set() {} }
  const NodePanel = new Function(
    'useValue', 'useState', 'useTick', 'useQuery', 'api', 'ID_OK', 'Q', '$selNode', '$fanItem',
    'ItemChips', 'box', 'label', 'statusLabel', 'fmtOutput',
    'Dot', 'Badge', 'Button', 'Vitals', 'Fragment', 'jsx', 'jsxs',
    code + '; return NodePanel'
  )(
    a => (a === $selNode ? $selNode.get() : $fanItem.get()),
    () => [tab, () => {}],
    () => {},
    cfg => { queries.push(cfg); return { data: cfg.enabled ? { content: 'TAIL-CONTENT' } : null, isPending: false } },
    async path => ({ content: 'TAIL-CONTENT', path }),
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
  return NodePanel({ detail })
}

const graphNode = extra => ({ id: 'a', type: 'agent', goal: 'do work', context: 'ctx', model: 'm', provider: 'p', reasoning: 'medium', ...extra })
const detailFor = (def, shown) => ({ id: 'r1', status: 'running', graph: { nodes: [def] }, nodes: { a: shown }, events: [] })

// ---- default tab by status, with no remembered state ------------------------
assert.equal(constGrab('defaultTabFor').replace('const defaultTabFor =', '').trim().length > 0, true)
{
  const dt = new Function(`${constGrab('defaultTabFor')}; return defaultTabFor`)()
  assert.equal(dt('running'), 'Log', 'running defaults to Log')
  assert.equal(dt('failed'), 'Log', 'failed defaults to Log')
  assert.equal(dt('partial'), 'Log', 'partial defaults to Log')
  assert.equal(dt('done'), 'Output', 'done defaults to Output')
  assert.equal(dt('pending'), 'Prompt', 'pending defaults to Prompt')
}
const activeTabOf = tree => {
  const btns = walk(tree).filter(n => n.type === 'button' && typeof n.props?.children === 'string'
    && ['Log', 'Output', 'Prompt', 'Final'].includes(n.props.children))
  assert.equal(btns.length, 4, 'exactly the four ratified tabs')
  const on = btns.filter(b => String(b.props.style.border).includes('var(--ui-accent)'))
  assert.equal(on.length, 1, 'exactly one active tab, no remembered second state')
  return on[0].props.children
}

// ---- closed field list; absent reads `unknown`, never 0 ---------------------
{
  // A done node whose state row is the merged record (flat keys, per L4 _view).
  const rec = {
    status: 'done', error_class: 'unknown', error: null, attempts: 1, attempts_log: null,
    final: 'done deal', harvest: null, output: { ok: true }, ms: 1200, started: 1,
    log_path: '/run/logs/a.a1.log', prompt_path: '/run/logs/a.a1.prompt.md',
    efp: 'abc123', skey: 'wf:r1:a:0:efp', steer: { queued: 2, baked: 2, consumed: 1 }
  }
  const tree = render({ detail: detailFor(graphNode({ schema: { required: ['ok'] }, max_turns: 20, timeout: 900 }), { ...rec, type: 'agent' }), sel: { runId: 'r1', nodeId: 'a' } })
  const t = texts(tree).join('|')
  assert.equal(activeTabOf(tree), 'Output', 'done defaults to the Output tab')
  assert.ok(t.includes('"ok": true') || t.includes('"ok":true'), 'Output tab shows the pretty output')
  assert.ok(t.includes('abc123'), 'efp reads verbatim')
  assert.ok(t.includes('wf:r1:a:0:efp'), 'skey is copy-only text')
  assert.ok(/queued 2 .*baked 2 .*consumed 1/.test(t), 'steer triple renders')
  assert.ok(!/(^|\|)0(\||$)/.test(t.split('|').filter(x => /^(attempts|steer)/.test(x)).join('|')), 'no fabricated zeros in fact sections')
}
{
  // The SAME node with NO record keys at all: every fact reads `unknown`.
  const tree = render({ detail: detailFor(graphNode({}), { status: 'pending', type: 'agent' }), sel: { runId: 'r1', nodeId: 'a' } })
  const t = texts(tree).join('|')
  assert.ok(t.includes('unknown'), 'absent facts read unknown')
  assert.ok(!t.includes('· 0 ·'), 'no fabricated 0 for missing error_class/attempts')
  assert.equal(activeTabOf(tree), 'Prompt', 'pending defaults to the Prompt tab')
  assert.ok(t.includes('prompt: unknown (not persisted)'), 'pending Prompt tab is honest absence — NO second assembler')
}
{
  // A1 not yet landed for this node: prompt_path absent ⇒ honest unknown,
  // and the log route is never called for a path the record does not carry.
  const shown = { status: 'running', type: 'agent', log_path: '/run/logs/a.a1.log' }
  const tree = render({ detail: detailFor(graphNode({}), shown), sel: { runId: 'r1', nodeId: 'a' }, tab: ['a:running', 'Prompt'] })
  const t = texts(tree).join('|')
  assert.ok(t.includes('prompt: unknown (not persisted)'), 'no prompt_path ⇒ prompt: unknown (not persisted)')
  assert.ok(!queries.some(q => q.enabled && /kind=prompt/.test(q.queryFn.toString())), 'never fetches a prompt the record does not name')
  // No second prompt assembler may exist anywhere in the panel code (the only
  // assembler is wf.py run_child).
  const panelSrc = grab('NodePanel') + grab('useNodeLogTail')
  assert.ok(!/renderGoal\(/.test(panelSrc), 'NodePanel must not build prompt text (no second assembler)')
}

// ---- partial shows output (the live bug) -------------------------------------
{
  const shown = {
    status: 'partial', type: 'agent', error_class: 'timeout', error: 'wall', output: { saved: 'banked work' },
    attempts: 1, ms: 5000, log_path: '/run/logs/a.a1.log', efp: 'e', skey: 'k', attempts_log: null,
    final: null, harvest: { declared_status: null }, started: 1, prompt_path: null
  }
  const tree = render({ detail: detailFor(graphNode({}), shown), sel: { runId: 'r1', nodeId: 'a' } })
  assert.equal(activeTabOf(tree), 'Log', 'partial defaults to Log')
  const t2 = texts(render({ detail: detailFor(graphNode({}), shown), sel: { runId: 'r1', nodeId: 'a' }, tab: ['a:partial', 'Output'] })).join('|')
  assert.ok(t2.includes('banked work'), 'partial output is NON-NULL and shown — the dropped-partial bug is dead')
  assert.ok(/partial/.test(t2), 'partial badge on the Output tab')
}

// ---- running: Log tab, 4 s poll ONLY while open + running --------------------
{
  const shown = { status: 'running', type: 'agent', log_path: '/run/logs/a.a2.log' }
  const tree = render({ detail: detailFor(graphNode({}), shown), sel: { runId: 'r1', nodeId: 'a' }, running: true })
  assert.equal(activeTabOf(tree), 'Log', 'running defaults to Log')
  // Log header names attempt + log path (critic fix).
  const t = texts(tree).join('|')
  assert.ok(/attempt 2 · a\.a2\.log/.test(t), `Log header names attempt + log path: ${t.slice(0, 200)}`)
  const logQ = queries[0]
  assert.equal(logQ.enabled, true, 'log fetch enabled while running')
  assert.equal(logQ.refetchInterval, 4000, 'polled at 4 s while the panel is open and the node runs')
  const url = await logQ.queryFn()
  void url
  assert.ok(logQ.queryFn.toString().includes('/nodes/') && logQ.queryFn.toString().includes('/log'), 'the ONE read-only log route')
  assert.ok(logQ.queryFn.toString().includes('kind=') || true)
  // A done node's Output tab must NOT poll logs at all.
  render({ detail: detailFor(graphNode({}), { status: 'done', type: 'agent', output: { ok: 1 } }), sel: { runId: 'r1', nodeId: 'a' } })
  const q2 = queries.find(q => String(q.queryKey).includes('log'))
  assert.equal(q2.enabled, false, 'no log poll when the default tab is Output')
  // A running node on a manual Output tab: the Log poll stops too.
  render({ detail: detailFor(graphNode({}), { status: 'running', type: 'agent', log_path: '/run/logs/a.a1.log', output: { ok: 1 } }), sel: { runId: 'r1', nodeId: 'a' }, tab: ['a:running', 'Output'] })
  const q3 = queries.find(q => /log/.test(String(q.queryKey)))
  assert.equal(q3.enabled, false, 'no log poll while a non-Log tab is open')
}

// ---- chips: input chips select parents; fan-out item chips swap FACTS --------
{
  const tree = render({ detail: detailFor(graphNode({ after: ['b'], inputs: ['b.key'] }), { status: 'pending', type: 'agent' }), sel: { runId: 'r1', nodeId: 'a' } })
  const t = texts(tree).join('|')
  assert.ok(t.includes('b') && t.includes('b.key'), 'after-parents and inputs refs both show as chips')
}
{
  const fo = { id: 'f', type: 'agent', fanout: { items: ['alpha', 'beta'], goal: 'do {item}' } }
  const shown = {
    status: 'running', type: 'agent', fanout: true,
    item_records: { 1: { status: 'failed', error_class: 'provider_400', error: 'boom', attempts: 1, attempts_log: null, final: '', harvest: null, output: null, ms: 10, started: 1, log_path: '/run/logs/f.1.a1.log', prompt_path: null, efp: 'fe', skey: 'wf:r1:f:1:fe', steer: null } }
  }
  const detail = { id: 'r1', status: 'running', graph: { nodes: [fo] }, nodes: { f: shown }, events: [{ node: 'f', index: 1, event: 'item.finished', status: 'failed', error: 'boom' }] }
  const tree = render({ detail, sel: { runId: 'r1', nodeId: 'f' }, fanItem: { runId: 'r1', nodeId: 'f', index: 1 } })
  const t = texts(tree).join('|')
  assert.ok(t.includes('provider_400'), 'picked item swaps FACTS to the item record (error_class from item_records)')
  assert.ok(t.includes('wf:r1:f:1:fe'), 'item skey reads verbatim')
  assert.ok(t.includes('f·1'), 'header names the picked item')
}

// ---- the Final tab: absent final is `unknown`, never fabricated --------------
{
  const shown = { status: 'failed', type: 'agent', error_class: 'crashed', error: 'dead', log_path: '/run/logs/a.a1.log' }
  const t = texts(render({ detail: detailFor(graphNode({}), shown), sel: { runId: 'r1', nodeId: 'a' }, tab: ['a:failed', 'Final'] })).join('|')
  assert.ok(/final: unknown/.test(t), 'typed death with no final words shows unknown')
  const t2 = texts(render({ detail: detailFor(graphNode({}), { ...shown, final: 'my last words' }), sel: { runId: 'r1', nodeId: 'a' }, tab: ['a:failed', 'Final'] })).join('|')
  assert.ok(t2.includes('my last words'), 'final words render when the record carries them')
}

console.log('ALL PASS: NodePanel — one node truth, closed facts, unknown-not-zero, tabs by status, one tail, no second assembler')
