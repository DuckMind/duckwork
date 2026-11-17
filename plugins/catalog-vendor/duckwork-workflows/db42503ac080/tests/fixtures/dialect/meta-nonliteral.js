const base = { description: 'Lint every package' }
export const meta = { name: 'meta-nonliteral', ...base }

const lint = await agent('Run the linter across packages/* and return {clean: boolean}.', {
  schema: { type: 'object', required: ['clean'], properties: { clean: { type: 'boolean' } } },
})

return lint
