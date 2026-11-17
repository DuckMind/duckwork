/**
 * Command Tray — shell commands this Duckwork session ran (terminal tool).
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/command-tray/.
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

function insertText(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return
  try {
    window.dispatchEvent(
      new CustomEvent('duckwork:composer-insert', {
        detail: { mode: 'block', target: 'main', text: trimmed },
      }),
    )
  } catch {
    /* older hosts */
  }
  if (host.os && typeof host.os.writeClipboard === 'function') {
    void host.os.writeClipboard(trimmed)
  }
  host.notify({
    kind: 'info',
    message: 'Command inserted into the chat box. Paste (Ctrl+V) if it did not appear.',
  })
}

function copyText(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return
  if (host.os && typeof host.os.writeClipboard === 'function') {
    void host.os.writeClipboard(trimmed).then((ok) => {
      host.notify({
        kind: 'info',
        message: ok === false ? 'Could not copy command.' : 'Command copied.',
      })
    })
    return
  }
  host.notify({ kind: 'info', message: 'Clipboard not available.' })
}

function statusLabel(it) {
  const status = it.status || 'unknown'
  if (it.exit_code === null || it.exit_code === undefined) return status
  return `${status} ${it.exit_code}`
}

function useTray(ctx) {
  return useQuery({
    queryKey: ['command-tray', 'tray'],
    queryFn: () => ctx.rest('/tray'),
    refetchInterval: 4000,
  })
}

function TrayPane({ ctx }) {
  const query = useTray(ctx)
  const mutate = useMutation({
    mutationFn: () => ctx.rest('/clear', { method: 'POST', body: {} }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['command-tray'] })
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
            children: 'Command Tray',
          }),
          jsx('div', {
            style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
            children: items.length ? `${items.length}` : '',
          }),
        ],
      }),
      jsx('div', {
        style: { fontSize: 12, color: 'var(--ui-text-tertiary)', lineHeight: 1.45 },
        children: 'Shell commands the agent ran this session. Click to insert; does not auto-run.',
      }),
      query.isLoading
        ? jsx('div', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Loading…' })
        : null,
      query.error
        ? jsx('div', {
            style: { fontSize: 12 },
            children: 'Backend unreachable. Enable command-tray and restart the gateway.',
          })
        : null,
      !query.isLoading && !items.length
        ? jsx('div', {
            style: { color: 'var(--ui-text-tertiary)' },
            children: 'No commands yet. Agent terminal tool runs will land here.',
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
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  padding: '6px 0',
                  borderBottom: '1px solid var(--ui-stroke-secondary)',
                },
                children: [
                  jsx('button', {
                    type: 'button',
                    title: it.command,
                    onClick: () => insertText(it.command),
                    style: {
                      textAlign: 'left',
                      fontSize: 12,
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                      fontWeight: 600,
                      color: 'var(--ui-text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                      wordBreak: 'break-all',
                    },
                    children: it.command,
                  }),
                  it.preview
                    ? jsx('div', {
                        style: {
                          fontSize: 11,
                          color: 'var(--ui-text-tertiary)',
                          wordBreak: 'break-all',
                        },
                        children: it.preview,
                      })
                    : null,
                  jsxs('div', {
                    style: {
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      fontSize: 11,
                      color: 'var(--ui-text-tertiary)',
                    },
                    children: [
                      jsx('span', {
                        style: {
                          color:
                            it.status === 'fail'
                              ? 'var(--ui-text-secondary)'
                              : 'var(--ui-text-tertiary)',
                        },
                        children: statusLabel(it),
                      }),
                      it.runs && it.runs > 1 ? jsx('span', { children: `×${it.runs}` }) : null,
                      it.ts ? jsx('span', { children: `· ${formatTime(it.ts)}` }) : null,
                      jsx('button', {
                        type: 'button',
                        onClick: () => copyText(it.command),
                        style: {
                          fontSize: 11,
                          color: 'var(--ui-text-tertiary)',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          padding: 0,
                        },
                        children: 'copy',
                      }),
                    ],
                  }),
                ],
              },
              `${it.command}|${it.ts || ''}`,
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
  const query = useTray(ctx)
  const items = (query.data && query.data.items) || []
  const n = typeof query.data?.count === 'number' ? query.data.count : items.length
  const fails = items.filter((it) => it.status === 'fail').length

  return jsx('button', {
    type: 'button',
    title: 'Command Tray',
    onClick: () => {
      host.notify({
        kind: 'info',
        message: n
          ? `Command Tray has ${n} command${n === 1 ? '' : 's'}${fails ? ` (${fails} fail)` : ''}.`
          : 'Command Tray is empty.',
      })
    },
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '0 6px',
      fontSize: '0.6875rem',
      color: fails ? 'var(--ui-text-secondary)' : 'var(--ui-text-tertiary)',
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
    },
    children: n ? `cmd ${n}` : 'cmd',
  })
}

export default {
  id: 'command-tray',
  name: 'Command Tray',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'command tray',
      data: { placement: 'right', width: '300px' },
      render: () => jsx(TrayPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 127,
      render: () => jsx(TrayChip, { ctx }),
    })
  },
}
