#!/usr/bin/env node
/**
 * sync.mjs — keep this repo's plugin.js and the live Duckwork install in lockstep.
 *
 * Why this exists: the copy Duckwork actually loads lives in
 *   <duckwork home>/desktop-plugins/agent-log/plugin.js
 * while development/publishing happens in this repo. Copying by hand drifts.
 *
 * Usage (run from the repo root):
 *   node sync.mjs                 repo  -> live  (guard + backup + copy + md5)
 *   node sync.mjs --check         compare md5 only, change nothing (exit 1 if drift)
 *   node sync.mjs --pull          live  -> repo  (pull live edits back for committing)
 *   node sync.mjs --push "msg"    repo -> live, then git add/commit/push
 *   node sync.mjs --push "msg" --no-sync   commit/push the repo as-is, don't touch live
 *
 * Env: DUCKWORK_HOME overrides the live home (default %LOCALAPPDATA%\duckwork).
 */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'

const REPO_DIR = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(REPO_DIR, 'desktop', 'plugin.js')
const HOME = process.env.DUCKWORK_HOME ||
  (process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'duckwork') : path.join(process.env.USERPROFILE || '', '.duckwork'))
const LIVE_DIR = path.join(HOME, 'desktop-plugins', 'agent-log')
const LIVE = path.join(LIVE_DIR, 'plugin.js')

const argv = process.argv.slice(2)
const CHECK = argv.includes('--check')
const PULL = argv.includes('--pull')
const NO_SYNC = argv.includes('--no-sync')
const pushIdx = argv.indexOf('--push')
const PUSH_MSG = pushIdx !== -1 ? (argv[pushIdx + 1] || '').trim() : ''

const md5 = (p) => crypto.createHash('md5').update(fs.readFileSync(p)).digest('hex')
const stamp = () => new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
const log = (s) => console.log(s)

// Mirror the desktop runtime loader's import scan. A quoted word after
// "from "/"import " anywhere (even a UI string) is an "import" to the loader,
// and the plugin then silently fails to load — never ship a file that fails it.
const LOADER_RE = /(from\s*|import\s*\(\s*|import\s+)(['"])([^'"]+)\2/g
const ALLOWED = new Set(['@duckwork/plugin-sdk', 'react', 'react/jsx-runtime'])
function guardLoadable(file) {
  const src = fs.readFileSync(file, 'utf8')
  const bad = []
  for (const m of src.matchAll(LOADER_RE)) {
    const spec = m[3]
    if (!/^[./]/.test(spec) && !/^[a-z][a-z0-9+.-]*:/i.test(spec) && !ALLOWED.has(spec)) bad.push(spec)
  }
  if (bad.length) {
    log(`\x1b[31mLOAD GUARD FAIL\x1b[0m  ${file} would NOT load in Duckwork: phantom import(s) ${bad.join(', ')}`)
    log('  (a quoted word after `from ` or `import ` is read as an import by the loader)')
    process.exit(2)
  }
}

if (!fs.existsSync(SRC)) { log(`missing source: ${SRC}`); process.exit(2) }

const srcHash = md5(SRC)
const liveExists = fs.existsSync(LIVE)
const liveHash = liveExists ? md5(LIVE) : '(none)'

log(`repo plugin.js   ${srcHash}`)
log(`live plugin.js   ${liveHash}  (${liveExists ? LIVE : 'not installed yet'})`)

if (CHECK) {
  if (!liveExists) { log('\x1b[33mLIVE MISSING\x1b[0m — run `node sync.mjs` to install.'); process.exit(1) }
  if (srcHash === liveHash) { log('\x1b[32mIN SYNC\x1b[0m'); process.exit(0) }
  log('\x1b[33mDRIFT DETECTED\x1b[0m — repo and live differ.'); process.exit(1)
}

if (PULL) {
  // live -> repo (brings edits made against the running install back for commit)
  if (!liveExists) { log('nothing to pull — live file missing.'); process.exit(1) }
  guardLoadable(LIVE)
  fs.copyFileSync(LIVE, SRC)
  log(`\x1b[32mpulled live -> repo\x1b[0m  ${md5(SRC)}`)
} else if (!NO_SYNC) {
  // repo -> live, with a timestamped backup of the file being replaced
  guardLoadable(SRC)
  if (!fs.existsSync(LIVE_DIR)) fs.mkdirSync(LIVE_DIR, { recursive: true })
  if (liveExists) {
    const bakDir = path.join(LIVE_DIR, '.bak')
    fs.mkdirSync(bakDir, { recursive: true })
    const bak = path.join(bakDir, `plugin.js.bak_sync_${stamp()}`)
    fs.copyFileSync(LIVE, bak)
    log(`backed up live   ${bak}`)
  }
  fs.copyFileSync(SRC, LIVE)
  const newHash = md5(LIVE)
  if (newHash !== srcHash) { log(`\x1b[31mCOPY MISMATCH\x1b[0m ${newHash} != ${srcHash}`); process.exit(1) }
  log(`\x1b[32msynced repo -> live\x1b[0m  ${newHash}  — Ctrl+K → Reload desktop plugins in Duckwork`)
}

if (PUSH_MSG || pushIdx !== -1) {
  const msg = PUSH_MSG || `sync ${stamp()}`
  const sh = (cmd) => execSync(cmd, { cwd: REPO_DIR, stdio: 'inherit' })
  // Inline a sane identity if the clone has none, so `--push` works out of the box.
  let name = '', email = ''
  try {
    name = execSync('git config user.name', { cwd: REPO_DIR }).toString().trim()
    email = execSync('git config user.email', { cwd: REPO_DIR }).toString().trim()
  } catch {}
  const ident = name && email ? '' : `-c user.name=PixelAlchemist4 -c user.email=PixelAlchemist4@users.noreply.github.com `
  sh('git add -A')
  // exit 0 when there is nothing to commit (don't fail the whole run)
  try { sh(`git ${ident}commit -m ${JSON.stringify(msg)}`) }
  catch { log('nothing new to commit') }
  sh('git push')
  const sha = execSync('git rev-parse HEAD', { cwd: REPO_DIR }).toString().trim()
  log(`\x1b[32mpushed\x1b[0m ${sha}`)
  log(`catalog pin SHA: ${sha}`)
}
