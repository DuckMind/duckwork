import { host, useValue } from '@duckwork/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const exact = new Intl.NumberFormat('ru-RU')

const compact = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

function formatExact(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? exact.format(value)
    : '-'
}

function SessionTokens() {
  const usage = useValue(host.state.focusedUsage)

  const input = usage?.input ?? null
  const output = usage?.output ?? null
  const total = usage?.total ?? null
  const contextPercent = usage?.context_percent ?? null

  const title = [
    `input: ${formatExact(input)}`,
    `output: ${formatExact(output)}`,
    `total: ${formatExact(total)}`,
    `context: ${contextPercent === null ? '-' : `${contextPercent}%`}`,
  ].join('\n')

  const label =
    total === null
      ? 'Σ — tok'
      : `Σ ${compact.format(total)} tok (${contextPercent === null ? '-' : `${contextPercent}%`})`

  return jsx('span', {
    className:
      'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    title,
    'aria-label': title,
    children: label,
  })
}

const plugin = {
  id: 'session-token-counter',
  name: 'Session Token Counter',

  register(ctx) {
    if (!host.state.focusedUsage) {
      throw new Error(
        'This Duckwork Desktop build does not expose host.state.focusedUsage — update Duckwork to 0.20.2 or newer.'
      )
    }

    ctx.register({
      id: 'session-tokens',
      area: 'statusBar.right',
      order: 135,
      render: () => jsx(SessionTokens, {}),
    })
  },
}

export default plugin
