export const meta = {
  name: 'args-template',
  description: 'Parameterised research: the question and the target dir arrive via args',
}

const survey = await agent(`Survey ${args.dir} and answer: ${args.question}. Return {findings}.`, {
  label: 'survey',
  schema: { type: 'object', required: ['findings'], properties: { findings: { type: 'string' } } },
})

const report = await agent(`Write a one-page report answering "${args.question}" from these findings:\n${survey.findings}`, { label: 'report' })

return report
