// Build desktop/plugin.js from src/. The vendored Duckwork synth imports app modules by their `@/` path; this maps
// them to the vendored copy and the shims, so the bundle needs nothing from the app but the plugin SDK and React.
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import * as esbuild from 'esbuild'

const here = path.dirname(fileURLToPath(import.meta.url))
const vendor = path.join(here, 'src', 'vendor')
const MAP = {
  '@/lib/audio-context': path.join(vendor, 'audio-context.ts'),
  '@/store/ambient': path.join(vendor, 'shims', 'ambient.js'),
  '@/store/completion-sound': path.join(vendor, 'shims', 'completion-store.js'),
  '@/store/haptics': path.join(vendor, 'shims', 'haptics.js')
}

await esbuild.build({
  entryPoints: [path.join(here, 'src', 'plugin.jsx')],
  outfile: path.join(here, 'desktop', 'plugin.js'),
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  jsx: 'automatic',
  external: ['@duckwork/plugin-sdk', 'react', 'react/jsx-runtime'],
  legalComments: 'inline',
  logLevel: 'info',
  plugins: [
    {
      name: 'vendored-app-imports',
      setup(build) {
        build.onResolve({ filter: /^@\// }, args => {
          const target = MAP[args.path]
          if (!target) throw new Error(`unmapped app import ${args.path} in ${args.importer}`)
          return { path: target }
        })
      }
    }
  ]
})
