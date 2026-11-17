// registerHooks resolve hook for the shared harness: maps '@duckwork/plugin-sdk'
// to the canonical tests/fixtures/sdk-stub.mjs.
export function resolve(specifier, context, next) {
  if (specifier === '@duckwork/plugin-sdk') return { url: new URL('../fixtures/sdk-stub.mjs', import.meta.url).href, shortCircuit: true }
  return next(specifier, context)
}
