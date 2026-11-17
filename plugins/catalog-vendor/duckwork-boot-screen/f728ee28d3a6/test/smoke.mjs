// duckwork-boot-screen smoke test: stub out the SDK import, then verify top-level module
// evaluation, normalize() edge semantics, the shouldPlay() gate, and the register() shape.
// Usage: node test/smoke.mjs   (run after building)
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import assert from 'node:assert'

const root = path.dirname(new URL(import.meta.url).pathname.replace(/^\//, ''))
// Stripping the leading / already yields a valid C:/... Windows path — no drive-letter fixup needed
const rootDir = root
const pluginPath = path.join(rootDir, '..', 'plugin.js')
let src = fs.readFileSync(pluginPath, 'utf8')

// 1) Stub every import (string search rather than regex — the specifiers contain a bare /
//    which would trip up the regex delimiter)
function replaceOnce(haystack, startNeedle, endNeedle, replacement) {
  const start = haystack.indexOf(startNeedle)
  if (start < 0) throw new Error('start needle not found: ' + startNeedle.slice(0, 60))
  const end = haystack.indexOf(endNeedle, start)
  if (end < 0) throw new Error('end needle not found: ' + endNeedle.slice(0, 60))
  return haystack.slice(0, start) + replacement + haystack.slice(end + endNeedle.length)
}

src = replaceOnce(src, 'import {', "} from '@duckwork/plugin-sdk'",
`const host = { notify() {}, navigate() {}, request() { return Promise.resolve(null) } }
const haptic = () => {}
const APPEARANCE_AREAS = { extra: 'appearance.extra' }
const ROUTES_AREA = 'routes'
const SIDEBAR_NAV_AREA = 'sidebar.nav'
const PALETTE_AREA = 'palette'
const ToggleRow = 'ToggleRow', ListRow = 'ListRow', SegmentedControl = 'SegmentedControl'
const Input = 'Input', Button = 'Button'`)
src = src.replace("import { jsx, jsxs } from 'react/jsx-runtime'", 'const jsx = () => null, jsxs = () => null')
src = src.replace("import { useState } from 'react'", 'const useState = (init) => [typeof init === "function" ? init() : init, () => {}]')

if (src.includes("} from '@duckwork/plugin-sdk'")) throw new Error('SDK import not stubbed')
if (src.includes("from 'react/jsx-runtime'") || src.includes("from 'react'")) throw new Error('react import not stubbed')

// 2) Expose the internals for assertions
src += '\nexport { normalize, shouldPlay, DEFAULTS }\n'

// 3) Minimal browser global stubs (no DOM work at module top level; the DOM path from
//    register→play is caught by play()'s try/catch inside runSplash — that is the expected behavior)
globalThis.window = {
  sessionStorage: { getItem: () => null, setItem: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
  setTimeout: () => 0,
  __DSH_STARTUP__: null
}
globalThis.document = {
  getElementById: () => null,
  createElement: () => ({
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    style: { setProperty() {}, removeProperty() {} },
    setAttribute() {}, appendChild() {}, removeChild() {},
    querySelector: () => null, querySelectorAll: () => []
  }),
  createElementNS: () => ({ setAttribute() {}, appendChild() {} }),
  head: { appendChild() {} },
  body: { appendChild() {}, style: {} },
  documentElement: { classList: { add() {}, remove() {} }, style: {} },
  addEventListener() {},
  removeEventListener() {}
}
globalThis.fetch = () => Promise.reject(new Error('no network in smoke'))

const tmp = path.join(rootDir, '__smoke_mod.mjs')
fs.writeFileSync(tmp, src, 'utf8')
try {
  const mod = await import('file:///' + tmp.replace(/\\/g, '/'))

  // --- normalize edge cases ---
  const d = mod.normalize(null)
  assert.equal(d.identity, 'OMOX', 'identity default')
  assert.match(d.identityId, /^[0-9a-f]{16}$/, 'identityId is a random 16-hex hash')
  assert.equal(d.brand1, 'DUCKWORK', 'branding: brand1')
  assert.equal(d.orgZh, '赫尔墨斯', 'branding: orgZh')
  assert.equal(d.accessLevel, '0', 'access level default')
  assert.equal(d.footer, 'POWERED BY FORDEX', 'branding: footer')
  assert.equal(d.welcomeBox, 'DUCKWORK DESKTOP', 'branding: welcomeBox')
  assert.equal(d.mode, 'session', 'mode default')
  assert.equal(d.voiceSource, 'asset', 'voiceSource default')

  assert.equal(mod.normalize({ speed: 99 }).speed, 3, 'speed clamp hi')
  assert.equal(mod.normalize({ speed: 0.01 }).speed, 0.35, 'speed clamp lo')
  assert.equal(mod.normalize({ speed: 'x' }).speed, 1, 'speed non-finite fallback')
  assert.equal(mod.normalize({ mode: 'nope' }).mode, 'session', 'enum fallback')
  assert.equal(mod.normalize({ enabled: 'true' }).enabled, true, 'bool from string')
  assert.equal(mod.normalize({ enabled: 'false' }).enabled, false, 'bool false from string')
  assert.equal(mod.normalize({ accent: 'red' }).accent, '#ff7500', 'color invalid fallback')
  assert.equal(mod.normalize({ accent: '#00ff00' }).accent, '#00ff00', 'color valid kept')
  assert.equal(mod.normalize({ voiceRate: 5 }).voiceRate, 2, 'voiceRate clamp')
  assert.equal(mod.normalize({ orgZh: 'x'.repeat(100) }).orgZh.length, 64, 'text truncated')
  assert.equal(mod.normalize({ identity: '  ' }).identity, 'OMOX', 'blank identity fallback')

  // --- shouldPlay gate ---
  const base = mod.normalize(null)
  assert.equal(mod.shouldPlay({ ...base, enabled: false }), false, 'disabled never plays')
  assert.equal(mod.shouldPlay({ ...base, mode: 'always' }), true, 'always plays')
  // session: already shown
  globalThis.window.sessionStorage.getItem = (k) => (k === 'duckwork-boot-screen:shown' ? '1' : null)
  assert.equal(mod.shouldPlay({ ...base, mode: 'session' }), false, 'session shown -> skip')
  globalThis.window.sessionStorage.getItem = () => null
  assert.equal(mod.shouldPlay({ ...base, mode: 'session' }), true, 'session unshown -> play')
  // daily: already shown today
  const today = new Date().toISOString().slice(0, 10)
  globalThis.window.localStorage.getItem = (k) => (k === 'duckwork-boot-screen:day' ? today : null)
  assert.equal(mod.shouldPlay({ ...base, mode: 'daily' }), false, 'daily today -> skip')
  globalThis.window.localStorage.getItem = () => null
  assert.equal(mod.shouldPlay({ ...base, mode: 'daily' }), true, 'daily other day -> play')

  // --- register() contribution shape ---
  const contributions = []
  const stored = new Map()
  const ctx = {
    register(c) { contributions.push(c); return () => {} },
    storage: {
      get: (k, fb) => (stored.has(k) ? stored.get(k) : fb),
      set: (k, v) => stored.set(k, v),
      remove: (k) => stored.delete(k)
    },
    onDispose() {}
  }
  // play() inside register() is swallowed by try/catch because there is no DOM — it must not throw
  mod.default.register(ctx)
  assert.equal(mod.default.id, 'duckwork-boot-screen', 'plugin id')
  assert.equal(contributions.length, 5, 'five contributions registered')
  const areas = contributions.map((c) => c.area).sort()
  assert.deepEqual(areas, ['appearance.extra', 'palette', 'palette', 'routes', 'sidebar.nav'], 'areas')
  const route = contributions.find((c) => c.area === 'routes')
  assert.equal(route.data.path, '/startup-animation', 'route path')
  assert.equal(typeof route.render, 'function', 'route page render')
  const nav = contributions.find((c) => c.area === 'sidebar.nav')
  assert.equal(nav.data.path, '/startup-animation', 'sidebar nav pairs the route')
  assert.equal(nav.data.label, 'Startup Animation', 'sidebar nav label')
  const palette = contributions.find((c) => c.area === 'palette' && c.id === 'replay')
  assert.equal(typeof palette.data.run, 'function', 'palette run is function')
  assert.equal(palette.data.label, 'Startup Animation: Play Now', 'palette replay label')
  const openSettings = contributions.find((c) => c.area === 'palette' && c.id === 'open-settings')
  assert.equal(openSettings.data.label, 'Startup Animation: Open Settings', 'palette settings label')
  assert.equal(typeof openSettings.data.run, 'function', 'palette settings run')
  const card = contributions.find((c) => c.area === 'appearance.extra')
  assert.equal(typeof card.render, 'function', 'appearance card render')

  // writeCfg goes through storage: register again and read back (simulates config surviving a hot reload)
  stored.set('config', { mode: 'daily', speed: 2, identity: 'TESTER' })
  contributions.length = 0
  mod.default.register(ctx)
  assert.ok(contributions.length === 5, 're-register works')

  // --- the confirm key must be intercepted in the capture phase ---
  // Regression guard: Enter/Space used to be bound only on document's bubble phase and were eaten
  // by the chat composer's onKeyDown (Enter in a textarea sends the message) → it showed up as
  // "pressing Enter does nothing / you have to press it many times", while Space happened to still
  // work. Pin capture binding + the keyup fallback + NumpadEnter.
  const runtime = src
  assert.ok(
    runtime.includes("document.addEventListener('keydown', onKey, true)"),
    'confirm keys bound in capture phase (survives composer stopPropagation)')
  assert.ok(
    runtime.includes("document.addEventListener('keyup', onKeyUp, true)"),
    'keyup fallback bound')
  assert.ok(runtime.includes("e.key === 'NumpadEnter'"), 'numpad enter recognised')
  assert.ok(
    /addEventListener\('keydown', escHandler, true\)/.test(runtime),
    'Esc skip also bound in capture phase')
  assert.ok(
    runtime.includes('stopPropagation'),
    'handlers stop propagation so the composer never sees the confirm key')

  console.log('SMOKE OK — normalize/shouldPlay/register/capture-keys: all assertions passed')
} finally {
  fs.rmSync(tmp, { force: true })
}
