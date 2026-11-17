export const meta = {
  name: 'two-stage-pipeline',
  description: 'Extract claims, then verify each, then critique each verification',
  phases: [{ title: 'Extract' }, { title: 'Verify' }, { title: 'Skeptic' }],
}

phase('Extract')
const extracted = await agent('Read investor_update.md and list every factual claim. Return {claims: [{number, text}]}.', {
  label: 'extract',
  schema: { type: 'object', required: ['claims'], properties: { claims: { type: 'array', items: { type: 'object', required: ['number', 'text'], properties: { number: { type: 'integer' }, text: { type: 'string' } } } } } },
})

const results = await pipeline(
  extracted.claims,
  (claim) => agent(`Verify claim #${claim.number} against the source documents: ${claim.text}. Return {number: ${claim.number}, verdict, evidence}.`, {
    label: `verify-${claim.number}`,
    phase: 'Verify',
    schema: { type: 'object', required: ['number', 'verdict', 'evidence'], properties: { number: { type: 'integer' }, verdict: { type: 'string' }, evidence: { type: 'string' } } },
  }),
  (verified) => agent(`A verifier said "${verified.verdict}" for claim #${verified.number} citing: ${verified.evidence}. Argue the opposite; return {holds, why}.`, {
    label: `skeptic-${verified.number}`,
    phase: 'Skeptic',
    schema: { type: 'object', required: ['holds', 'why'], properties: { holds: { type: 'boolean' }, why: { type: 'string' } } },
  }),
)

return results
