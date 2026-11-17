/**
 * Desktop-half harness: load desktop/plugin.js in a vm and drive it.
 *
 * Why: the Desktop app compiles plugin.js in its own runtime, so pytest can
 * never touch it. This runs the file the way it is shipped — ESM stripped down
 * to the same globalThis body the app uses, SDK stubbed — and then asserts the
 * two things that silently break in production: the registration shape, and
 * that render() actually runs and draws the plan.
 *
 *   node --test tests/desktop.test.mjs
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createContext, runInContext } from 'node:vm'

const SRC = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')

/** Load the plugin body with a stubbed SDK and return its registration + entries. */
function load({ queryData = null, queryError = null } = {}) {
  const calls = []
  const registered = []

  const body = SRC.replace(/^import\s*\{[\s\S]*?\}\s*from\s*'@duckwork\/plugin-sdk';?$/m, '')
    .replace(/^import\s*\{[\s\S]*?\}\s*from\s*'react\/jsx-runtime';?$/m, '')
    .replace(/^import\s*\{[\s\S]*?\}\s*from\s*'react';?$/m, '')
    .replace('export default {', 'globalThis.plugin = {')

  assert.ok(!body.includes("from '@duckwork/plugin-sdk'"), 'SDK import was not stripped')
  assert.ok(body.includes('globalThis.plugin = {'), 'default export was not rewritten')

  const refetch = []
  const sandbox = {
    console,
    ctx: { rest: (path, opts) => { calls.push({ path, opts }); return Promise.resolve(queryData) } },
    cn: (...parts) => parts.filter(Boolean).join(' '),
    host: { notify: () => {} },
    STATUSBAR_AREAS: { left: 'statusbar-left', center: 'statusbar-center', right: 'statusbar-right' },
    useQuery: (options) => {
      refetch.push(options.refetchInterval)
      return queryError
        ? { data: undefined, isError: true, error: queryError }
        : { data: queryData, isError: false, error: null }
    },
    useQueryClient: () => ({ invalidateQueries: () => {} }),
    useState: (initial) => [initial, () => {}],
    jsx: (type, props, key) => ({ type, props: props || {}, key }),
    jsxs: (type, props, key) => ({ type, props: props || {}, key }),
  }
  sandbox.globalThis = sandbox

  const context = createContext(sandbox)
  runInContext(body, context, { filename: 'desktop/plugin.js' })

  const plugin = sandbox.globalThis.plugin || sandbox.plugin
  assert.ok(plugin, 'plugin.js did not define a default export')
  plugin.register({
    register: (entry) => registered.push(entry),
    rest: sandbox.ctx.rest,
  })

  return { plugin, registered, calls, refetch }
}

/** Every string drawn anywhere in a rendered tree. */
function texts(node, out = []) {
  if (node == null || typeof node === 'boolean') return out
  if (typeof node === 'string' || typeof node === 'number') {
    out.push(String(node))
    return out
  }
  if (Array.isArray(node)) {
    node.forEach((child) => texts(child, out))
    return out
  }
  if (typeof node === 'object') {
    const props = node.props || {}
    texts(props.children, out)
    if (typeof node.type === 'function') texts(node.type(props), out)
  }
  return out
}

const PLAN = {
  plan: {
    id: 'plan_1',
    goal: 'Ship the catalog entry',
    status: 'active',
    updated_at: new Date().toISOString(),
    steps: [
      { id: 's01', title: 'write it', status: 'completed', notes: [] },
      { id: 's02', title: 'pin the sha', status: 'in_progress', notes: ['sha abc123'] },
      { id: 's03', title: 'open the PR', status: 'blocked', notes: [] },
      { id: 's04', title: 'tell Ritesh', status: 'not_started', notes: [] },
    ],
  },
  counts: { done: 1, total: 4, blocked: 1, in_progress: 1, not_started: 1 },
  current_step_id: 's02',
}

test('registers a right-rail pane and a status-bar chip', () => {
  const { plugin, registered } = load()
  assert.equal(plugin.id, 'handflow')
  const ids = registered.map((entry) => entry.id)
  assert.equal(new Set(ids).size, ids.length, `duplicate entry ids: ${ids}`)

  const pane = registered.find((entry) => entry.area === 'panes')
  assert.ok(pane, 'no pane registered')
  assert.equal(pane.data.placement, 'right')
  assert.match(pane.data.width, /^\d+px$/)
  assert.equal(typeof pane.render, 'function')

  const chip = registered.find((entry) => String(entry.area).startsWith('statusbar'))
  assert.ok(chip, 'no status-bar chip registered')
})

test('render() draws the empty state when nothing has been planned', () => {
  const { registered } = load({ queryData: null })
  const drawn = texts(registered[0].render()).join(' ')
  assert.match(drawn, /NO ACTIVE PLAN/)
})

test('render() draws the goal, every step, its mark and the counts', () => {
  const { registered } = load({ queryData: PLAN })
  const drawn = texts(registered[0].render()).join(' ')
  assert.match(drawn, /Ship the catalog entry/)
  for (const step of PLAN.plan.steps) {
    assert.ok(drawn.includes(step.title), `step missing from pane: ${step.title}`)
  }
  assert.ok(drawn.includes('[✓]') && drawn.includes('[→]') && drawn.includes('[!]') && drawn.includes('[ ]'))
  assert.ok(drawn.includes('1/4'), 'progress count missing')
  assert.match(drawn, /note: sha abc123/, 'current step note missing')
})

test('clicking a step mark POSTs the matching op and refetches', async () => {
  const { registered, calls } = load({ queryData: PLAN })
  const button = (function find(node) {
    if (!node || typeof node !== 'object') return null
    if (Array.isArray(node)) return node.map(find).find(Boolean) || null
    if (node.type === 'button' && node.props.title === 'complete') return node
    if (typeof node.type === 'function') return find(node.type(node.props))
    return find(node.props?.children)
  })(registered[0].render())
  assert.ok(button, 'no "complete" affordance rendered for the in-progress step')
  await button.props.onClick()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].path, '/plans/plan_1/steps/s02')
  // JSON round-trip: the object literal was built inside the vm realm, so
  // deepStrictEqual would fail on prototype identity rather than on content.
  assert.equal(JSON.stringify(calls[0].opts.body), '{"op":"complete"}')
  assert.equal(calls[0].opts.method, 'POST')
})

test('polls no faster than the SDK allows', () => {
  const { registered, refetch } = load({ queryData: PLAN })
  // texts() walks the tree, which is what actually invokes the components (and
  // therefore their useQuery calls) — including the chip.
  registered.forEach((entry) => texts(entry.render()))
  assert.ok(refetch.length >= 2, `expected the pane and the chip to poll, got ${refetch.length}`)
  for (const interval of refetch) {
    assert.ok(interval >= 3000, `refetchInterval ${interval}ms is faster than the 3s floor`)
  }
})

test('a backend error still renders (fails soft, no throw)', () => {
  const { registered } = load({ queryError: new Error('offline') })
  const drawn = texts(registered[0].render()).join(' ')
  assert.match(drawn, /unreachable/i)
  assert.match(texts(registered[1].render()).join(' '), /▤ —/)
})
