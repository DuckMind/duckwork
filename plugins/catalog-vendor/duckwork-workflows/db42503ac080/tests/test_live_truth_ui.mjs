// Desktop read-path contract: only canonical status can animate/count a runner.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'desktop/plugin.js'), 'utf8')
const grab = name => {
  const i = src.indexOf(`function ${name}(`)
  assert.ok(i >= 0, name)
  let depth = 0, j = src.indexOf(') {', i) + 2
  for (; j < src.length; j++) if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break
  return src.slice(i, j + 1)
}
const isBusy = new Function(`${src.match(/const isBusy = [^\n]+/)[0]}; return isBusy`)()
assert.equal(isBusy('running'), true)
assert.equal(isBusy('held'), false, 'a held gate is not a running runner')
assert.equal(isBusy('interrupted'), false)
const runningCount = new Function('isBusy', `${src.match(/const runningCount = [^\n]+/)[0]}; return runningCount`)(isBusy)
assert.equal(runningCount({counts: {running: 3}, runs: [{status: 'held'}]}), 3, 'count all runs, not the recent page')
assert.equal(runningCount({runs: [{status: 'held'}, {status: 'interrupted'}, {status: 'running'}]}), 1)
assert.equal(runningCount({counts: {running: 0}, runs: [{status: 'running'}]}), 0)
assert.match(src, /WORKFLOWS · \$\{runningCount\(data\)\}/, 'the WORKFLOWS tab title is the sole live count (LiveChip deleted)')
assert.ok(!src.includes('statusBar.right'), 'the status-bar chip is gone — one live count, not two')

const fanItems = new Function(`${grab('fanItems')}\n${grab('itemLabel')}\n${grab('renderGoal')}; return fanItems`)()
const def = { id: 'a', fanout: { items: [1, 2], goal: 'x' } }
assert.deepEqual(fanItems(def, { status: 'pending' }, [{ node: 'a', event: 'item.started', index: 0 }]).map(x => x.status), ['pending', 'pending'])

const liveDef = { id: 'a', fanout: { items: ['current', 'orphan'], goal: 'x' } }
const starts = [0, 1].map(index => ({ node: 'a', index, event: 'item.started' }))
const verified = (item_metrics, events = starts, output = null) => fanItems(liveDef, { status: 'running', item_metrics, output }, events)
const stale = verified({ 0: { live: 1 }, 1: { live: 0, api_calls: 2 } })
assert.deepEqual(stale.map(r => r.status), ['running', 'pending'], 'stale start cannot borrow sibling liveness')
assert.deepEqual(verified({ 0: { live: 1 } }).map(r => r.status), ['running', 'pending'], 'missing metrics row is not live')
assert.deepEqual(verified({}).map(r => r.status), ['pending', 'pending'], 'empty authoritative metrics is not legacy')
const retry = verified({ 0: { live: 1 } }, [
  { node: 'a', index: 0, event: 'item.finished', status: 'failed' },
  { node: 'a', index: 0, event: 'item.started' }
])
assert.equal(retry[0].status, 'running', 'current verified live attempt beats old finish')
const committed = verified({ 0: { live: 1 }, 1: { live: 0 } }, starts,
  { all_results: [{ status: 'done', output: 'saved' }, { status: 'failed', error: 'saved error' }] })
assert.deepEqual(committed.map(r => r.status), ['done', 'failed'], 'committed terminal results survive metrics')
assert.equal(committed[0].output, 'saved')

// Run actual Timeline and ItemDetail render functions with tiny JSX stubs; no SDK/browser needed.
const jsx = (type, props) => ({ type, props })
const jsxs = jsx
const box = (_, ...children) => ({ type: 'box', props: { children } })
const { Timeline } = new Function('useValue', 'useTick', 'parseTime', 'jsx', 'jsxs', 'box', 'timelineTone', 'fmtDur', 'cn', '$selNode', '$fanItem',
  `${grab('Timeline')}; return { Timeline }`)(() => null, () => {}, x => Date.parse(x), jsx, jsxs, box,
  sp => sp.status === 'running' ? 'LIVE' : 'NOT-LIVE', () => '1s', (...xs) => xs.join(' '), {}, { set() {} })
const detail = { id: 'old', status: 'interrupted', nodes: { a: { status: 'pending' } }, events: [
  { event: 'run.started', ts: '2026-01-01T00:00:00Z' },
  { event: 'node.started', node: 'a', ts: '2026-01-01T00:00:01Z' }
] }
const walk = node => Array.isArray(node) ? node.flatMap(walk) : node && typeof node === 'object' ? [node, ...Object.values(node.props || {}).flatMap(walk)] : []
const { ItemDetail } = new Function('jsx', 'box', 'label', 'Dot', 'Badge', 'Vitals', 'fmtDur', 'fmtOutput', 'EDGE_TONE',
  `${grab('ItemDetail')}; return { ItemDetail }`)(jsx, box, x => x, 'Dot', 'Badge', 'Vitals', () => '1s', x => x, { failed: 'red' })
const vitals = row => walk(ItemDetail({ row })).filter(x => x.type === 'Vitals')
assert.equal(vitals(stale[0])[0].props.live, true, 'verified current item shows live indicator')
assert.equal(vitals(stale[1])[0].props.live, false, 'stale item keeps metrics without heartbeat')
assert.equal(vitals(retry[0])[0].props.live, true, 'retry live indicator follows current row')
const nodes = walk(Timeline({ detail }))
assert.ok(nodes.some(x => x.type === 'div' && x.props?.style?.background === 'NOT-LIVE'), 'stale open span must use canonical pending tone')
assert.ok(!nodes.some(x => String(x.props?.className || '').includes('animate-pulse')), 'stale span must not pulse')
console.log('desktop live-truth PASS')
