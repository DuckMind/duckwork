/**
 * Prompt Tray — saved snippets, click to insert into the Duckwork composer.
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/prompt-tray/.
 */

import { host, useQuery, useMutation, queryClient } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState } from 'react'

function insertIntoComposer(text) {
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
    message: 'Prompt inserted into the chat box. Paste (Ctrl+V) if it did not appear.',
  })
}

function usePrompts(ctx) {
  return useQuery({
    queryKey: ['prompt-tray', 'prompts'],
    queryFn: () => ctx.rest('/prompts'),
    refetchInterval: 8000,
  })
}

function TrayPane({ ctx }) {
  const query = usePrompts(ctx)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const addMut = useMutation({
    mutationFn: () => ctx.rest('/add', { method: 'POST', body: { title, body } }),
    onSettled: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['prompt-tray'] })
      if (saved && saved.ok) {
        setTitle('')
        setBody('')
      }
    },
  })
  const delMut = useMutation({
    mutationFn: (id) => ctx.rest('/delete', { method: 'POST', body: { id } }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['prompt-tray'] })
    },
  })

  const items = (query.data && query.data.items) || []
  const addError = addMut.data && addMut.data.ok === false ? addMut.data.error : ''

  return jsxs('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
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
          jsx('div', { style: { fontWeight: 600 }, children: 'Prompt Tray' }),
          jsx('div', {
            style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
            children: items.length ? `${items.length}` : '',
          }),
        ],
      }),
      jsx('div', {
        style: { fontSize: 12, color: 'var(--ui-text-tertiary)', lineHeight: 1.45 },
        children: 'Click a prompt to drop it into the chat box.',
      }),
      query.isLoading ? jsx('div', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Loading…' }) : null,
      query.error
        ? jsx('div', {
            style: { fontSize: 12 },
            children: 'Backend unreachable. Enable prompt-tray and restart the gateway.',
          })
        : null,
      jsx('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 8 },
        children: items.map((it) =>
          jsxs(
            'div',
            {
              style: {
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                padding: '8px 0',
                borderBottom: '1px solid var(--ui-stroke-secondary)',
              },
              children: [
                jsxs('div', {
                  style: { display: 'flex', alignItems: 'center', gap: 8 },
                  children: [
                    jsx('button', {
                      type: 'button',
                      onClick: () => insertIntoComposer(it.body),
                      style: {
                        flex: 1,
                        textAlign: 'left',
                        fontSize: 13,
                        fontWeight: 600,
                        color: 'var(--ui-text-secondary)',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                      },
                      children: it.title,
                    }),
                    jsx('button', {
                      type: 'button',
                      title: 'Delete',
                      onClick: () => delMut.mutate(it.id),
                      style: {
                        fontSize: 11,
                        color: 'var(--ui-text-tertiary)',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                      },
                      children: '×',
                    }),
                  ],
                }),
                jsx('button', {
                  type: 'button',
                  onClick: () => insertIntoComposer(it.body),
                  style: {
                    textAlign: 'left',
                    fontSize: 12,
                    color: 'var(--ui-text-tertiary)',
                    lineHeight: 1.4,
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                  },
                  children: it.body,
                }),
              ],
            },
            it.id,
          ),
        ),
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 },
        children: [
          jsx('input', {
            value: title,
            placeholder: 'Title',
            onChange: (event) => setTitle(event.target.value),
            style: {
              fontSize: 12,
              padding: '6px 8px',
              color: 'var(--ui-text-secondary)',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary)',
              borderRadius: 6,
            },
          }),
          jsx('textarea', {
            value: body,
            placeholder: 'Prompt text',
            rows: 3,
            onChange: (event) => setBody(event.target.value),
            style: {
              fontSize: 12,
              padding: '6px 8px',
              resize: 'vertical',
              color: 'var(--ui-text-secondary)',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary)',
              borderRadius: 6,
            },
          }),
          jsx('button', {
            type: 'button',
            disabled: addMut.isPending || !title.trim() || !body.trim(),
            onClick: () => addMut.mutate(),
            style: {
              alignSelf: 'flex-start',
              fontSize: 12,
              padding: '6px 10px',
              color: 'var(--ui-text-secondary)',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary)',
              borderRadius: 6,
              cursor: addMut.isPending ? 'wait' : 'pointer',
            },
            children: addMut.isPending ? 'Saving…' : 'Add',
          }),
          addError ? jsx('div', { style: { fontSize: 12, color: 'var(--ui-text-tertiary)' }, children: addError }) : null,
        ],
      }),
    ],
  })
}

function TrayChip({ ctx }) {
  const query = usePrompts(ctx)
  const n = query.data && typeof query.data.count === 'number' ? query.data.count : 0
  return jsx('button', {
    type: 'button',
    title: 'Prompt Tray',
    onClick: () => {
      host.notify({
        kind: 'info',
        message: n ? `Prompt Tray has ${n} saved prompt${n === 1 ? '' : 's'}. Click one in the pane.` : 'Prompt Tray is empty.',
      })
    },
    style: {
      padding: '0 6px',
      fontSize: '0.6875rem',
      color: 'var(--ui-text-tertiary)',
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
    },
    children: n ? `pt ${n}` : 'pt',
  })
}

function LeadingChips({ ctx }) {
  const query = usePrompts(ctx)
  const items = ((query.data && query.data.items) || []).slice(0, 3)
  if (!items.length) return null
  return jsxs('div', {
    style: { display: 'inline-flex', gap: 4, alignItems: 'center' },
    children: items.map((it) =>
      jsx(
        'button',
        {
          type: 'button',
          title: it.body,
          onClick: () => insertIntoComposer(it.body),
          style: {
            fontSize: 11,
            padding: '2px 6px',
            color: 'var(--ui-text-tertiary)',
            background: 'transparent',
            border: '1px solid var(--ui-stroke-secondary)',
            borderRadius: 4,
            cursor: 'pointer',
          },
          children: it.title,
        },
        it.id,
      ),
    ),
  })
}

export default {
  id: 'prompt-tray',
  name: 'Prompt Tray',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'prompt tray',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(TrayPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 124,
      render: () => jsx(TrayChip, { ctx }),
    })
    ctx.register({
      id: 'leading',
      area: 'composer.leading',
      render: () => jsx(LeadingChips, { ctx }),
    })
    ctx.register({
      id: 'attach',
      area: 'composer.attachments',
      data: {
        label: 'Prompt Tray',
        icon: 'comment',
        run: ({ insertText }) => {
          const first = (queryClient.getQueryData(['prompt-tray', 'prompts']) || {}).items
          const body = first && first[0] && first[0].body
          if (body && typeof insertText === 'function') {
            insertText(body)
            return
          }
          host.notify({
            kind: 'info',
            message: 'Open the Prompt Tray pane to pick a saved prompt.',
          })
        },
      },
    })
  },
}
