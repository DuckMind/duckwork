/**
 * File Tray — paths this Duckwork session touched (read / write / patch).
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/file-tray/.
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

function insertPath(path) {
  const text = (path || '').trim()
  if (!text) return
  try {
    window.dispatchEvent(
      new CustomEvent('duckwork:composer-insert', {
        detail: { mode: 'block', target: 'main', text },
      }),
    )
  } catch {
    /* older hosts */
  }
  if (host.os && typeof host.os.writeClipboard === 'function') {
    void host.os.writeClipboard(text)
  }
  host.notify({
    kind: 'info',
    message: 'Path inserted into the chat box. Paste (Ctrl+V) if it did not appear.',
  })
}

function copyPath(path) {
  const text = (path || '').trim()
  if (!text) return
  if (host.os && typeof host.os.writeClipboard === 'function') {
    void host.os.writeClipboard(text).then((ok) => {
      host.notify({
        kind: 'info',
        message: ok === false ? 'Could not copy path.' : 'Path copied.',
      })
    })
    return
  }
  host.notify({ kind: 'info', message: 'Clipboard not available.' })
}

function revealPath(ctx, path) {
  const text = (path || '').trim()
  if (!text) return
  if (ctx.os && typeof ctx.os.revealPath === 'function') {
    void ctx.os.revealPath(text).then((ok) => {
      if (ok === false) {
        host.notify({ kind: 'info', message: 'Could not reveal path in Explorer.' })
      }
    })
    return
  }
  host.notify({ kind: 'info', message: 'Reveal not available on this host.' })
}

function useTray(ctx) {
  return useQuery({
    queryKey: ['file-tray', 'tray'],
    queryFn: () => ctx.rest('/tray'),
    refetchInterval: 4000,
  })
}

function TrayPane({ ctx }) {
  const query = useTray(ctx)
  const mutate = useMutation({
    mutationFn: () => ctx.rest('/clear', { method: 'POST', body: {} }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['file-tray'] })
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
            children: 'File Tray',
          }),
          jsx('div', {
            style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
            children: items.length ? `${items.length}` : '',
          }),
        ],
      }),
      jsx('div', {
        style: { fontSize: 12, color: 'var(--ui-text-tertiary)', lineHeight: 1.45 },
        children: 'Paths the agent read, wrote, or patched this session. Click a name to insert it.',
      }),
      query.isLoading
        ? jsx('div', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Loading…' })
        : null,
      query.error
        ? jsx('div', {
            style: { fontSize: 12 },
            children: 'Backend unreachable. Enable file-tray and restart the gateway.',
          })
        : null,
      !query.isLoading && !items.length
        ? jsx('div', {
            style: { color: 'var(--ui-text-tertiary)' },
            children: 'No files yet. Agent read_file / write_file / patch will land here.',
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
                    title: it.path,
                    onClick: () => insertPath(it.path),
                    style: {
                      textAlign: 'left',
                      fontSize: 13,
                      fontWeight: 600,
                      color: 'var(--ui-text-secondary)',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                      wordBreak: 'break-all',
                    },
                    children: it.name || it.path,
                  }),
                  jsx('div', {
                    style: {
                      fontSize: 11,
                      color: 'var(--ui-text-tertiary)',
                      wordBreak: 'break-all',
                    },
                    children: it.path,
                  }),
                  jsxs('div', {
                    style: {
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      fontSize: 11,
                      color: 'var(--ui-text-tertiary)',
                    },
                    children: [
                      jsx('span', { children: it.action || it.tool || '' }),
                      it.ts ? jsx('span', { children: `· ${formatTime(it.ts)}` }) : null,
                      jsx('button', {
                        type: 'button',
                        onClick: () => copyPath(it.path),
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
                      jsx('button', {
                        type: 'button',
                        onClick: () => revealPath(ctx, it.path),
                        style: {
                          fontSize: 11,
                          color: 'var(--ui-text-tertiary)',
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          padding: 0,
                        },
                        children: 'reveal',
                      }),
                    ],
                  }),
                ],
              },
              it.path,
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
  const n = query.data && typeof query.data.count === 'number' ? query.data.count : 0

  return jsx('button', {
    type: 'button',
    title: 'File Tray',
    onClick: () => {
      host.notify({
        kind: 'info',
        message: n ? `File Tray has ${n} path${n === 1 ? '' : 's'}.` : 'File Tray is empty.',
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
    children: n ? `ft ${n}` : 'ft',
  })
}

export default {
  id: 'file-tray',
  name: 'File Tray',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'file tray',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(TrayPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 125,
      render: () => jsx(TrayChip, { ctx }),
    })
  },
}
