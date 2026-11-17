export const meta = {
  name: 'date-now',
  description: 'Stamp the report with the current time',
}

const stamp = Date.now()
const report = await agent(`Write the nightly report. Generated at ${stamp}.`, { label: 'report' })

return report
