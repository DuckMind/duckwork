export const meta = {
  name: 'unknown-option',
  description: 'Migrate one component in an isolated worktree',
}

const done = await agent('Migrate src/components/Button.js to TypeScript.', {
  label: 'button',
  isolation: 'worktree',
})

return done
