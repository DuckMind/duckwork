// Builds desktop/src/plugin.jsx into the committed desktop/plugin.js (plain ESM).
// There is no local node_modules: esbuild is borrowed read-only from a Duckwork
// Desktop checkout. Set DUCKWORK_NODE_MODULES=/path/to/duckwork-desktop/node_modules,
// or DUCKWORK_ESBUILD=/path/to/esbuild/lib/main.js.
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const modules = process.env.DUCKWORK_NODE_MODULES
const esbuildPath = process.env.DUCKWORK_ESBUILD ?? (modules ? join(modules, 'esbuild/lib/main.js') : null)
if (!esbuildPath) {
  console.error('Set DUCKWORK_NODE_MODULES (a Duckwork Desktop node_modules dir) or DUCKWORK_ESBUILD.')
  process.exit(2)
}
const esbuild = await import(pathToFileURL(esbuildPath).href)

const ALLOWED = ['@duckwork/plugin-sdk', 'react', 'react/jsx-runtime']

await esbuild.build({
  entryPoints: [join(here, 'src', 'plugin.jsx')],
  outfile: join(here, 'plugin.js'),
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  jsx: 'automatic',
  external: ALLOWED,
  legalComments: 'none',
  charset: 'utf8',
  banner: {
    js: '// duckwork-office Desk desktop plugin. Built from desktop/src by desktop/build.mjs; do not edit.'
  },
  logLevel: 'info'
})
