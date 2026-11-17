// Headless test for desktop/plugin.js. Run with: node test/plugin.test.mjs (Node 20+).
//
// Loads the plugin the way the Desktop runtime loader does, with its two import
// specifiers rewritten to stand-in modules, then drives register() with a fake
// ctx, document and window. No dependencies, no files written.
import { readFileSync } from 'node:fs'

const SDK = `
export function atom(value) {
  const listeners = new Set()
  return {
    get: () => value,
    set(next) { value = next; for (const listener of listeners) listener(value) },
    subscribe(listener) { listeners.add(listener); listener(value); return () => listeners.delete(listener) }
  }
}
export const APPEARANCE_AREAS = { extra: 'appearance.extra' }
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const ListRow = 'ListRow'
export const SegmentedControl = 'SegmentedControl'
export const haptic = () => {}
export const usePluginI18n = () => key => key
export const useValue = store => store.get()
`
const JSX_RUNTIME = 'export const jsx = (type, props) => ({ type, props })'
const asModuleUrl = code => `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`

const source = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')
  .replace("from '@duckwork/plugin-sdk'", `from '${asModuleUrl(SDK)}'`)
  .replace("from 'react/jsx-runtime'", `from '${asModuleUrl(JSX_RUNTIME)}'`)
const { default: plugin } = await import(asModuleUrl(source))

// ── Fakes ────────────────────────────────────────────────────────────────────
const head = []
globalThis.document = {
  createElement: tag => ({
    tag,
    textContent: '',
    setAttribute() {},
    remove() {
      const at = head.indexOf(this)
      if (at >= 0) head.splice(at, 1)
    }
  }),
  head: { append: element => head.push(element) }
}
const windowListeners = {}
globalThis.window = { addEventListener: (type, listener) => (windowListeners[type] = listener) }
const setPlatform = platform =>
  Object.defineProperty(globalThis, 'navigator', { value: { platform, userAgent: '' }, configurable: true })

const storage = new Map()
const locales = {}
let locale = 'en'
let disposers = []
let contributions = []
let localeListener = null

function makeCtx() {
  const track = dispose => (disposers.push(dispose), dispose)
  return {
    i18n: {
      register: bundles => Object.assign(locales, bundles),
      t: key => (locales[locale] ?? locales.en)[key],
      onLocaleChange: listener => track(() => (localeListener = null), (localeListener = listener))
    },
    storage: {
      get: (key, fallback) => (storage.has(key) ? JSON.parse(storage.get(key)) : fallback),
      set: (key, value) => storage.set(key, JSON.stringify(value))
    },
    onDispose: dispose => void track(dispose),
    addEventListener: (target, type, listener) => (target.addEventListener(type, listener), track(() => {})),
    register: c => (contributions.push(c), track(() => (contributions = contributions.filter(x => x !== c)))),
    registerMany: cs => (contributions.push(...cs), track(() => (contributions = contributions.filter(x => !cs.includes(x)))))
  }
}
const load = () => plugin.register(makeCtx())
const unload = () => {
  disposers.splice(0).forEach(dispose => dispose())
}
const css = () => head[0]?.textContent
const byId = id => contributions.find(c => c.id === id)
const area = name => contributions.filter(c => c.area === name)

let failures = 0
const check = (label, ok) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}`)
  if (!ok) failures++
}

// ── macOS ────────────────────────────────────────────────────────────────────
setPlatform('MacIntel')
load()
check('plugin id matches its folder name', plugin.id === 'preview-text-size')
check('one <style> is appended', head.length === 1)
check('default size is 100%, so no CSS is applied', css() === '')
check('Appearance row is registered', byId('appearance-row')?.area === 'appearance.extra')
check('three palette commands', area('palette').length === 3)
check('three rebindable shortcuts', area('keybinds').length === 3)
check(
  'macOS default chords',
  JSON.stringify(area('keybinds').map(c => c.data.defaults)) === '[["mod+alt+="],["mod+alt+-"],["mod+alt+0"]]'
)
const run = id => byId(id).data.run()
run('key-larger')
check('larger: 100% -> 110%', css() === '[data-preview-markdown] { zoom: 1.1; }')
for (let i = 0; i < 6; i++) run('key-larger')
check('larger stops at 175%', css() === '[data-preview-markdown] { zoom: 1.75; }')
check('palette row shows the live size', byId('palette-larger').data.detail() === '175%')
run('key-reset')
check('reset returns to 100% and removes the rule', css() === '')
run('key-smaller')
run('key-smaller')
check('smaller stops at 90%', css() === '[data-preview-markdown] { zoom: 0.9; }')
check('the size is persisted', storage.get('scale') === '90')
const row = byId('appearance-row').render()
row.props.setScale(150)
check('Appearance row setter applies the size', css() === '[data-preview-markdown] { zoom: 1.5; }')

unload()
check('unload removes the <style>', head.length === 0)
check('unload removes every contribution', contributions.length === 0)

load()
check('reload restores the stored size', css() === '[data-preview-markdown] { zoom: 1.5; }')
unload()
storage.set('scale', '133')
load()
check('an off-preset stored value snaps to the nearest preset', css() === '[data-preview-markdown] { zoom: 1.25; }')
storage.set('scale', '"garbage"')
windowListeners.storage({ key: 'duckwork.plugin.preview-text-size.scale' })
check('garbage from storage falls back to 100%', css() === '')
storage.set('scale', '175')
windowListeners.storage({ key: 'duckwork.plugin.preview-text-size.scale' })
check('a change from another window is followed', css() === '[data-preview-markdown] { zoom: 1.75; }')
windowListeners.storage({ key: 'some.other.key' })
check('unrelated storage events are ignored', css() === '[data-preview-markdown] { zoom: 1.75; }')

locale = 'zh'
localeListener()
check('a language switch relabels the commands', byId('palette-larger').data.label === '预览文字放大')
check('a language switch does not duplicate commands', area('palette').length === 3 && area('keybinds').length === 3)
unload()
locale = 'en'

// ── Windows / Linux ──────────────────────────────────────────────────────────
setPlatform('Win32')
load()
check(
  'no default chords off macOS (Ctrl+Alt is AltGr there)',
  area('keybinds').every(c => Array.isArray(c.data.defaults) && c.data.defaults.length === 0)
)
unload()

console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed')
process.exit(failures ? 1 : 0)
