#!/usr/bin/env node
// Regenerate locales/pt-br.desktop.yaml from the pt overrides on
// StudioCodeAI/duckwork-agent branch feature/i18n-pt-br (PR #92590).
//
//   DUCKWORK_REPO=/path/to/duckwork-agent node tools/build-desktop-pack.mjs
//
// The pt catalog is a set of `TranslationOverrides` split by topic; each file
// is bundled with esbuild (it only imports types, erased at build) and composed
// exactly like apps/desktop/src/i18n/pt.ts does. Leaves are flattened to dotted
// keys and filtered against the CURRENT upstream English key export
// (`git show upstream/main:locales/_keys.desktop.json`) so the pack never
// carries a key upstream has removed.
import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const PACK = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const REPO = resolve(process.env.DUCKWORK_REPO ?? join(PACK, '..', 'duckwork-agent'))
const REF = process.env.DUCKWORK_REF ?? 'upstream/main'
const TMP = join(PACK, '.build')

const require = createRequire(join(REPO, 'package.json'))
const esbuild = require('esbuild')

const app = join(REPO, 'apps/desktop')
const I18N = join(app, 'src/i18n')

const alias = {
  '@duckwork/shared/ansi': join(REPO, 'apps/shared/src/ansi.ts'),
  '@duckwork/shared/billing': join(REPO, 'apps/shared/src/billing-types.ts'),
  '@duckwork/shared/color': join(REPO, 'apps/shared/src/color.ts'),
  '@duckwork/shared/i18n': join(REPO, 'apps/shared/src/i18n.ts'),
  '@duckwork/shared/translucency': join(REPO, 'apps/shared/src/translucency.ts'),
  '@duckwork/shared': join(REPO, 'apps/shared/src/index.ts'),
  '@': join(app, 'src')
}

async function loadExport(file, exportName) {
  const outfile = join(TMP, `${file.replace(/\.ts$/, '')}-${process.pid}.mjs`)
  await esbuild.build({
    entryPoints: [join(I18N, file)],
    bundle: true,
    format: 'esm',
    platform: 'node',
    target: 'node22',
    jsx: 'automatic',
    alias,
    loader: { '.css': 'empty', '.svg': 'empty', '.png': 'empty', '.woff2': 'empty', '.woff': 'empty' },
    logLevel: 'silent',
    outfile
  })
  const mod = await import(pathToFileURL(outfile).href)
  return mod[exportName]
}

function flatten(node, prefix = '', out = {}) {
  if (node !== null && typeof node === 'object' && !Array.isArray(node)) {
    for (const [key, value] of Object.entries(node)) {
      flatten(value, prefix ? `${prefix}.${key}` : key, out)
    }
  } else if (typeof node === 'string') {
    out[prefix] = node
  }
  return out
}

function upstream(path) {
  return execFileSync('git', ['show', `${REF}:${path}`], { cwd: REPO, maxBuffer: 64 * 1024 * 1024 }).toString('utf8')
}

function refKeys(path) {
  const data = JSON.parse(upstream(path))
  return new Set(Array.isArray(data) ? data : data.keys)
}

const SAFE_KEY = /^[A-Za-z0-9_.-]+$/

function yamlLine(key, value) {
  const k = SAFE_KEY.test(key) && !/^(on|off|yes|no)$/i.test(key) ? key : JSON.stringify(key)
  return `${k}: ${JSON.stringify(value)}`
}

function renderYaml(flat) {
  const keys = Object.keys(flat).sort()
  return `${keys.map(key => yamlLine(key, flat[key])).join('\n')}\n`
}

const PARTS = [
  ['pt_common.ts', 'ptCommon'],
  ['pt_boot.ts', 'ptBoot'],
  ['pt_models.ts', 'ptModels'],
  ['pt_capabilities.ts', 'ptCapabilities'],
  ['pt_command_center.ts', 'ptCommandCenter'],
  ['pt_chat.ts', 'ptChat'],
  ['pt_chrome.ts', 'ptChrome'],
  ['pt_assistant.ts', 'ptAssistant']
]

async function main() {
  rmSync(TMP, { recursive: true, force: true })
  mkdirSync(TMP, { recursive: true })
  mkdirSync(join(PACK, 'locales'), { recursive: true })

  const byName = Object.fromEntries(
    await Promise.all(PARTS.map(async ([file, name]) => [name, await loadExport(file, name)]))
  )
  const introPt = await loadExport('intro-pt.ts', 'introPt')
  const ptSettingsA = await loadExport('pt_settings_a.ts', 'ptSettingsA')
  const ptSettingsB = await loadExport('pt_settings_b.ts', 'ptSettingsB')

  // Mirror apps/desktop/src/i18n/pt.ts's composition order exactly.
  const composed = {
    ...byName.ptCommon,
    ...byName.ptBoot,
    ...byName.ptModels,
    ...byName.ptCapabilities,
    ...byName.ptCommandCenter,
    ...byName.ptChat,
    ...byName.ptChrome,
    ...byName.ptAssistant,
    intro: introPt,
    settings: { ...ptSettingsA, ...ptSettingsB }
  }

  const flat = flatten(composed)
  const ref = refKeys('locales/_keys.desktop.json')
  const kept = {}
  const dropped = []
  for (const [key, value] of Object.entries(flat)) {
    if (ref.has(key)) kept[key] = value
    else dropped.push(key)
  }

  writeFileSync(join(PACK, 'locales/pt-br.desktop.yaml'), renderYaml(kept), 'utf8')
  writeFileSync(join(PACK, 'locales/pt-br.yaml'), upstream('locales/pt.yaml'), 'utf8')
  writeFileSync(join(PACK, 'locales/pt-br.tui.yaml'), upstream('locales/pt.tui.yaml'), 'utf8')
  writeFileSync(join(TMP, 'dropped.json'), JSON.stringify(dropped, null, 2), 'utf8')

  console.log(`overrides flattened : ${Object.keys(flat).length}`)
  console.log(`reference keys      : ${ref.size}`)
  console.log(`kept in pack        : ${Object.keys(kept).length}`)
  console.log(`dropped (dead here) : ${dropped.length} -> .build/dropped.json`)
}

await main()
