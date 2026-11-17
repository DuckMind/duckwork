import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const source = readFileSync(join(root, 'desktop/plugin.js'), 'utf8')
const match = source.match(/const inlineHeader = \(data, elapsed\) => \{[\s\S]*?\n\}/)
assert.ok(match, 'inline header helper exists')
const header = new Function('nodesCount', 'fmtDur', 'kfmt', 'usd', 'idleS', 'TERMINAL', `${match[0]}; return inlineHeader`)(
  r => `${r.nodes_done}/${r.nodes_total} terminal`, n => `${n}ms`, String, n => `$${n.toFixed(2)}`,
  m => m.last_activity == null ? null : 9, new Set(['done', 'failed', 'stopped'])
)
const [first, second] = header({ id: 'id', name: 'Sample', status: 'running', nodes_done: 2, nodes_total: 3,
  metrics: { tokens_in: 100, tokens_out: 12, api_calls: 4, tool_calls: 1, cost: 0.25, live: 1, last_activity: 1 } }, 3000)
assert.deepEqual(first, ['Sample', 'running', '2/3 terminal', '3000ms'])
assert.deepEqual(second, ['IN 100', 'OUT 12', 'API 4', 'TOOL 1', 'COST $0.25', 'LIVE 1', 'IDLE 9s'])
assert.deepEqual(header({ id: 'unknown', status: 'pending', nodes_done: 0, nodes_total: 1 }, null)[1], [])
assert.deepEqual(header({ id: 'unknown', status: 'running', nodes_done: 0, nodes_total: 1,
  metrics: { live: 1 } }, null)[1], ['LIVE 1'])
assert.match(source, /headerRows\[0\]\.map/)
assert.match(source, /headerRows\[1\]\.map/)
assert.match(source, /jsx\(MiniGraph, \{ detail: data \}\)/)
assert.match(source, /jsx\(FanStrip, \{ runId: data.id/)
console.log('ALL PASS: inline two-row header, labels, unknown metrics, retained interactions')
