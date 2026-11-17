export const meta = {
  name: 'dynamic-agent-count',
  description: 'Spawn one reviewer per distinct owner found in CODEOWNERS, dedup in JS',
}

const owners = await agent('Parse CODEOWNERS and return {entries: [{path, owner}]}.', {
  schema: { type: 'object', required: ['entries'], properties: { entries: { type: 'array', items: { type: 'object', required: ['path', 'owner'], properties: { path: { type: 'string' }, owner: { type: 'string' } } } } } },
})

const distinct = [...new Set(owners.entries.map(e => e.owner))]
const byOwner = distinct.map(owner => () =>
  agent(`Review every path owned by ${owner}: ${owners.entries.filter(e => e.owner === owner).map(e => e.path).join(', ')}`, { label: owner }),
)

const reviews = await parallel(byOwner)

return reviews.map((r, i) => ({ owner: distinct[i], review: r }))
