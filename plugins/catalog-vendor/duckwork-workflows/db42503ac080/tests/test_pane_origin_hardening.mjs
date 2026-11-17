// est-wk7l — the pane's originator lookup must NEVER resolve through inherited
// properties of the session->profile map. A persisted session id that collides
// with an Object.prototype member (toString / constructor / __proto__) used to
// render the native function/object as the agent's name (adversary ui-probes:
// '@function toString() { [native code] }', '@[object Object]'). The label must
// be an own-property, typed-string read, and never be another row's origin.
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

const paneModel = new Function(`${grab('paneModel')}\n${grab('originLabel')}\n${grab('safeProfileLabel')}\n${grab('parseTime')}; return paneModel`)()

const base = (id, status, session) => ({ id, status, updated: 1000, owner: session ? { session_id: session } : null })
const map = {}   // ordinary object: prototype members are reachable unless guarded

// persisted ids that collide with Object.prototype members
const runs = [
  base('r-toString', 'done', 'toString'),
  base('r-constructor', 'done', 'constructor'),
  base('r-proto', 'done', '__proto__'),
  base('r-normal', 'done', 'normal-session'),
]
const model = paneModel(runs, map)
const originOf = id => (model.rest.find(r => r.id === id) || {}).origin
for (const [id, sid] of [['r-toString', 'toString'], ['r-constructor', 'constructor'], ['r-proto', '__proto__']]) {
  const o = originOf(id)
  assert.equal(typeof o, 'string', `${id}: origin must be a string, got ${typeof o}`)
  assert.ok(!o.includes('native code') && !o.includes('[object'),
    `${id}: origin leaks a prototype member: ${o}`)
  // the honest fallback: originLabel's law — the raw session id as a string,
  // never the prototype's value and never another row's origin.
  assert.ok(o === 'unknown' || o === sid || o === '@' + sid,
    `${id}: origin fell back dishonestly: ${o}`)
}
// the ordinary row keeps the raw id when the map holds nothing
assert.equal(originOf('r-normal'), 'normal-session')

// own-property only: a map that DOES carry the session resolves normally
const owned = { 'toString-x': 'alpha' }
const m2 = paneModel([base('r-owned', 'done', 'toString-x')], owned)
assert.equal(m2.rest[0].origin, 'alpha')

// __proto__ assignment can never poison later rows through the lookup
const poisoned = {}
poisoned['__proto__'] = { 'evil-session': 'evil' }
const m3 = paneModel([base('r-evil', 'done', 'evil-session')], poisoned)
assert.notEqual(m3.rest[0].origin, 'evil', 'inherited property must not resolve as an origin')

console.log('test_pane_origin_hardening OK')
