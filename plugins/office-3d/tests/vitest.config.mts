import { fileURLToPath } from 'node:url'
import { defineConfig, mergeConfig } from 'vitest/config'
import desktopConfig from '../../../apps/desktop/vite.config.ts'

const desktopRoot = fileURLToPath(new URL('../../../apps/desktop/', import.meta.url))
export default defineConfig(async env => mergeConfig(await desktopConfig(env), {
  root: desktopRoot,
  test: {
    environment: 'jsdom',
    setupFiles: [desktopRoot + 'vitest.setup.ts'],
    include: [fileURLToPath(new URL('./duckwork-desktop.test.ts', import.meta.url))],
    env: { NODE_ENV: 'development' },
    testTimeout: 15000,
    hookTimeout: 30000
  }
}))
