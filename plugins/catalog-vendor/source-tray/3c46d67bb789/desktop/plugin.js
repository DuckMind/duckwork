/**
 * Source Tray — URLs this Duckwork session opened (search / extract / browser).
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/source-tray/.
 */

import { host, useQuery, useMutation, queryClient } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

function TrayPane({ ctx }) {
  const query = useQuery({
    queryKey: ['source-tray', 'tray'],
    queryFn: () => ctx.rest('/tray'),
    refetchInterval: 4000,
  })
  const mutate = useMutation({
    mutationFn: () => ctx.rest('/clear', { method: 'POST', body: {} }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['source-tray'] })
    },
  })

  const items = (query.data && query.data.items) || []

  return jsxs('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      padding: 12,
      height: '100%',
      overflow: 'auto',
      fontSize: 13,
      color: 'var(--ui-text-secondary)',
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' },
        children: [
          jsx('div', {
            style: { fontWeight: 600, color: 'var(--ui-text-secondary)' },
            children: 'Source Tray',
          }),
          jsx('div', {
            style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
            children: items.length ? `${items.length}` : '',
          }),
        ],
      }),
      query.isLoading
        ? jsx('div', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Loading…' })
        : null,
      query.error
        ? jsx('div', {
            style: { fontSize: 12 },
            children: 'Backend unreachable. Enable source-tray in plugins.enabled and restart the gateway.',
          })
        : null,
      !query.isLoading && !items.length
        ? jsx('div', {
            style: { color: 'var(--ui-text-tertiary)' },
            children: 'No URLs yet. Agent web_search / web_extract / browser_navigate will land here.',
          })
        : null,
      jsx('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 10 },
        children: items
          .slice()
          .reverse()
          .map((it) =>
            jsxs(
              'div',
              {
                style: { display: 'flex', flexDirection: 'column', gap: 2 },
                children: [
                  jsx('div', {
                    style: { color: 'var(--ui-text-secondary)', lineHeight: 1.35 },
                    children: it.title || it.url,
                  }),
                  jsx('div', {
                    style: {
                      fontSize: 11,
                      color: 'var(--ui-text-tertiary)',
                      wordBreak: 'break-all',
                    },
                    children: it.url,
                  }),
                  jsxs('div', {
                    style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
                    children: [it.tool || '', it.ts ? ` · ${formatTime(it.ts)}` : ''],
                  }),
                ],
              },
              it.url,
            ),
          ),
      }),
      items.length
        ? jsx('button', {
            type: 'button',
            disabled: mutate.isPending,
            onClick: () => mutate.mutate(),
            style: {
              alignSelf: 'flex-start',
              fontSize: 12,
              padding: '4px 8px',
              border: '1px solid var(--ui-stroke-secondary)',
              background: 'transparent',
              color: 'var(--ui-text-secondary)',
              borderRadius: 4,
              cursor: mutate.isPending ? 'wait' : 'pointer',
            },
            children: mutate.isPending ? 'Clearing…' : 'Clear tray',
          })
        : null,
    ],
  })
}

function TrayChip({ ctx }) {
  const query = useQuery({
    queryKey: ['source-tray', 'tray'],
    queryFn: () => ctx.rest('/tray'),
    refetchInterval: 8000,
  })
  const n = query.data && typeof query.data.count === 'number' ? query.data.count : 0

  return jsxs('button', {
    type: 'button',
    title: 'Source Tray',
    onClick: () => {
      host.notify({
        kind: 'info',
        message: n ? `Source Tray has ${n} URL${n === 1 ? '' : 's'}.` : 'Source Tray is empty.',
      })
    },
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '0 6px',
      fontSize: '0.6875rem',
      color: 'var(--ui-text-tertiary)',
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
    },
    children: [
      jsx('span', {
        children: n ? `src ${n}` : 'src',
      }),
    ],
  })
}

export default {
  id: 'source-tray',
  name: 'Source Tray',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'source tray',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(TrayPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 126,
      render: () => jsx(TrayChip, { ctx }),
    })
  },
}
