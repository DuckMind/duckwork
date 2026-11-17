/**
 * Sketch Pad — draw with the mouse, confirm, attach PNG on the next chat send.
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/sketch-pad/.
 */

import { host } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useEffect, useRef, useState } from 'react'

const pending = { path: null, thumb: null }
const listeners = new Set()

function bump() {
  listeners.forEach((fn) => fn())
}

function setPending(next) {
  pending.path = next && next.path ? next.path : null
  pending.thumb = next && next.thumb ? next.thumb : null
  bump()
}

function usePending() {
  const [, setTick] = useState(0)
  useEffect(() => {
    const on = () => setTick((n) => n + 1)
    listeners.add(on)
    return () => listeners.delete(on)
  }, [])
  return pending
}

function SketchCanvas({ canvasRef, dirtyRef }) {
  const drawing = useRef(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx2d = canvas.getContext('2d')
    if (!ctx2d) return undefined

    const resize = () => {
      const parent = canvas.parentElement
      const w = Math.max(200, Math.floor((parent && parent.clientWidth) || 240))
      const h = 220
      const prev = canvas.toDataURL()
      canvas.width = w
      canvas.height = h
      ctx2d.fillStyle = '#f7f7f4'
      ctx2d.fillRect(0, 0, w, h)
      if (dirtyRef.current) {
        const img = new Image()
        img.onload = () => ctx2d.drawImage(img, 0, 0, w, h)
        img.src = prev
      }
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [canvasRef, dirtyRef])

  const pos = (event) => {
    const canvas = canvasRef.current
    const box = canvas.getBoundingClientRect()
    return {
      x: ((event.clientX - box.left) / box.width) * canvas.width,
      y: ((event.clientY - box.top) / box.height) * canvas.height,
    }
  }

  const start = (event) => {
    event.preventDefault()
    const canvas = canvasRef.current
    const ctx2d = canvas && canvas.getContext('2d')
    if (!ctx2d) return
    try {
      canvas.setPointerCapture(event.pointerId)
    } catch {
      /* older hosts */
    }
    drawing.current = true
    dirtyRef.current = true
    const p = pos(event)
    ctx2d.strokeStyle = '#111111'
    ctx2d.lineWidth = 3
    ctx2d.lineCap = 'round'
    ctx2d.lineJoin = 'round'
    ctx2d.beginPath()
    ctx2d.moveTo(p.x, p.y)
  }

  const move = (event) => {
    if (!drawing.current) return
    const canvas = canvasRef.current
    const ctx2d = canvas && canvas.getContext('2d')
    if (!ctx2d) return
    const p = pos(event)
    ctx2d.lineTo(p.x, p.y)
    ctx2d.stroke()
  }

  const end = () => {
    drawing.current = false
  }

  return jsx('canvas', {
    ref: canvasRef,
    onPointerDown: start,
    onPointerMove: move,
    onPointerUp: end,
    onPointerLeave: end,
    style: {
      width: '100%',
      height: 220,
      display: 'block',
      borderRadius: 8,
      border: '1px solid var(--ui-stroke-secondary)',
      cursor: 'crosshair',
      touchAction: 'none',
      background: '#f7f7f4',
    },
  })
}

function SketchPane({ ctx }) {
  const canvasRef = useRef(null)
  const dirtyRef = useRef(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  const clearPad = () => {
    const canvas = canvasRef.current
    const ctx2d = canvas && canvas.getContext('2d')
    if (!ctx2d || !canvas) return
    ctx2d.fillStyle = '#f7f7f4'
    ctx2d.fillRect(0, 0, canvas.width, canvas.height)
    dirtyRef.current = false
    setPending(null)
    setStatus('')
  }

  const confirm = async () => {
    const canvas = canvasRef.current
    if (!canvas || !dirtyRef.current) {
      setStatus('Draw something first.')
      return
    }
    setBusy(true)
    setStatus('')
    try {
      const dataUrl = canvas.toDataURL('image/png')
      const saved = await ctx.rest('/save', {
        method: 'POST',
        body: { png_base64: dataUrl },
      })
      if (!saved || !saved.ok || !saved.path) {
        setStatus((saved && saved.error) || 'Could not save sketch.')
        return
      }
      setPending({ path: saved.path, thumb: dataUrl })
      setStatus('Ready. Send a chat message to attach this sketch.')
      host.notify({
        kind: 'info',
        message: 'Sketch queued. Send your next message to attach it.',
      })
    } catch (err) {
      setStatus('Backend unreachable. Enable sketch-pad and restart the gateway.')
    } finally {
      setBusy(false)
    }
  }

  return jsxs('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      padding: 12,
      height: '100%',
      color: 'var(--ui-text-secondary)',
      fontSize: 13,
    },
    children: [
      jsx('div', {
        style: { fontWeight: 600 },
        children: 'Sketch Pad',
      }),
      jsx('div', {
        style: { fontSize: 12, color: 'var(--ui-text-tertiary)', lineHeight: 1.45 },
        children: 'Draw a shape, then confirm. It attaches to your next chat send.',
      }),
      jsx(SketchCanvas, { canvasRef, dirtyRef }),
      jsxs('div', {
        style: { display: 'flex', gap: 8 },
        children: [
          jsx('button', {
            type: 'button',
            disabled: busy,
            onClick: confirm,
            style: {
              flex: 1,
              padding: '6px 10px',
              fontSize: 12,
              cursor: busy ? 'wait' : 'pointer',
              color: 'var(--ui-text-secondary)',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary)',
              borderRadius: 6,
            },
            children: busy ? 'Saving…' : 'Confirm',
          }),
          jsx('button', {
            type: 'button',
            onClick: clearPad,
            style: {
              padding: '6px 10px',
              fontSize: 12,
              cursor: 'pointer',
              color: 'var(--ui-text-tertiary)',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary)',
              borderRadius: 6,
            },
            children: 'Clear',
          }),
        ],
      }),
      status
        ? jsx('div', {
            style: { fontSize: 12, color: 'var(--ui-text-tertiary)' },
            children: status,
          })
        : null,
    ],
  })
}

function SketchBanner() {
  const state = usePending()
  if (!state.path) return null
  return jsxs('div', {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 10px',
      fontSize: 12,
      color: 'var(--ui-text-secondary)',
    },
    children: [
      state.thumb
        ? jsx('img', {
            src: state.thumb,
            alt: '',
            style: {
              width: 36,
              height: 28,
              objectFit: 'cover',
              borderRadius: 4,
              border: '1px solid var(--ui-stroke-secondary)',
            },
          })
        : null,
      jsx('span', { children: 'Sketch will attach when you send.' }),
      jsx('button', {
        type: 'button',
        onClick: () => setPending(null),
        style: {
          marginLeft: 'auto',
          fontSize: 11,
          cursor: 'pointer',
          color: 'var(--ui-text-tertiary)',
          background: 'transparent',
          border: 'none',
        },
        children: 'Remove',
      }),
    ],
  })
}

function SketchChip() {
  const state = usePending()
  return jsx('button', {
    type: 'button',
    title: 'Sketch Pad',
    onClick: () =>
      host.notify({
        kind: 'info',
        message: state.path ? 'Sketch queued for the next send.' : 'Draw in the Sketch Pad pane, then Confirm.',
      }),
    style: {
      padding: '0 6px',
      fontSize: '0.6875rem',
      color: 'var(--ui-text-tertiary)',
      background: 'transparent',
      border: 'none',
      cursor: 'pointer',
    },
    children: state.path ? 'sk •' : 'sk',
  })
}

export default {
  id: 'sketch-pad',
  name: 'Sketch Pad',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'sketch pad',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(SketchPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 128,
      render: () => jsx(SketchChip, {}),
    })
    ctx.register({
      id: 'banner',
      area: 'composer.top',
      render: () => jsx(SketchBanner, {}),
    })
    ctx.register({
      id: 'attach-on-send',
      area: 'composer.middleware',
      data: {
        handler: (draft) => {
          if (!pending.path) return draft
          const extra = {
            id: 'image:' + pending.path,
            kind: 'image',
            label: 'sketch.png',
            detail: pending.path,
            path: pending.path,
            previewUrl: pending.thumb || undefined,
            thumbnailUrl: pending.thumb || undefined,
          }
          const attachments = Array.isArray(draft.attachments) ? draft.attachments.slice() : []
          attachments.push(extra)
          setPending(null)
          return { text: draft.text, attachments }
        },
      },
    })
  },
}
