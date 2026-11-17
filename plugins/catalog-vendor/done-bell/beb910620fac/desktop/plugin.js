/**
 * Done Bell — notify when a Duckwork turn finishes so you can leave the window.
 *
 * Unified package: copied to $DUCKWORK_HOME/desktop-plugins/done-bell/.
 */

import { host, useQuery, useMutation, queryClient, useValue } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useEffect, useRef } from 'react'

function playChime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const audio = new Ctx()
    const now = audio.currentTime
    const osc = audio.createOscillator()
    const gain = audio.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, now)
    osc.frequency.setValueAtTime(1174.66, now + 0.11)
    gain.gain.setValueAtTime(0.07, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.32)
    osc.connect(gain)
    gain.connect(audio.destination)
    osc.start(now)
    osc.stop(now + 0.34)
  } catch {
    /* no audio */
  }
}

function settingsOf(data) {
  return (data && data.settings) || {}
}

function ring(ctx, settings, title, body) {
  if (settings.muted) return
  if (settings.sound !== false) playChime()
  if (settings.in_app) {
    host.notify({ kind: 'success', title, message: body })
  }
  if (settings.os_notify !== false && ctx.os && typeof ctx.os.notify === 'function') {
    try {
      ctx.os.notify({ title, body })
    } catch {
      /* older hosts */
    }
  }
}

function useBell(ctx) {
  return useQuery({
    queryKey: ['done-bell', 'status'],
    queryFn: () => ctx.rest('/status'),
    refetchInterval: 2500,
  })
}

function BellWatcher({ ctx }) {
  const query = useBell(ctx)
  const busyMap = useValue(host.state.busyBySession) || {}
  const prevMap = useRef(null)
  const prevNeeds = useRef(false)
  const settings = settingsOf(query.data)
  const needsYou = Boolean(query.data && query.data.needs_you)

  useEffect(() => {
    const next = busyMap && typeof busyMap === 'object' ? busyMap : {}
    const prev = prevMap.current
    prevMap.current = next
    if (!prev) return
    const ids = new Set([...Object.keys(prev), ...Object.keys(next)])
    let finished = false
    ids.forEach((id) => {
      if (prev[id] && !next[id]) finished = true
    })
    if (!finished) return
    ring(ctx, settings, 'Duckwork is done', 'The agent finished this turn.')
  }, [busyMap, ctx, settings])

  useEffect(() => {
    const was = prevNeeds.current
    prevNeeds.current = needsYou
    if (!was && needsYou && settings.needs_you !== false) {
      ring(ctx, settings, 'Duckwork needs you', 'Waiting for approval.')
    }
  }, [needsYou, ctx, settings])

  return null
}

function labelFor(busy, needsYou) {
  if (needsYou) return 'needs you'
  if (busy) return 'busy'
  return 'done'
}

function StatusChip({ ctx }) {
  const query = useBell(ctx)
  const busy = useValue(host.state.busy)
  const needsYou = Boolean(query.data && query.data.needs_you)
  const muted = Boolean(settingsOf(query.data).muted)
  const text = muted ? 'muted' : labelFor(busy, needsYou)
  return jsxs('span', {
    style: { display: 'inline-flex', alignItems: 'center' },
    children: [
      jsx(BellWatcher, { ctx }),
      jsx('button', {
        type: 'button',
        title: muted ? 'Done Bell is muted' : 'Done Bell',
        onClick: () => {
          host.notify({
            kind: 'info',
            message: muted
              ? 'Done Bell is muted. Open the pane to unmute.'
              : needsYou
                ? 'Duckwork is waiting for approval.'
                : busy
                  ? 'Duckwork is still working.'
                  : 'Idle. You will get a notify when the next turn finishes.',
          })
        },
        style: {
          padding: '0 6px',
          fontSize: '0.6875rem',
          color: needsYou && !muted ? 'var(--ui-text-secondary)' : 'var(--ui-text-tertiary)',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
        },
        children: text,
      }),
    ],
  })
}

function Toggle({ label, checked, onClick, disabled }) {
  return jsx('button', {
    type: 'button',
    disabled,
    onClick,
    style: {
      fontSize: 12,
      padding: '4px 8px',
      textAlign: 'left',
      color: 'var(--ui-text-secondary)',
      background: 'transparent',
      border: '1px solid var(--ui-stroke-secondary)',
      borderRadius: 6,
      cursor: disabled ? 'wait' : 'pointer',
    },
    children: `${checked ? 'on' : 'off'}  ${label}`,
  })
}

function BellPane({ ctx }) {
  const query = useBell(ctx)
  const busy = useValue(host.state.busy)
  const settings = settingsOf(query.data)
  const needsYou = Boolean(query.data && query.data.needs_you)
  const events = (query.data && query.data.events) || []
  const setMut = useMutation({
    mutationFn: (patch) => ctx.rest('/settings', { method: 'POST', body: patch }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['done-bell'] })
    },
  })
  const testMut = useMutation({
    mutationFn: () => ctx.rest('/test', { method: 'POST', body: {} }),
    onSettled: (data) => {
      queryClient.invalidateQueries({ queryKey: ['done-bell'] })
      ring(ctx, (data && data.settings) || settings, 'Duckwork is done', 'Test ring.')
    },
  })
  const pending = setMut.isPending

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
          jsx('div', { style: { fontWeight: 600 }, children: 'Done Bell' }),
          jsx('div', {
            style: { fontSize: 11, color: 'var(--ui-text-tertiary)' },
            children: settings.muted ? 'muted' : labelFor(busy, needsYou),
          }),
        ],
      }),
      jsx('div', {
        style: { fontSize: 12, color: 'var(--ui-text-tertiary)', lineHeight: 1.45 },
        children: 'Leave the window. When the turn finishes, Duckwork rings.',
      }),
      query.isLoading ? jsx('div', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Loading…' }) : null,
      query.error
        ? jsx('div', {
            style: { fontSize: 12 },
            children: 'Backend unreachable. Enable done-bell and restart the gateway.',
          })
        : null,
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 6 },
        children: [
          jsx(Toggle, {
            label: 'muted',
            checked: Boolean(settings.muted),
            disabled: pending,
            onClick: () => setMut.mutate({ muted: !settings.muted }),
          }),
          jsx(Toggle, {
            label: 'OS notify (when away)',
            checked: settings.os_notify !== false,
            disabled: pending,
            onClick: () => setMut.mutate({ os_notify: settings.os_notify === false }),
          }),
          jsx(Toggle, {
            label: 'chime',
            checked: settings.sound !== false,
            disabled: pending,
            onClick: () => setMut.mutate({ sound: settings.sound === false }),
          }),
          jsx(Toggle, {
            label: 'in-app toast',
            checked: Boolean(settings.in_app),
            disabled: pending,
            onClick: () => setMut.mutate({ in_app: !settings.in_app }),
          }),
          jsx(Toggle, {
            label: 'needs you (approval)',
            checked: settings.needs_you !== false,
            disabled: pending,
            onClick: () => setMut.mutate({ needs_you: settings.needs_you === false }),
          }),
        ],
      }),
      jsx('button', {
        type: 'button',
        disabled: testMut.isPending,
        onClick: () => testMut.mutate(),
        style: {
          alignSelf: 'flex-start',
          fontSize: 12,
          padding: '6px 10px',
          color: 'var(--ui-text-secondary)',
          background: 'transparent',
          border: '1px solid var(--ui-stroke-secondary)',
          borderRadius: 6,
          cursor: testMut.isPending ? 'wait' : 'pointer',
        },
        children: testMut.isPending ? 'Ringing…' : 'Test bell',
      }),
      jsx('div', {
        style: { fontSize: 11, color: 'var(--ui-text-tertiary)', marginTop: 4 },
        children: events.length ? 'Recent' : 'No turn events yet.',
      }),
      jsx('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 4 },
        children: events
          .slice()
          .reverse()
          .slice(0, 8)
          .map((event) =>
            jsxs(
              'div',
              {
                style: {
                  fontSize: 12,
                  color: 'var(--ui-text-tertiary)',
                  borderBottom: '1px solid var(--ui-stroke-secondary)',
                  padding: '4px 0',
                },
                children: [
                  jsx('span', { style: { color: 'var(--ui-text-secondary)' }, children: event.kind }),
                  '  ',
                  (event.at || '').slice(0, 19).replace('T', ' '),
                ],
              },
              event.id,
            ),
          ),
      }),
    ],
  })
}

export default {
  id: 'done-bell',
  name: 'Done Bell',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'done bell',
      data: { placement: 'right', width: '260px' },
      render: () => jsx(BellPane, { ctx }),
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 126,
      render: () => jsx(StatusChip, { ctx }),
    })
  },
}
