// Node-side unit test for the desktop half's fan-out normaliser (fanItems).
// Extracts the pure functions from plugin.js (no React/SDK needed) and feeds them
// REAL run records produced by the engine test-suite (tests/home6/workflows/*).
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  if (i < 0) throw new Error(`no ${name}`)
  let depth = 0, j = src.indexOf('{', i)
  for (; j < src.length; j++) { if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break }
  return src.slice(i, j + 1)
}
const constGrab = name => {
  const i = src.indexOf(`const ${name} =`)
  const j = src.indexOf('\n\n', i)
  return src.slice(i, j)
}
const code = [grab('fanItems'), grab('itemLabel'), grab('renderGoal'), constGrab('fanCounts')].join('\n')
const { fanItems, fanCounts } = new Function(`${code}; return { fanItems, fanCounts }`)()

let fails = 0
const check = (label, cond, detail = '') => { console.log((cond ? 'PASS ' : 'FAIL ') + label + (cond ? '' : `  [${detail}]`)); if (!cond) fails++ }

const load = run => {
  const r = join(here, 'home6', 'workflows', run)
  const graph = JSON.parse(readFileSync(join(r, 'graph.json'), 'utf8'))
  const rec = JSON.parse(readFileSync(join(r, 'nodes', 'f.json'), 'utf8'))
  const events = readFileSync(join(r, 'events.jsonl'), 'utf8').trim().split('\n').map(l => JSON.parse(l))
  return { def: graph.nodes.find(n => n.id === 'f'), st: { status: rec.status, output: rec.output, error: rec.error }, events }
}

// 1. failed node (quorum miss) — all_results carries both items
{
  const { def, st, events } = load('pc2-mixed')
  const rows = fanItems(def, st, events)
  check('mixed: 2 rows', rows.length === 2, JSON.stringify(rows))
  check('mixed: item 0 failed with reason', rows[0].status === 'failed' && /rc=2/.test(rows[0].error), rows[0].error)
  check('mixed: item 0 carries tail', /segfault/.test(rows[0].tail || ''), rows[0].tail)
  check('mixed: item 1 done with output', rows[1].status === 'done' && rows[1].output?.result === 'ok', JSON.stringify(rows[1].output))
  check('mixed: labels from item goal', rows[0].label === 'CRASHME now' && rows[1].label === 'fine task', rows.map(r => r.label).join('|'))
  check('mixed: goal rendered per item', rows[1].goal === 'fine task', rows[1].goal)
  const c = fanCounts(rows)
  check('mixed: counts 1 done 1 failed', c.done === 1 && c.failed === 1 && c.total === 2, JSON.stringify(c))
}
// 2. quorum:1 node done — survivors + all_results
{
  const { def, st, events } = load('pc2-quorum')
  const rows = fanItems(def, st, events)
  check('quorum: node done still shows failed item', rows[0].status === 'failed' && rows[1].status === 'done')
}
// 3. LIVE: node running, only events so far (no committed record)
{
  const { def, events } = load('pc2-mixed')
  const rows = fanItems(def, { status: 'running', output: null }, events)
  check('live: rows from def items', rows.length === 2)
  check('live: finished item from event carries error', rows[0].status === 'failed' && /rc=2/.test(rows[0].error), rows[0].error)
  const rows2 = fanItems(def, { status: 'running', output: null }, [])
  check('live: no events yet => running placeholders', rows2.every(r => r.status === 'running'))
}
// 4. pre-0.7.2 shape: done node, merged bare outputs only
{
  const def = { id: 'f', fanout: { goal: 'probe {host}', items: [{ host: 'a' }, { host: 'b' }] } }
  const rows = fanItems(def, { status: 'done', output: { items: [{ r: 1 }, { r: 2 }], failed_items: 0 } }, [])
  check('legacy: 2 rows, both done', rows.length === 2 && rows.every(r => r.status === 'done'))
  check('legacy: output mapped by index', rows[1].output?.r === 2, JSON.stringify(rows[1]))
  check('legacy: goal template rendered', rows[0].goal === 'probe a', rows[0].goal)
  check('legacy: label from host', rows[1].label === 'b')
}
// 5. items_from (no def items) + pending
{
  const def = { id: 'f', fanout: { goal: 'x {item}', items_from: 'plan.result' } }
  const rows = fanItems(def, { status: 'pending' }, [])
  check('items_from pending: zero rows, no crash', Array.isArray(rows) && rows.length === 0)
}
// 6. v0.7.3: item.started present ⇒ started item running, unstarted item PENDING
{
  const def = { id: 'f', fanout: { goal: 'g {index}', items: [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }] } }
  const started = [0, 2].map(i => ({ node: 'f', event: 'item.started', index: i }))
  const rows = fanItems(def, { status: 'running', output: null }, started)
  check('starts: 4 rows', rows.length === 4, JSON.stringify(rows.map(r => r.status)))
  check('starts: started items running, rest pending',
    rows.map(r => r.status).join(',') === 'running,pending,running,pending',
    rows.map(r => r.status).join(','))
  const c = fanCounts(rows)
  check('starts: running count 2', c.running === 2 && c.total === 4, JSON.stringify(c))
}
// 7. v0.7.3: no item.started at all ⇒ old guess (running node ⇒ running items)
{
  const def = { id: 'f', fanout: { goal: 'g {index}', items: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] } }
  const rows = fanItems(def, { status: 'running', output: null }, [{ node: 'f', event: 'node.started' }])
  check('no-starts: running node ⇒ all running (legacy guess)', rows.every(r => r.status === 'running'),
    rows.map(r => r.status).join(','))
  const { def: mdef, events } = load('pc2-mixed')
  const noStarts = events.filter(e => e.event !== 'item.started' && !(e.event === 'item.finished' && e.index === 1))
  const rows2 = fanItems(mdef, { status: 'running', output: null }, noStarts)
  check('no-starts: item.finished wins, unstarted falls back to running (legacy guess)',
    rows2[0].status === 'failed' && rows2[1].status === 'running',
    rows2.map(r => r.status).join(','))
}
// 8. row.metrics folded from st.item_metrics (string AND numeric keys), missing ⇒ null
{
  const { def, events } = load('pc2-mixed')
  const mk = out => fanItems(def, { status: 'running', output: null, item_metrics: out }, events)
  const a = mk({ 0: { api_calls: 3, tokens_out: 120 }, 1: { api_calls: 1 } })
  check('metrics: string keys mapped to rows', a[0].metrics?.api_calls === 3 && a[1].metrics?.api_calls === 1,
    JSON.stringify(a.map(r => r.metrics)))
  const b = mk({ 1: { tool_calls: 4 } })
  check('metrics: missing index ⇒ null', b[0].metrics === null && b[1].metrics?.tool_calls === 4,
    JSON.stringify(b.map(r => r.metrics)))
  const c = mk({})
  check('metrics: no item_metrics ⇒ null rows, statuses intact',
    c.every(r => r.metrics === null) && c[0].status === 'failed' && c[1].status === 'done',
    JSON.stringify(c.map(r => [r.status, r.metrics])))
}
console.log(fails ? `\n${fails} FAILED` : '\nALL PASS')
process.exit(fails ? 1 : 0)
