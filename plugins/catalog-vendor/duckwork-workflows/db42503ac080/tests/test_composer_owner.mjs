import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const tmp = mkdtempSync(join(tmpdir(), 'wf-composer-'))
try {
  const sdk = join(tmp, 'sdk.mjs'), react = join(tmp, 'react.mjs'), jsx = join(tmp, 'jsx.mjs')
  writeFileSync(sdk, `export const host = { composer: {} }; export const atom = x => x;
    export const Badge='',Button='',cn=()=>'',Codicon='',COMPOSER_AREAS={},EmptyState='',PANES_AREA='',PanelListRow='',PanelPill='',PanelSectionLabel='',ROUTES_AREA='',ScrollArea='',StatusDot='',TRANSCRIPT_DIRECTIVE_AREA='',useMutation=()=>{},useQuery=()=>{},useQueryClient=()=>{},useValue=()=>{};`)
  writeFileSync(react, 'export const useEffect=()=>{},useId=()=>{},useRef=()=>{},useState=()=>{};')
  writeFileSync(jsx, 'export const Fragment="",jsx=()=>{},jsxs=()=>{};')
  let src = readFileSync(new URL('../desktop/plugin.js', import.meta.url), 'utf8')
  for (const [name, file] of [['@duckwork/plugin-sdk',sdk],['react',react],['react/jsx-runtime',jsx]])
    src = src.replaceAll(`'${name}'`, JSON.stringify(pathToFileURL(file).href))
  const mod = join(tmp, 'plugin.mjs'); writeFileSync(mod, src)
  const { nudgeOwner } = await import(pathToFileURL(mod).href)
  const { host } = await import(pathToFileURL(sdk).href)
  const calls = []
  const owner = { session_id: 'runtime-owner' }
  host.openSession = async id => { calls.push(['open', id]) }
  host.composer.submit = (id, text) => { calls.push(['submit', id, text]); return true }
  assert.equal(await nudgeOwner(owner, 'resume'), 'submitted')
  assert.deepEqual(calls, [['open','runtime-owner'],['submit','runtime-owner','resume']])
  calls.length = 0
  host.composer.submit = () => false
  host.composer.insertText = () => { throw Error('must not insert when submit exists') }
  assert.equal(await nudgeOwner(owner, 'resume'), 'unavailable')
  delete host.composer.submit
  host.composer.insertText = async (id,text) => { calls.push(['insert',id,text]); return true }
  assert.equal(await nudgeOwner(owner, 'resume'), 'drafted')
  assert.deepEqual(calls.at(-1), ['insert','runtime-owner','resume'])
  delete host.composer.insertText
  assert.equal(await nudgeOwner(owner, 'resume'), 'no-sdk')
  assert.equal(await nudgeOwner({}, 'resume'), 'no-owner')
  host.composer.submit = () => { throw Error('not available') }
  assert.equal(await nudgeOwner(owner, 'resume'), 'unavailable')
  console.log('ALL PASS test_composer_owner (visible submit, draft fallback, fail-closed)')
} finally { rmSync(tmp, { recursive: true, force: true }) }
