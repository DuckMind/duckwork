/**
 * Where the node gates find the Duckwork install they verify against (the ESM twin of `env.py`).
 *
 * The gates used to reach the install with `HERE + '../../../duckwork-agent'`, which is right only
 * when this repo sits inside a `plugins/` folder of that install. A clone elsewhere made the
 * preview report "kit stylesheet NOT FOUND" and quietly draw unstyled frames — a warning nobody
 * reads is how a gate stops gatekeeping.
 *
 * Env-first, same table as `env.py`:
 *   DUCKWORK_HOME       the install root           (default: %LOCALAPPDATA%/duckwork, else ~/.duckwork)
 *   DUCKWORK_AGENT_DIR  the core checkout          (default: <DUCKWORK_HOME>/duckwork-agent when present)
 *   DUCKWORK_ELECTRON   the Electron binary        (default: the core's apps/desktop node_modules)
 */
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'

export const DUCKWORK_HOME = process.env.DUCKWORK_HOME
  ? path.resolve(process.env.DUCKWORK_HOME)
  : process.env.LOCALAPPDATA
    ? path.resolve(process.env.LOCALAPPDATA, 'duckwork')
    : path.resolve(homedir(), '.duckwork')

export const CORE_DIR = process.env.DUCKWORK_AGENT_DIR
  ? path.resolve(process.env.DUCKWORK_AGENT_DIR)
  : existsSync(path.join(DUCKWORK_HOME, 'duckwork-agent'))
    ? path.join(DUCKWORK_HOME, 'duckwork-agent')
    : null

export const DESKTOP_APP = CORE_DIR ? path.join(CORE_DIR, 'apps', 'desktop') : null

export const ELECTRON_CANDIDATES = DESKTOP_APP
  ? [
      path.join(DESKTOP_APP, 'node_modules', 'electron', 'dist', 'electron.exe'),
      path.join(DESKTOP_APP, 'node_modules', 'electron', 'dist', 'electron'),
      path.join(DESKTOP_APP, 'node_modules', '.bin', 'electron.cmd'),
      path.join(DESKTOP_APP, 'node_modules', '.bin', 'electron')
    ]
  : []

const firstPresent = candidates => candidates.find(candidate => existsSync(candidate)) || null

export function electronBinary() {
  if (process.env.DUCKWORK_ELECTRON) return path.resolve(process.env.DUCKWORK_ELECTRON)
  return firstPresent(ELECTRON_CANDIDATES)
}

export function describe() {
  return `DUCKWORK_HOME=${DUCKWORK_HOME} · core=${CORE_DIR || 'not found'}`
}
