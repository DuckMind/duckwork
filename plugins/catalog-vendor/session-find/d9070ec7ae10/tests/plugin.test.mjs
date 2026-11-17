// Source and unit tests for the session-find desktop plugin.
//
// Run: node --test desktop-plugins/session-find/tests/plugin.test.mjs
//
// The plugin is loaded uncompiled by the desktop app, so nothing typechecks it and
// a build never sees it. These tests guard what a compiler would not:
//   - no jsx()/jsxs() call takes a third argument (that slot is the element key;
//     children put there are dropped without a word and the panel renders empty),
//   - no em dash and no emoji anywhere in the file,
//   - only the three specifiers the runtime loader resolves are imported,
//   - the keybind default does not collide with a built-in default,
//   - the pure helpers behind the chips, the keys and the rows behave.

import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
// Two layouts ship this file: the window beside the tests at the package root,
// and the published one, where the window sits in desktop/ so the app can
// materialise it. Find it either way rather than teaching the suite one shape.
const PLUGIN = [join(here, '..', 'plugin.js'), join(here, '..', 'desktop', 'plugin.js')].find(
  candidate => existsSync(candidate)
)

if (!PLUGIN) {
  throw new Error('no plugin.js beside the tests or in desktop/')
}

const source = readFileSync(PLUGIN, 'utf8')

const ALLOWED_IMPORTS = new Set(['@duckwork/plugin-sdk', 'react', 'react/jsx-runtime'])

// ---- a small scanner: top-level arguments of every jsx()/jsxs() call --------------

const REGEX_PREV = new Set(['(', ',', '=', ':', '[', '!', '&', '|', '?', '{', '}', ';', '+', '-', '*', '%', '<', '>', '~', '^', '\n', ''])

/** Index just past the string/template/comment/regex starting at i, or -1. */
function skipLiteral(text, i, prev) {
  const c = text[i]
  const next = text[i + 1]

  if (c === '/' && next === '/') {
    const end = text.indexOf('\n', i)

    return end < 0 ? text.length : end
  }

  if (c === '/' && next === '*') {
    const end = text.indexOf('*/', i + 2)

    return end < 0 ? text.length : end + 2
  }

  if (c === '"' || c === "'") {
    let j = i + 1

    while (j < text.length && text[j] !== c) {
      j += text[j] === '\\' ? 2 : 1
    }

    return j + 1
  }

  if (c === '`') {
    let j = i + 1

    while (j < text.length && text[j] !== '`') {
      if (text[j] === '\\') {
        j += 2
      } else if (text[j] === '$' && text[j + 1] === '{') {
        j = matchClose(text, j + 1)
      } else {
        j += 1
      }
    }

    return j + 1
  }

  if (c === '/' && REGEX_PREV.has(prev)) {
    let j = i + 1
    let inClass = false

    while (j < text.length) {
      const ch = text[j]

      if (ch === '\\') {
        j += 2
        continue
      }

      if (ch === '[') {
        inClass = true
      } else if (ch === ']') {
        inClass = false
      } else if (ch === '/' && !inClass) {
        break
      }

      j += 1
    }

    j += 1

    while (/[a-z]/i.test(text[j] || '')) {
      j += 1
    }

    return j
  }

  return -1
}

/** Index of the bracket that closes the one at `open`. */
function matchClose(text, open) {
  let depth = 0
  let prev = ''
  let i = open

  while (i < text.length) {
    const skipped = skipLiteral(text, i, prev)

    if (skipped >= 0) {
      i = skipped
      prev = 'x'
      continue
    }

    const c = text[i]

    if (c === '(' || c === '[' || c === '{') {
      depth += 1
    } else if (c === ')' || c === ']' || c === '}') {
      depth -= 1

      if (depth === 0) {
        return i
      }
    }

    if (!/\s/.test(c)) {
      prev = c
    }

    i += 1
  }

  return text.length
}

/** Every jsx/jsxs call in `text` with its top-level arguments as source strings. */
export function jsxCalls(text) {
  const calls = []
  const re = /(^|[^\w$.])(jsxs?)\s*\(/g
  let match

  while ((match = re.exec(text))) {
    const open = match.index + match[0].length - 1
    const close = matchClose(text, open)
    const args = []
    let depth = 0
    let start = open + 1
    let prev = '('
    let i = open + 1

    while (i < close) {
      const skipped = skipLiteral(text, i, prev)

      if (skipped >= 0) {
        i = skipped
        prev = 'x'
        continue
      }

      const c = text[i]

      if (c === '(' || c === '[' || c === '{') {
        depth += 1
      } else if (c === ')' || c === ']' || c === '}') {
        depth -= 1
      } else if (c === ',' && depth === 0) {
        args.push(text.slice(start, i).trim())
        start = i + 1
      }

      if (!/\s/.test(c)) {
        prev = c
      }

      i += 1
    }

    const tail = text.slice(start, close).trim()

    if (tail) {
      args.push(tail)
    }

    const line = text.slice(0, match.index).split('\n').length
    calls.push({ args, fn: match[2], line })
  }

  return calls
}

function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

// ---- source rules -------------------------------------------------------------------

test('no jsx() or jsxs() call takes a third argument', () => {
  const calls = jsxCalls(stripComments(source))

  assert.ok(calls.length >= 40, `scanner found only ${calls.length} jsx calls; it is not reading the file`)

  const offenders = calls.filter(call => call.args.length > 2).map(call => `line ~${call.line}: ${call.fn}(${call.args[0]}, ..., ${call.args[2]})`)

  assert.deepEqual(offenders, [])
})

test('the third-argument check fails on the broken shapes it exists for', () => {
  const broken = [
    "jsx('div', { style: {} }, [jsx('span', {})])",
    "jsxs(Row, props, ['a', 'b'])",
    "jsx(Panel, { a: 1 }, 'child text')"
  ]

  for (const sample of broken) {
    const [call] = jsxCalls(sample)

    assert.equal(call.args.length, 3, sample)
  }

  const healthy = "jsx('div', { children: [jsx('span', { key: 'a', children: 'x, y' })], title: `a, ${b(1, 2)}`, re: /,\\(/g })"

  assert.ok(jsxCalls(healthy).every(call => call.args.length <= 2))
})

test('no em dash anywhere in the file, literal or escaped', () => {
  assert.equal(source.includes('\u2014'), false, 'literal em dash')
  assert.equal(/\\u2014|\\u\{2014\}|&mdash;/i.test(source), false, 'escaped em dash')
})

test('no emoji anywhere in the file', () => {
  const hits = [...source.matchAll(/\p{Extended_Pictographic}/gu)].map(match => match[0])

  assert.deepEqual(hits, [])
})

test('imports only what the runtime loader resolves', () => {
  const specifiers = [...source.matchAll(/^\s*import\s[\s\S]*?from\s+'([^']+)'/gm)].map(match => match[1])

  assert.ok(specifiers.length > 0)

  for (const specifier of specifiers) {
    assert.ok(ALLOWED_IMPORTS.has(specifier), `unsupported import ${specifier}`)
  }

  assert.equal(/\bimport\s*\(/.test(stripComments(source)), false, 'dynamic import')
})

test('the keybind default is not a built-in default', () => {
  const actions = '/var/lib/duckwork/src/apps/desktop/src/lib/keybinds/actions.ts'

  if (!existsSync(actions)) {
    return
  }

  const app = readFileSync(actions, 'utf8')
  const taken = new Set([...app.matchAll(/'((?:mod|ctrl|alt|shift)\+[^']+)'/g)].map(match => match[1]))
  const combo = /const OPEN_COMBO = '([^']+)'/.exec(source)?.[1]

  assert.ok(combo, 'OPEN_COMBO not found')
  assert.ok(taken.has('mod+shift+f'), 'the clash this choice avoids is gone; revisit OPEN_COMBO')
  assert.equal(taken.has(combo), false, `${combo} is already a built-in default`)
})

// ---- load the module with the three specifiers stubbed ------------------------------

function dataUrl(code) {
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

const SDK_STUB = `
const atomOf = value => { let v = value; const subs = new Set(); return { get: () => v, set: n => { v = n; subs.forEach(f => f(n)) }, subscribe: f => { subs.add(f); f(v); return () => subs.delete(f) }, listen: f => { subs.add(f); return () => subs.delete(f) } } }
const noop = () => null
export const atom = atomOf
export const Dialog = noop, DialogContent = noop, DialogDescription = noop, DialogTitle = noop, Kbd = noop, MessageTextContent = noop, ScrollArea = noop, SearchField = noop
export const host = { state: { profile: atomOf('default'), cwd: atomOf('') }, openSession: async () => {}, notifyError: noop }
export const icons = new Proxy({}, { get: () => noop })
export const KEYBINDS_AREA = 'keybinds', PALETTE_AREA = 'palette'
export const STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const TITLEBAR_AREAS = { center: 'titleBar.center', left: 'titleBar.left', right: 'titleBar.right' }
export const queryClient = { prefetchQuery: async () => {} }
export const relativeTime = () => 'just now'
export const useQuery = () => ({}), useValue = store => store.get()
`

const REACT_STUB = `
export class Component { constructor(props) { this.props = props } }
export const useCallback = f => f, useEffect = () => {}, useMemo = f => f(), useRef = v => ({ current: v }), useState = v => [typeof v === 'function' ? v() : v, () => {}]
`

const JSX_STUB = `export const jsx = (type, props) => ({ type, props }); export const jsxs = jsx`

const rewritten = source
  .replace("from '@duckwork/plugin-sdk'", `from '${dataUrl(SDK_STUB)}'`)
  .replace("from 'react/jsx-runtime'", `from '${dataUrl(JSX_STUB)}'`)
  .replace("from 'react'", `from '${dataUrl(REACT_STUB)}'`)

const mod = await import(dataUrl(rewritten))

test('register wires the window, a palette row and a keybind on one action id', () => {
  const registered = []
  const stored = new Map()
  const ctx = {
    onDispose: () => {},
    register: c => registered.push(c),
    registerMany: cs => registered.push(...cs),
    rest: async () => [],
    storage: { get: (key, fallback) => (stored.has(key) ? stored.get(key) : fallback), remove: () => {}, set: (key, value) => stored.set(key, value) }
  }

  assert.equal(mod.default.id, 'session-find')
  mod.default.register(ctx)

  const byArea = Object.fromEntries(registered.map(c => [c.area, c]))

  assert.equal(typeof byArea['titleBar.center']?.render, 'function')
  assert.equal(byArea.palette?.data.label, 'Find a session')
  assert.deepEqual(byArea.keybinds?.data.defaults, ['mod+alt+f'])
  assert.equal(byArea.palette.data.action, byArea.keybinds.data.id)
})

test('parseQuery splits words, phrases and typed filters', () => {
  const parsed = mod.parseQuery('dns move in:signal -in:kanban after:2026-09-01 before:2026-10-01 me: repo:acme "exact words"')

  assert.deepEqual(parsed.words, ['dns', 'move'])
  assert.deepEqual(parsed.phrases, ['exact words'])
  assert.deepEqual(
    parsed.filters.map(filter => `${filter.kind}=${filter.value}`),
    ['in=signal', '-in=kanban', 'after=2026-09-01', 'before=2026-10-01', 'me=', 'repo=acme', 'exact=exact words']
  )
  assert.equal(mod.freeText('in:signal  dns "a b"'), 'dns a b')
  // A half-typed filter is still a word, so the chip does not flicker in.
  assert.deepEqual(mod.parseQuery('in:').words, ['in:'])
})

test('a source chip toggles its in: token and drops the opposite one', () => {
  assert.equal(mod.toggleSource('dns', 'signal'), 'dns in:signal ')
  assert.equal(mod.toggleSource('dns in:signal ', 'signal'), 'dns ')
  assert.equal(mod.toggleSource('dns -in:signal', 'signal'), 'dns in:signal ')
  assert.equal(mod.toggleSource('', 'desktop'), 'in:desktop ')
  assert.deepEqual(mod.activeSources('x IN:Signal in:desktop'), ['signal', 'desktop'])
  assert.equal(mod.removeToken('dns after:2026-09-01 move', 'after:2026-09-01'), 'dns move ')
  assert.equal(mod.removeToken('dns "a b" move', '"a b"'), 'dns move ')
  assert.equal(mod.removeToken('dns', 'absent'), 'dns')
})

test('highlights mark words and phrases, longest first, case-insensitive', () => {
  const terms = mod.highlightTerms('dns "dns move" -noise in:signal a')

  assert.deepEqual(terms, ['dns move', 'dns'])
  assert.deepEqual(mod.splitHighlights('We did the DNS move today', terms), [
    { hit: false, text: 'We did the ' },
    { hit: true, text: 'DNS move' },
    { hit: false, text: ' today' }
  ])
  assert.deepEqual(mod.splitHighlights('no terms', []), [{ hit: false, text: 'no terms' }])
  assert.deepEqual(mod.highlightTerms('a+b (c'), ['a+b', '(c'])
  assert.doesNotThrow(() => mod.splitHighlights('a+b (c', mod.highlightTerms('a+b (c')))
})

test('rows normalize from the shapes the service may answer', () => {
  const row = { session_id: 's1', title: '  dns \n move ', source: 'desktop', last_activity_at: 1792715103.48, pinned: 1, snippet: 'a\n b', snippet_message_id: 9, why: ['keyword', 'VECTOR'] }

  const [fromArray] = mod.normalizeRows([row, { ...row }])
  const [fromResults] = mod.normalizeRows({ results: [row], reranked: true })

  assert.equal(mod.normalizeRows([row, { ...row }]).length, 1, 'deduped by session id')
  assert.deepEqual(fromArray, fromResults)
  assert.equal(fromArray.title, 'dns move')
  assert.equal(fromArray.snippet, 'a b')
  assert.equal(fromArray.at, 1792715103480)
  assert.equal(fromArray.pinned, true)
  assert.deepEqual(fromArray.why, ['keyword', 'vector'])
  assert.equal(mod.normalizeRows({ results: [{ id: 'x' }] })[0].title, 'Untitled session')
  assert.deepEqual(mod.normalizeRows(null), [])
  assert.equal(mod.toMs('2026-10-22T00:00:00Z'), Date.parse('2026-10-22T00:00:00Z'))
  assert.equal(mod.toMs(1792715103480), 1792715103480)
  assert.equal(mod.toMs('1792715103'), 1792715103000)
  assert.equal(mod.toMs(undefined), 0)
})

test('snippets read as one line of prose, sources lead with the chat ones', () => {
  assert.equal(mod.plainSnippet('## 1. The **DNS move**: `swiftink.io` is\n done'), '1. The DNS move: swiftink.io is done')
  assert.equal(mod.plainSnippet('| name | route |\n|---|---|\n| a | b |'), '| name | route | | a | b |')
  assert.equal(mod.plainSnippet('issue #42 stays'), 'issue #42 stays')
  assert.deepEqual(mod.orderSources(['kanban', 'Desktop', 'cron', 'signal', 'desktop']), ['desktop', 'signal', 'kanban', 'cron'])
})

test('why reads title, keyword, meaning', () => {
  assert.equal(mod.whyLabel(['vector']), 'meaning')
  assert.equal(mod.whyLabel(['vector', 'keyword', 'title']), 'title + keyword + meaning')
  assert.equal(mod.whyLabel([]), '')
})

test('the footer reads a round trip as fast, ok or slow', () => {
  assert.equal(mod.speedTone(null), 'none')
  assert.equal(mod.speedTone(0), 'fast')
  assert.equal(mod.speedTone(mod.FAST_TRIP_MS), 'fast')
  assert.equal(mod.speedTone(mod.FAST_TRIP_MS + 1), 'ok')
  assert.equal(mod.speedTone(mod.SLOW_TRIP_MS), 'ok')
  assert.equal(mod.speedTone(mod.SLOW_TRIP_MS + 1), 'slow')
  assert.equal(mod.tookText(38.6), '39 ms')
  assert.equal(mod.tookText(0), '0 ms')
  assert.equal(mod.tookText(null), '')
})

test('pinned rows lead the empty state', () => {
  const rows = [{ id: 'a', pinned: false }, { id: 'b', pinned: true }, { id: 'c', pinned: false }]

  assert.deepEqual(mod.partitionPinned(rows).flat.map(row => row.id), ['b', 'a', 'c'])
})

test('scope cycles all, profile, repo, and skips repo with no workspace', () => {
  assert.equal(mod.nextScope('all', true), 'profile')
  assert.equal(mod.nextScope('profile', true), 'repo')
  assert.equal(mod.nextScope('repo', true), 'all')
  assert.equal(mod.nextScope('profile', false), 'all')
  assert.equal(mod.scopeLabel('repo', 'default', '/home/dev/acme/'), 'Repo acme')
  assert.equal(mod.nextSort('best'), 'newest')
  assert.equal(mod.nextSort('newest'), 'best')
})

test('moves clamp at both ends', () => {
  assert.equal(mod.moveIndex(0, -1, 5), 0)
  assert.equal(mod.moveIndex(4, 1, 5), 4)
  assert.equal(mod.moveIndex(2, 8, 5), 4)
  assert.equal(mod.moveIndex(-1, 1, 5), 1)
  assert.equal(mod.moveIndex(0, 1, 0), -1)
})

const press = (key, mods = {}) => ({ altKey: false, ctrlKey: false, isComposing: false, key, metaKey: false, shiftKey: false, ...mods })

test('keys follow the house table, and a move never opens', () => {
  assert.deepEqual(mod.keyAction(press('ArrowDown'), true), { delta: 1, type: 'move' })
  assert.deepEqual(mod.keyAction(press('ArrowUp'), false), { delta: -1, type: 'move' })
  assert.deepEqual(mod.keyAction(press('j', { ctrlKey: true }), true), { delta: 1, type: 'move' })
  assert.deepEqual(mod.keyAction(press('k', { ctrlKey: true }), true), { delta: -1, type: 'move' })
  // Off macOS ctrl+j / ctrl+k are the app's own chords (right sidebar, palette).
  assert.equal(mod.keyAction(press('j', { ctrlKey: true }), false), null)
  assert.equal(mod.keyAction(press('k', { ctrlKey: true }), false), null)
  assert.deepEqual(mod.keyAction(press('Enter'), true), { intent: 'in-place', type: 'open' })
  assert.deepEqual(mod.keyAction(press('Enter', { metaKey: true }), true), { intent: 'tab', type: 'open' })
  assert.deepEqual(mod.keyAction(press('Enter', { ctrlKey: true, shiftKey: true }), false), { intent: 'window', type: 'open' })
  assert.deepEqual(mod.keyAction(press('Tab'), true), { type: 'sort' })
  assert.deepEqual(mod.keyAction(press('Tab', { shiftKey: true }), true), { type: 'sort' })
  assert.deepEqual(mod.keyAction(press('r', { ctrlKey: true }), true), { type: 'scope' })
  // Bare letters are text in the field.
  for (const key of ['j', 'k', 'h', 'l', ' ', 'Escape']) {
    assert.equal(mod.keyAction(press(key), true), null, key)
  }

  assert.equal(mod.keyAction({ ...press('Enter'), isComposing: true }, true), null)
})

test('the search path carries the contract parameters', () => {
  const all = new URL(`http://x${mod.searchPath({ cwd: '/r', keywords: true, meaning: true, profile: 'default', q: 'dns in:signal', scope: 'all', sort: 'best' })}`)

  assert.equal(all.pathname, '/search')
  assert.equal(all.searchParams.get('q'), 'dns in:signal')
  assert.equal(all.searchParams.get('limit'), '30')
  assert.equal(all.searchParams.get('sort'), 'best')
  assert.equal(all.searchParams.get('scope'), 'all')
  assert.equal(all.searchParams.get('profile'), 'default')
  // Both retrieval toggles are spelled out on every request, so a changed
  // default in the service cannot change what the window shows.
  assert.equal(all.searchParams.get('vec'), '1')
  assert.equal(all.searchParams.get('kw'), '1')
  assert.equal(all.searchParams.has('rerank'), false)
  assert.equal(all.searchParams.has('cwd'), false)
  // The paint stage asks for the keyword index alone; the fused answer omits it.
  assert.equal(all.searchParams.has('fast'), false)

  const fast = new URL(`http://x${mod.searchPath({ cwd: '', fast: true, keywords: true, meaning: false, profile: '', q: 'gal', scope: 'all', sort: 'best' })}`)

  assert.equal(fast.searchParams.get('fast'), '1')
  assert.equal(fast.searchParams.get('q'), 'gal')
  assert.equal(fast.searchParams.get('vec'), '0')
  assert.equal(fast.searchParams.get('kw'), '1')

  const repo = new URL(`http://x${mod.searchPath({ cwd: '/r', keywords: false, meaning: true, profile: '', q: 'x', scope: 'repo', sort: 'newest' })}`)

  assert.equal(repo.searchParams.get('cwd'), '/r')
  assert.equal(repo.searchParams.get('vec'), '1')
  assert.equal(repo.searchParams.get('kw'), '0')
})

test('a result opens at its message when the desktop can, and at the session when it cannot', () => {
  const calls = []
  const hostApi = {
    openSession: (...args) => calls.push(['session', ...args]),
    revealMessage: (...args) => calls.push(['message', ...args])
  }

  mod.openTarget(hostApi, { id: 's1', messageId: 41 }, { intent: 'tab', profile: 'work' })
  assert.deepEqual(calls.at(-1), ['message', 's1', 41, { intent: 'tab', profile: 'work' }])

  // A hit with no message (a title-only or recent row) has nothing to land on.
  mod.openTarget(hostApi, { id: 's2', messageId: null }, { intent: 'in-place' })
  assert.deepEqual(calls.at(-1), ['session', 's2', { intent: 'in-place' }])

  // An older desktop has no message door at all: it still opens, at the tail.
  mod.openTarget({ openSession: (...args) => calls.push(['legacy', ...args]) }, { id: 's3', messageId: 7 }, {})
  assert.deepEqual(calls.at(-1), ['legacy', 's3', {}])
})
