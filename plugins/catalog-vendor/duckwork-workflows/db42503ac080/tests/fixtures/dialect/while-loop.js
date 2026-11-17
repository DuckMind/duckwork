export const meta = {
  name: 'while-loop',
  description: 'Keep fixing type errors until the check passes or two rounds make no progress',
}

let round = 0
let lastCount = Infinity
let check = await agent('Run `tsc --noEmit` and return {errors: <count>, sample: [<first 5 lines>]}.', {
  schema: { type: 'object', required: ['errors', 'sample'], properties: { errors: { type: 'integer' }, sample: { type: 'array', items: { type: 'string' } } } },
})

while (check.errors > 0 && round < 8) {
  if (check.errors >= lastCount) {
    round += 1
  }
  lastCount = check.errors
  await agent(`Fix these TypeScript errors:\n${check.sample.join('\n')}`, { label: `fix-${round}` })
  check = await agent('Run `tsc --noEmit` again and return {errors, sample}.', {
    schema: { type: 'object', required: ['errors', 'sample'], properties: { errors: { type: 'integer' }, sample: { type: 'array', items: { type: 'string' } } } },
  })
}

return { rounds: round, remaining: check.errors }
