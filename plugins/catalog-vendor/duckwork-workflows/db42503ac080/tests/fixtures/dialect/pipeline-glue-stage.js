export const meta = {
  name: 'pipeline-glue-stage',
  description: 'Verify claims; skip the skeptic stage for anything not confirmed',
}

const extracted = await agent('List every claim in investor_update.md. Return {claims: [{number, text}]}.', {
  schema: { type: 'object', required: ['claims'], properties: { claims: { type: 'array', items: { type: 'object' } } } },
})

const results = await pipeline(
  extracted.claims,
  (claim) => agent(`Verify claim #${claim.number}: ${claim.text}. Return {verdict}.`, {
    label: `verify-${claim.number}`,
    schema: { type: 'object', required: ['verdict'], properties: { verdict: { type: 'string' } } },
  }),
  (verifyResult, claim) => {
    if (!verifyResult || verifyResult.verdict !== 'confirmed') {
      return Promise.resolve(verifyResult ? { ...verifyResult, skeptic_reviewed: false } : null)
    }
    return agent(`Argue against claim #${claim.number}. Return {holds}.`, {
      label: `skeptic-${claim.number}`,
      schema: { type: 'object', required: ['holds'], properties: { holds: { type: 'boolean' } } },
    }).then((skepticResult) => ({ ...verifyResult, skeptic_reviewed: true, holds: skepticResult && skepticResult.holds }))
  },
)

return results
