// devkit Desktop half: the Scratchpad tab (beside Files) and the buffer viewer.
// The tab groups chats by last activity like the session sidebar. A chat title opens the chat
// (host.openSession); a file name opens the buffer in a main-workspace tab (host.openWorkspace)
// with line numbers and Edit/Save. Chats the backend reports as deleted (``exists === false``)
// sit in their own group; unknown is never treated as deleted.
import { Button, ConfirmDialog, EmptyState, host } from '@duckwork/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

let rest = null
const refreshListeners = new Set()
const notifyRefresh = () => refreshListeners.forEach((fn) => fn())

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December']

function fmtBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

// Same buckets as the chat sidebar: Today, Yesterday, Earlier this week, Last week, then months.
function bucketOf(seconds, now = new Date()) {
  const day = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const weekStart = new Date(day)
  weekStart.setDate(day.getDate() - ((day.getDay() + 6) % 7))
  const lastWeekStart = new Date(weekStart)
  lastWeekStart.setDate(weekStart.getDate() - 7)
  const t = new Date(seconds * 1000)
  if (t >= day) return 'Today'
  const yesterday = new Date(day)
  yesterday.setDate(day.getDate() - 1)
  if (t >= yesterday) return 'Yesterday'
  if (t >= weekStart) return 'Earlier this week'
  if (t >= lastWeekStart) return 'Last week'
  return t.getFullYear() === now.getFullYear() ? MONTHS[t.getMonth()] : `${MONTHS[t.getMonth()]} ${t.getFullYear()}`
}

function groupRows(rows) {
  const groups = []
  const byLabel = new Map()
  for (const row of rows) {
    const label = row.exists === false ? 'Deleted chats' : bucketOf(row.last_active)
    if (!byLabel.has(label)) {
      byLabel.set(label, [])
      groups.push(label)
    }
    byLabel.get(label).push(row)
  }
  const ordered = groups.filter((g) => g !== 'Deleted chats')
  if (byLabel.has('Deleted chats')) ordered.push('Deleted chats')
  return ordered.map((label) => ({ label, rows: byLabel.get(label) }))
}

async function loadTitles() {
  const titles = new Map()
  for (const scope of ['live', 'stored']) {
    try {
      const res = await host.request('session.list', { scope, limit: 200, include_hidden: true })
      for (const row of res?.sessions || []) {
        for (const id of [row.id, row.session_id]) if (id && !titles.has(id)) titles.set(id, row.title || '')
      }
    } catch {
      // titles are cosmetic; the backend decides what is deleted
    }
  }
  return titles
}

const bufferUrl = (dir, name) => `/sessions/${encodeURIComponent(dir)}/buffers/${encodeURIComponent(name)}`

function BufferView({ dir, name, sessionId, title, deleted }) {
  const [buffer, setBuffer] = useState(null)
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setBuffer(await rest(bufferUrl(dir, name)))
    } catch (e) {
      setError(String(e?.message || e))
    }
  }, [dir, name])

  useEffect(() => {
    void load()
  }, [load])

  const save = async () => {
    try {
      await rest(bufferUrl(dir, name), { method: 'PUT', body: { content: draft } })
      setDraft(null)
      await load()
      notifyRefresh()
      host.notify({ kind: 'success', message: `Saved ${name}` })
    } catch (e) {
      host.notify({ kind: 'error', message: `Could not save ${name}: ${e?.message || e}` })
    }
  }

  const editing = draft !== null
  const lines = (buffer?.content ?? '').split('\n')
  if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop()

  const toolbar = jsxs('div', {
    className: 'flex items-center gap-2 border-b border-(--ui-stroke-secondary) px-3 py-1.5 text-xs',
    children: [
      jsx('span', { className: 'font-mono text-(--ui-text-secondary)', children: name }),
      jsx('span', { className: 'truncate text-(--ui-text-tertiary)', children: deleted ? '· deleted chat' : title ? `· ${title}` : '' }),
      jsx('span', { className: 'mr-auto' }),
      !deleted && sessionId
        ? jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => void host.openSession(sessionId), children: 'Open chat' })
        : null,
      editing
        ? jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => setDraft(null), children: 'Cancel' })
        : jsx(Button, { size: 'xs', variant: 'ghost', onClick: () => void load(), children: 'Reload' }),
      editing
        ? jsx(Button, { size: 'xs', onClick: () => void save(), children: 'Save' })
        : jsx(Button, { size: 'xs', variant: 'ghost', disabled: !buffer, onClick: () => setDraft(buffer?.content ?? ''), children: 'Edit' })
    ]
  })

  const body = error
    ? jsx(EmptyState, { title: 'Could not open this buffer', description: error })
    : editing
      ? jsx('textarea', {
          className: 'h-full w-full resize-none bg-transparent p-3 font-mono text-xs leading-5 outline-none',
          spellCheck: false,
          value: draft,
          onChange: (e) => setDraft(e.target.value)
        })
      : jsx('div', {
          className: 'grid font-mono text-xs leading-5',
          style: { gridTemplateColumns: 'auto 1fr' },
          children: lines.flatMap((line, i) => [
            jsx('span', { className: 'select-none pr-3 pl-3 text-right text-(--ui-text-quaternary)', children: i + 1 }, `n${i}`),
            jsx('span', { className: 'whitespace-pre pr-3', children: line || ' ' }, `l${i}`)
          ])
        })

  return jsxs('div', {
    className: 'flex h-full flex-col overflow-hidden',
    children: [toolbar, jsx('div', { className: 'min-h-0 flex-1 overflow-auto py-2', children: body })]
  })
}

function openBuffer(row, name, title) {
  const props = { dir: row.dir, name, sessionId: row.session_id, title, deleted: row.exists === false }
  if (typeof host.openWorkspace === 'function') {
    host.openWorkspace(`devkit-buffer-${row.dir}-${name}`, {
      title: name,
      minWidth: 320,
      render: () => jsx(BufferView, props)
    })
    return true
  }
  return false
}

function ScratchpadPane({ ctx }) {
  const [rows, setRows] = useState(null)
  const [titles, setTitles] = useState(new Map())
  const [error, setError] = useState('')
  const [inline, setInline] = useState(null)
  const [confirm, setConfirm] = useState(null)

  const refresh = useCallback(async () => {
    setError('')
    try {
      const [inv, names] = await Promise.all([rest('/sessions'), loadTitles()])
      setRows(inv.sessions || [])
      setTitles(names)
    } catch (e) {
      setError(String(e?.message || e))
      setRows([])
    }
  }, [])

  useEffect(() => {
    void refresh()
    refreshListeners.add(refresh)
    const stopTimer = ctx.setInterval(() => void refresh(), 30000)
    return () => {
      refreshListeners.delete(refresh)
      stopTimer()
    }
  }, [refresh, ctx])

  const act = async (fn) => {
    try {
      await fn()
    } catch (e) {
      host.notify({ kind: 'error', message: `Scratchpad: ${e?.message || e}` })
    }
    await refresh()
  }

  const deleted = (rows || []).filter((r) => r.exists === false)

  if (inline) {
    return jsxs('div', {
      className: 'flex h-full flex-col',
      children: [
        jsx(Button, { size: 'xs', variant: 'ghost', className: 'self-start m-1', onClick: () => setInline(null), children: '‹ Back' }),
        jsx('div', { className: 'min-h-0 flex-1', children: jsx(BufferView, inline) })
      ]
    })
  }

  const header = jsxs('div', {
    className: 'flex items-center gap-1 px-3 pt-2 pb-1',
    children: [
      jsx('div', { className: 'mr-auto text-xs font-semibold tracking-wide text-(--ui-text-secondary)', children: 'SCRATCHPAD' }),
      jsx(Button, { size: 'micro', variant: 'ghost', title: 'Refresh', onClick: () => void refresh(), children: '↻' }),
      jsx(Button, {
        size: 'micro',
        variant: 'ghost',
        disabled: !rows || rows.length === 0,
        title: 'Remove every buffer of every chat',
        onClick: () => setConfirm({ kind: 'all' }),
        children: 'Clear all'
      })
    ]
  })

  const groups = groupRows(rows || [])
  const list =
    rows === null
      ? jsx('div', { className: 'p-3 text-xs text-(--ui-text-tertiary)', children: 'Loading…' })
      : rows.length === 0
        ? jsx(EmptyState, { title: error ? 'Could not load the scratchpad' : 'No drafts yet', description: error || 'Drafts the agent writes appear here, by chat.' })
        : groups.map((group) =>
            jsxs(
              'div',
              {
                className: 'pb-1',
                children: [
                  jsxs('div', {
                    className: 'flex items-center px-3 pt-2 pb-0.5 text-[0.65rem] font-semibold tracking-wider text-(--ui-text-quaternary) uppercase',
                    children: [
                      jsx('span', { className: 'mr-auto', children: group.label }),
                      group.label === 'Deleted chats'
                        ? jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => setConfirm({ kind: 'deleted' }), children: 'Clear' })
                        : null
                    ]
                  }),
                  ...group.rows.map((row) => {
                    const title = titles.get(row.session_id) || ''
                    const isDeleted = row.exists === false
                    return jsxs(
                      'div',
                      {
                        className: 'px-3 py-0.5',
                        children: [
                          jsxs('div', {
                            className: 'flex items-center gap-1',
                            children: [
                              jsx('button', {
                                type: 'button',
                                disabled: isDeleted,
                                className: 'min-w-0 flex-1 truncate text-left text-sm text-(--ui-text-primary) hover:underline disabled:no-underline disabled:text-(--ui-text-tertiary)',
                                title: isDeleted ? 'This chat was deleted' : `Open chat · ${row.buffers.length} file(s) · ${fmtBytes(row.bytes)}`,
                                onClick: () => void host.openSession(row.session_id),
                                children: isDeleted ? 'Deleted chat' : title || 'Untitled chat'
                              }),
                              jsx(Button, {
                                size: 'micro',
                                variant: 'ghost',
                                className: 'text-(--ui-text-quaternary)',
                                title: 'Delete this chat’s drafts',
                                onClick: () => setConfirm({ kind: 'row', row, title }),
                                children: '×'
                              })
                            ]
                          }),
                          ...row.buffers.map((b) =>
                            jsxs(
                              'div',
                              {
                                className: 'flex items-center gap-1 pl-3',
                                children: [
                                  jsx('button', {
                                    type: 'button',
                                    className: 'min-w-0 flex-1 truncate text-left font-mono text-xs text-(--ui-text-secondary) hover:text-(--ui-text-primary) hover:underline',
                                    title: `Open ${b.name} · ${fmtBytes(b.bytes)}`,
                                    onClick: () => {
                                      if (!openBuffer(row, b.name, title)) {
                                        setInline({ dir: row.dir, name: b.name, sessionId: row.session_id, title, deleted: isDeleted })
                                      }
                                    },
                                    children: b.name
                                  }),
                                  jsx(Button, {
                                    size: 'micro',
                                    variant: 'ghost',
                                    className: 'text-(--ui-text-quaternary)',
                                    title: `Delete ${b.name}`,
                                    onClick: () => void act(() => rest(bufferUrl(row.dir, b.name), { method: 'DELETE' })),
                                    children: '×'
                                  })
                                ]
                              },
                              b.name
                            )
                          )
                        ]
                      },
                      row.dir
                    )
                  })
                ]
              },
              group.label
            )
          )

  const dialog = confirm
    ? jsx(ConfirmDialog, {
        open: true,
        destructive: true,
        onClose: () => setConfirm(null),
        title:
          confirm.kind === 'all'
            ? 'Clear every draft?'
            : confirm.kind === 'deleted'
              ? `Clear drafts of ${deleted.length} deleted chat${deleted.length === 1 ? '' : 's'}?`
              : `Delete the drafts of “${confirm.title || 'this chat'}”?`,
        description: 'Only the scratchpad buffers are removed. Chats are not touched.',
        confirmLabel: 'Delete',
        onConfirm: async () => {
          if (confirm.kind === 'all') await act(() => rest('/clear', { method: 'POST', body: { all: true } }))
          else if (confirm.kind === 'deleted')
            await act(() => rest('/clear', { method: 'POST', body: { dirs: deleted.map((r) => r.dir) } }))
          else await act(() => rest(`/sessions/${encodeURIComponent(confirm.row.dir)}`, { method: 'DELETE' }))
          setConfirm(null)
        }
      })
    : null

  return jsxs('div', {
    className: 'flex h-full flex-col overflow-hidden',
    children: [header, jsx('div', { className: 'min-h-0 flex-1 overflow-y-auto', children: list }), dialog]
  })
}

export default {
  id: 'devkit',
  name: 'devkit',
  register(ctx) {
    rest = ctx.rest
    // Refresh the tab whenever the agent touches the scratchpad.
    ctx.onEvent('tool.complete', (event) => {
      if (event?.payload?.name === 'scratchpad') notifyRefresh()
    })
    ctx.register({
      id: 'scratchpad-files-tab',
      area: 'panes',
      title: 'Scratchpad',
      data: { placement: 'right', dock: { pane: 'files', pos: 'center' } },
      render: () => jsx(ScratchpadPane, { ctx })
    })
  }
}
