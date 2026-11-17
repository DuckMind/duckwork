import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const ENTRY = path.join(here, '..', 'desktop', 'plugin.js')

/**
 * The app loads the entry uncompiled and may import only the plugin SDK, so the
 * tests evaluate the very same source with stubs instead of a bundle.
 */
async function loadPlugin(focusedUsage = {}) {
  const source = await readFile(ENTRY, 'utf8')
  const body = source
    .replace(/^import .*\n/gm, '')
    .replace('export default plugin', 'return plugin')

  let usage = null
  const host = { state: { focusedUsage } }
  const useValue = () => usage
  const jsx = (type, props) => (typeof type === 'function' ? type(props) : { type, props })
  const plugin = new Function('host', 'useValue', 'jsx', body)(host, useValue, jsx)

  const contributions = []
  plugin.register({ register: contribution => contributions.push(contribution) })

  return {
    contributions,
    setUsage: value => {
      usage = value
    },
    render: () => contributions[0].render()
  }
}

const digits = value => String(value).replace(/\D/g, '')

test('registers one right-aligned status bar item', async () => {
  const { contributions } = await loadPlugin()

  assert.equal(contributions.length, 1)
  assert.equal(contributions[0].area, 'statusBar.right')
  assert.equal(contributions[0].id, 'session-tokens')
  assert.equal(contributions[0].order, 135)
})

test('refuses to register on a build without focusedUsage, naming the field', async () => {
  // `null` — not `undefined`, which would just re-trigger the default parameter.
  await assert.rejects(loadPlugin(null), /host\.state\.focusedUsage[\s\S]*0\.20\.2/)
})

test('renders the compact total and the context share', async () => {
  const item = await loadPlugin()
  item.setUsage({ input: 1200000, output: 45678, total: 1245678, context_percent: 37 })

  const { props } = item.render()

  assert.equal(props.children, 'Σ 1.2M tok (37%)')
  assert.equal(props['aria-label'], props.title)
  assert.equal(props.className.includes('--ui-text-tertiary'), true)
})

test('spells the exact figures out in the tooltip', async () => {
  const item = await loadPlugin()
  item.setUsage({ input: 1234567, output: 45678, total: 1280245, context_percent: 37 })

  const lines = item.render().props.title.split('\n')

  assert.equal(lines.length, 4)
  assert.match(lines[0], /^input: /)
  assert.match(lines[1], /^output: /)
  assert.match(lines[2], /^total: /)
  assert.match(lines[3], /^context: 37%$/)
  // The numbers are grouped for reading, so compare digits, not separators.
  assert.equal(digits(lines[0]), '1234567')
  assert.equal(digits(lines[1]), '45678')
  assert.equal(digits(lines[2]), '1280245')
})

test('shows placeholders before the backend reports usage', async () => {
  const item = await loadPlugin()

  const { props } = item.render()

  assert.equal(props.children, 'Σ — tok')
  assert.equal(props.title, 'input: -\noutput: -\ntotal: -\ncontext: -')
})

test('renders a real zero rather than a placeholder', async () => {
  const item = await loadPlugin()
  item.setUsage({ input: 0, output: 0, total: 0, context_percent: 0 })

  assert.equal(item.render().props.children, 'Σ 0 tok (0%)')
})

test('writes the context share as a placeholder when it is absent', async () => {
  const item = await loadPlugin()
  item.setUsage({ input: 10, output: 5, total: 15 })

  const { props } = item.render()

  assert.equal(props.children, 'Σ 15 tok (-)')
  assert.match(props.title, /^context: -$/m)
})

test('falls back to the placeholder label when only input/output are reported', async () => {
  const item = await loadPlugin()
  item.setUsage({ input: 10, output: 5 })

  const { props } = item.render()

  // The label is driven by `total` alone; the tooltip still has the two figures.
  assert.equal(props.children, 'Σ — tok')
  assert.equal(digits(props.title.split('\n')[0]), '10')
  assert.equal(digits(props.title.split('\n')[1]), '5')
})
