export const meta = {
  name: 'pipeline-length-template',
  description: 'Verify every claim, then write a summary that cites how many were checked',
}

const extracted = await agent('List every claim in investor_update.md. Return {claims: [{number, text}]}.', {
  schema: { type: 'object', required: ['claims'], properties: { claims: { type: 'array', items: { type: 'object' } } } },
})

const verified = await pipeline(
  extracted.claims,
  (claim) => agent(`Verify claim #${claim.number}: ${claim.text}. Return {verdict}.`, { label: `verify-${claim.number}` }),
)

const summary = await agent(`We verified ${verified.length} claims. Summarise the verdicts:\n${verified}`, { label: 'summary' })

return summary
