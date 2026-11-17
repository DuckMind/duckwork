export const meta = {
  name: 'static-parallel',
  description: 'Three independent audits at once, then one summary',
}

phase('Audit')
const audits = await parallel([
  () => agent('Audit src/auth/ for missing permission checks.', { label: 'auth', phase: 'Audit' }),
  () => agent('Audit src/db/ for unparameterised SQL.', { label: 'db', phase: 'Audit' }),
  () => agent('Audit src/api/ for unvalidated request bodies.', { label: 'api', phase: 'Audit' }),
])

phase('Report')
const summary = await agent(`Summarise these three audit results into one prioritised list:\n${audits}`, { label: 'summary' })

return summary
