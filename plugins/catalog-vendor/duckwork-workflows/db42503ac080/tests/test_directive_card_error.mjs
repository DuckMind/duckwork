// Pin: the directive card must never degrade to dead text when a refetch
// fails with cached data, and the never-fetched error branch must be clickable
// (retry), not inert. Root cause of the flip-flop: `if (error)` ran BEFORE
// `if (!data)`, so any transient auth/transport blip evicted a good pill into
// `workflow ${id}` dead text — and the error span had no click affordance.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const plugin = readFileSync(join(here, '..', 'desktop', 'plugin.js'), 'utf8')

// Extract the real DirectiveBody by brace-matching (house pattern).
const MARKER = 'function DirectiveBody({ id }) {'
const start = plugin.indexOf(MARKER)
assert.notEqual(start, -1, 'DirectiveBody exists')
let depth = 0, end = start + MARKER.length - 1 // the body's opening brace
for (; end < plugin.length; end++) {
  if (plugin[end] === '{') depth++
  else if (plugin[end] === '}' && --depth === 0) { end++; break }
}
const src = plugin.slice(start, end)

function render(queryState) {
  const calls = []
  const jsx = (type, props) => ({ type, props })
  const invalidated = []
  const runQuery = () => queryState
  const fn = new Function(
    'jsx', 'jsxs', 'useQuery', 'useQueryClient', 'useValue', 'useTick', 'useState',
    'Dot', 'pillModel', 'host', '$selRun', 'Q', 'runQuery', '$fanOpen', '$fanItem',
    `${src}; return DirectiveBody`
  )(
    jsx,
    (type, props) => ({ type, props, many: true }),
    qfn => qfn,
    () => ({ invalidateQueries: q => invalidated.push(q) }),
    () => false,
    () => {},
    init => [typeof init === 'function' ? init() : init, () => {}],
    () => jsx('dot', {}),
    () => ({ collapsedLine: 'run · done · 2/2', tone: {} }),
    { navigate: () => {} },
    { set: () => {} },
    ['duckwork-workflows'],
    () => queryState,
    { get: () => false },
    { get: () => null }
  )
  const out = fn({ id: 'wf-1' })
  return { out, invalidated }
}

// 1) data present + error present -> the PILL renders (data wins), not dead text.
{
  const { out } = render({ data: { id: 'wf-1', status: 'done' }, error: new Error('401'), isFetching: true })
  assert.notEqual(out.props.children?.toString?.(), undefined)
  const text = JSON.stringify(out)
  assert.ok(!text.includes('workflow…'), 'cached data must not render the loading branch')
  assert.ok(!/"workflow \(wf-1\)"/.test(text), 'cached data must not render the error dead-text branch')
  assert.ok(text.includes('run · done · 2/2'), 'pill collapsed line renders despite the refetch error')
}

// 2) no data ever + error -> clickable RETRY button carrying the id.
{
  const { out, invalidated } = render({ data: undefined, error: new Error('401'), isFetching: false })
  assert.equal(out.type, 'button', 'error branch must be a button, never inert chrome')
  assert.match(String(out.props.children), /wf-1/, 'error branch keeps the id visible')
  out.props.onClick({})
  assert.equal(invalidated.length, 1, 'click invalidates the run query (retry)')
  assert.deepEqual(invalidated[0].queryKey, ['duckwork-workflows', 'run', 'wf-1'])
}

// 3) no data, no error -> quiet loading span (unchanged).
{
  const { out } = render({ data: undefined, error: null, isFetching: false })
  assert.equal(out.type, 'span')
  assert.equal(out.props.children, 'workflow…')
}

// 4) error branch while retrying shows the loading label inside the button.
{
  const { out } = render({ data: undefined, error: new Error('401'), isFetching: true })
  assert.equal(out.type, 'button')
  assert.equal(out.props.children, 'workflow…')
}

console.log('ALL PASS: directive card — data wins over error, error branch retries')
