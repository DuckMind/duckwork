// node:module registerHooks() resolve hook (sync): maps '@duckwork/plugin-sdk' to the test stub.
export function resolve(specifier, context, next) {
  if (specifier === '@duckwork/plugin-sdk') return { url: new URL('./sdk-stub.mjs', import.meta.url).href, shortCircuit: true }
  return next(specifier, context)
}
