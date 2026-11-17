export const meta = {
  name: 'args-iterable',
  description: 'One agent per file path passed in via args',
}

const results = await pipeline(args.files, file =>
  agent(`Convert ${file} from JavaScript to TypeScript.`, { label: file }),
)

return results.filter(Boolean)
