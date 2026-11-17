export const meta = {
  name: 'sequential-awaits',
  description: 'Three agents in a row, each reading one field of the one before',
}

const plan = await agent('Read README.md and propose one refactor. Return {target, rationale}.', {
  label: 'plan',
  schema: { type: 'object', required: ['target', 'rationale'], properties: { target: { type: 'string' }, rationale: { type: 'string' } } },
})

const patch = await agent(`Implement the refactor of ${plan.target}. Rationale: ${plan.rationale}. Return {diff}.`, {
  label: 'patch',
  model: 'sonnet',
  schema: { type: 'object', required: ['diff'], properties: { diff: { type: 'string' } } },
})

const review = await agent(`Review this diff for correctness only:\n${patch.diff}`, { label: 'review' })

return review
