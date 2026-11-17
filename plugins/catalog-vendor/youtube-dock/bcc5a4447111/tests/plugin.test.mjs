import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import React from 'react'
import * as jsxRuntime from 'react/jsx-runtime'
import { renderToStaticMarkup } from 'react-dom/server'

const source = await readFile(new URL('../desktop/plugin.js', import.meta.url), 'utf8')

// This is a unit SDK double, not a substitute for exercising the actual Desktop.
async function loadPlugin(locale = 'en', { saved = false, removeFails = false } = {}) {
  const contributions = []
  const disposers = []
  const storageCalls = []
  let bundles = {}
  const t = key => bundles[locale]?.[key] ?? bundles.en?.[key] ?? key
  const wrap = tag => ({ children }) => React.createElement(tag, null, children)
  const sdk = {
    Button: ({ children, type, ...props }) => React.createElement('button', { type, 'aria-label': props['aria-label'] }, children),
    Codicon: () => React.createElement('span', { 'aria-hidden': true }),
    Switch: props => React.createElement('button', { role: 'switch', 'aria-checked': props.checked }),
    MessageTextContent: ({ text }) => React.createElement('span', { 'data-preview-markdown': text }),
    PALETTE_AREA: 'palette', TITLEBAR_AREAS: { right: 'titleBar.right' },
    Popover: ({ children, open }) => React.createElement('div', { 'data-open': String(open) }, children),
    PopoverContent: wrap('aside'), PopoverTrigger: wrap('div'),
    atom: initial => { let value = initial; return { get: () => value, set: next => { value = next }, listen: () => () => {} } },
    host: { state: {}, notify: () => {} }, translateNow: key => key,
    usePluginI18n: () => t, useValue: value => value.get()
  }
  const ctx = {
    i18n: { register: value => { bundles = value }, t },
    storage: {
      get: key => { storageCalls.push(['get', key]); return saved },
      set: (key, value) => storageCalls.push(['set', key, value]),
      remove: key => { storageCalls.push(['remove', key]); if (removeFails) throw new Error('storage unavailable') }
    },
    register: contribution => { contributions.push(contribution); return () => {} },
    onDispose: dispose => disposers.push(dispose)
  }
  const context = vm.createContext({ console })
  const synthetic = (name, exports) => new vm.SyntheticModule(Object.keys(exports), function () {
    for (const [key, value] of Object.entries(exports)) this.setExport(key, value)
  }, { context, identifier: name })
  const deps = new Map([
    ['@duckwork/plugin-sdk', synthetic('sdk', sdk)],
    ['react/jsx-runtime', synthetic('jsx', jsxRuntime)]
  ])
  const module = new vm.SourceTextModule(source, { context, identifier: 'youtube-dock/desktop/plugin.js' })
  await module.link(name => {
    assert.ok(deps.has(name), `Unexpected runtime import: ${name}`)
    return deps.get(name)
  })
  await module.evaluate()
  module.namespace.default.register(ctx)
  return { module: module.namespace, contributions, disposers, storageCalls,
    render: () => renderToStaticMarkup(React.createElement(module.namespace.YouTubeMenu)) }
}

function hrefOf(markdown) {
  return markdown.slice(markdown.indexOf('](') + 2, -1)
}

test('registers an opt-in titlebar menu and palette command without opening any page', async () => {
  const plugin = await loadPlugin()
  assert.equal(plugin.module.default.defaultEnabled, false)
  assert.equal(plugin.contributions.length, 2)
  assert.equal(plugin.contributions[0].area, 'titleBar.right')
  assert.equal(plugin.contributions[1].area, 'palette')
  assert.match(plugin.render(), /data-open="false"/)
})

test('palette opens the menu and plugin disposal closes its local state', async () => {
  const plugin = await loadPlugin()
  plugin.contributions[1].data.run()
  assert.match(plugin.render(), /data-open="true"/)
  plugin.disposers.forEach(dispose => dispose())
  assert.match(plugin.render(), /data-open="false"/)
})

test('only fixed Home and Shorts destinations produce encoded native preview links', async () => {
  const plugin = await loadPlugin()
  assert.equal(plugin.module.DESTINATIONS.length, 2)
  for (const destination of plugin.module.DESTINATIONS) {
    const markdown = plugin.module.previewMarkdown(destination.url)
    assert.ok(hrefOf(markdown).startsWith('#preview/'))
    assert.equal(decodeURIComponent(hrefOf(markdown).slice('#preview/'.length)), destination.url)
    assert.equal(new URL(destination.url).origin, 'https://www.youtube.com')
  }
  for (const url of ['https://example.com/', 'javascript:alert(1)', 'https://www.youtube.com.evil.test/']) {
    assert.throws(() => plugin.module.previewMarkdown(url))
  }
})

test('real React renders the English menu and the two SDK preview controls', async () => {
  const plugin = await loadPlugin()
  const html = plugin.render()
  assert.match(html, /YouTube — recommendations and Shorts/)
  assert.match(html, /Recommended videos/)
  assert.equal((html.match(/data-preview-markdown=/g) ?? []).length, 2)
  assert.doesNotMatch(html, /<iframe|<webview|<script/)
})

test('Korean and unsupported locales use translated labels and the English fallback', async () => {
  const korean = await loadPlugin('ko')
  assert.match(korean.render(), /추천 피드/)
  assert.match(korean.render(), /쇼츠/)
  const fallback = await loadPlugin('fr')
  assert.match(fallback.render(), /Recommended videos/)
})

test('one-click destination has no automatic pin capture handler', async () => {
  const plugin = await loadPlugin()
  for (const destination of plugin.module.DESTINATIONS) {
    const section = plugin.module.Destination({ destination, t: key => key })
    assert.equal(section.props.children[2].props.onClickCapture, undefined)
  }
})

test('removed beta cannot affect opening even with old saved ON or OFF', async () => {
  for (const saved of [true, false, null, 'true']) {
    const p = await loadPlugin('en', { saved })
    assert.equal((p.render().match(/data-preview-markdown=/g) ?? []).length, 2)
    assert.doesNotMatch(p.render(), /Beta|Manual tab setup|Copy address|role="switch"/)
    assert.equal(p.module.ManualGuide, undefined)
    assert.equal(p.module.copyDestination, undefined)
    assert.equal(p.module.setManualGuide, undefined)
    assert.deepEqual(p.storageCalls, [['remove', 'manualPinGuide']])
  }
})

test('obsolete-key cleanup failure cannot break the one-click menu', async () => {
  const p = await loadPlugin('ko', { saved: true, removeFails: true })
  assert.equal((p.render().match(/data-preview-markdown=/g) ?? []).length, 2)
  assert.doesNotMatch(p.render(), /베타|주소 복사|수동 탭 설정/)
  assert.deepEqual(p.storageCalls, [['remove', 'manualPinGuide']])
})

test('production has no beta controls, clipboard, preference reads or automatic pin adapter', () => {
  assert.doesNotMatch(source, /ManualGuide|manualGuide|setManualGuide|copyDestination|writeClipboard|storage\.(get|set)|MutationObserver|querySelector|dispatchEvent|onClickCapture/)
})

test('native Duckwork decoder preserves and resolves both visible preview links', {
  skip: !process.env.DUCKWORK_SOURCE_ROOT && 'Set DUCKWORK_SOURCE_ROOT for the native integration check'
}, async () => {
  const { build } = await import('esbuild')
  const root = path.resolve(process.env.DUCKWORK_SOURCE_ROOT)
  const compiled = await build({
    entryPoints: [path.join(root, 'apps/desktop/src/lib/preview-targets.ts')],
    bundle: true, write: false, format: 'esm', platform: 'node',
    alias: { '@': path.join(root, 'apps/desktop/src') }, logLevel: 'silent'
  })
  const encoded = Buffer.from(compiled.outputFiles[0].text).toString('base64')
  const { previewTargetFromMarkdownHref, stripPreviewTargets } = await import(`data:text/javascript;base64,${encoded}`)
  const plugin = await loadPlugin()
  for (const destination of plugin.module.DESTINATIONS) {
    const markdown = plugin.module.previewMarkdown(destination.url)
    assert.equal(stripPreviewTargets(markdown), markdown, 'Controls must not be stripped as agent hand-off markers')
    assert.equal(previewTargetFromMarkdownHref(hrefOf(markdown)), destination.url)
  }
})
