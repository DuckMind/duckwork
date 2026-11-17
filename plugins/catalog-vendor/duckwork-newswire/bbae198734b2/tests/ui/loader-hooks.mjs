const STUB_URLS = {
  "@duckwork/plugin-sdk": "file:///home/tony/projects/duckwork-newswire/tests/ui/.stubs/sdk.mjs",
  "react": "file:///home/tony/projects/duckwork-newswire/tests/ui/.stubs/react.mjs",
  "react/jsx-runtime": "file:///home/tony/projects/duckwork-newswire/tests/ui/.stubs/jsx-runtime.mjs"
}
export function resolve(specifier, context, nextResolve) {
  if (STUB_URLS[specifier]) {
    return { url: STUB_URLS[specifier], shortCircuit: true }
  }
  return nextResolve(specifier, context)
}
