// meeting-overlay — native Duckwork desktop pane for the meeting-mode copilot.
//
// Layout (top → bottom):
//   1. toolbar   (fixed)       — listening · auto-recap · model · capture
//   2. answer    (FIXED card)  — the latest answer, never scrolls away
//   3. transcript (flex 1, own scroll, auto-anchored to latest line)
//   4. sessions  (fixed, own scroll cap)
//   5. action bar (fixed, bottom edge)
//
// The answer card is NOT inside the transcript's scroll container: that was the
// "answers don't flow" bug — auto-scroll pinned the shared container to the
// bottom and scrolled every answer out of view the moment a transcript line
// landed. Fixed answer + separately-scrolling transcript fixes it structurally.
//
// Rules: only @duckwork/plugin-sdk / react / react/jsx-runtime resolve; no JSX in
// a disk plugin (jsx/jsxs only); theme vars only; small type.

import { host, haptic, useQuery, queryClient } from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useRef, useEffect, useLayoutEffect, useState } from 'react'

const rest = { fn: null }
const os = { fn: null }

const faint = 'var(--ui-text-quaternary)'
const tert = 'var(--ui-text-tertiary)'
const accent = 'var(--ui-accent)'
const stroke = 'var(--ui-stroke-secondary)'
// Accent-filled buttons (green): text = panel background color, not white, so
// it reads as native Duckwork contrast instead of a glowing white-on-green slab.
const onAccent = 'var(--ui-background, var(--ui-bg-chrome))'

const MODELS = [
  { id: 'host', label: 'Host', hint: 'Your Duckwork default model (fast, low reasoning — hosted)' },
  { id: 'local', label: 'Local', hint: 'Qwen3-4B running on this Mac (works offline)' },
]
const MODES = [
  { id: 'phone', label: 'Phone', hint: 'Use this phone as the microphone (streams its own audio)' },
  { id: 'mic', label: 'Mic', hint: 'Capture this Mac\u2019s microphone' },
  { id: 'blackhole', label: 'Audio', hint: 'Capture computer audio (call on this Mac)' },
  { id: 'both', label: 'Both', hint: 'Capture computer audio + mic together' },
]

// Lucide-style stroke icons (not emoji) — no truncation, no font dependency.
const ICON = {
  host: ['M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z'],
  local: ['M22 12H2', 'M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z', 'M6 16h.01', 'M10 16h.01'],
  both: ['M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z', 'M22 17.65l-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65', 'M22 12.65l-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65'],
  mic: ['M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z', 'M19 10v2a7 7 0 0 1-14 0v-2', 'M12 19v3'],
  blackhole: ['M2 3h20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z', 'M8 21h8', 'M12 17v4'],
  phone: ['M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.08 4.18 2 2 0 0 1 4.08 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z'],
  trash: ['M3 6h18', 'M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2', 'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6'],
  xcircle: ['M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z', 'M15 9l-6 6', 'M9 9l6 6'],
  check: ['M20 6L9 17l-5-5'],
}

function Icon({ name, size = 14, fill = false }) {
  const paths = ICON[name] || []
  return jsx('svg', {
    width: size, height: size, viewBox: '0 0 24 24',
    fill: fill ? 'currentColor' : 'none',
    stroke: fill ? 'none' : 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round',
    style: { flexShrink: 0, display: 'block' },
    children: paths.map((d, i) => jsx('path', { key: i, d })),
  })
}

const labelStyle = {
  fontSize: '9px', fontWeight: 700, letterSpacing: '0.07em',
  textTransform: 'uppercase', color: faint, lineHeight: 1,
}

function Chip({ options, value, onPick, tone = 'outline', recording = false, disabled = [] }) {
  // tone 'outline' = capture sources; tone 'fill' = model (muted/dark fill).
  // For capture sources: idle = medium-gray outline on the selected one; when
  // recording, the selected capture's icon strokes GREEN (or RED if it's the
  // phone, which glows like REC). disabled ids are non-clickable (no cursor).
  const fill = tone === 'fill'
  return jsxs('div', {
    style: { display: 'flex', gap: '4px' },
    children: options.map(o => {
      const selected = value === o.id
      const isDisabled = disabled.includes(o.id)
      const live = selected && recording
      const phoneLive = o.id === 'phone' && live
      const liveColor = phoneLive ? 'var(--ui-red)' : 'var(--ui-accent)'
      return jsx('button', {
        key: o.id,
        onClick: isDisabled ? undefined : () => { haptic('tap'); onPick(o.id) },
        title: o.hint || o.label,
        'aria-label': o.hint || o.label,
        disabled: isDisabled,
        style: {
          flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '27px', padding: 0, borderRadius: '6px',
          cursor: isDisabled ? 'default' : 'pointer',
          userSelect: 'none', WebkitUserSelect: 'none',
          opacity: isDisabled && !phoneLive ? 0.5 : 1,
          border: fill
            ? (selected ? '1px solid ' + stroke : '1px solid transparent')
            : (selected ? '1px solid ' + (live ? liveColor : stroke) : '1px solid transparent'),
          background: fill
            ? (selected ? 'color-mix(in srgb, var(--ui-text-tertiary) 14%, transparent)' : 'transparent')
            : (phoneLive ? 'color-mix(in srgb, var(--ui-red) 14%, transparent)' : 'transparent'),
          color: fill
            ? (selected ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)')
            : (selected ? (live ? liveColor : 'var(--ui-text-primary)') : tert),
        },
        children: jsx(Icon, { name: o.id, size: 15, fill: false }),
      })
    }),
  })
}

// Minimal draggable chunk-interval scrobbler. A thin ticked line with a tiny
// square grabber, no label, no border. Drag state lives in a ref (NOT state):
// pointermove fires faster than React re-renders, so state would read stale
// false and the grab would never track.
function Scrobber({ value, onChange }) {
  const MIN = 15, MAX = 60, STEP = 5
  const trackRef = useRef(null)
  const ticks = []
  for (let v = MIN; v <= MAX; v += STEP) ticks.push(v)

  const valToPct = v => ((v - MIN) / (MAX - MIN)) * 100
  const pctToVal = pct => {
    const raw = MIN + (pct / 100) * (MAX - MIN)
    return Math.round(raw / STEP) * STEP
  }
  const onMoveRef = useRef(onChange)
  onMoveRef.current = onChange
  // Proven drag recipe for this renderer (same as the accent color picker):
  // pointerdown on the track, then WINDOW-level pointermove/pointerup so the
  // drag keeps tracking after the cursor leaves the tiny track.
  const onPointerDown = e => {
    const box = trackRef.current
    if (!box) return
    const emit = clientX => {
      const r = box.getBoundingClientRect()
      const pct = Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100))
      onMoveRef.current(Math.max(MIN, Math.min(MAX, pctToVal(pct))))
    }
    emit(e.clientX)
    const onPointerMove = ev => emit(ev.clientX)
    const stop = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', stop)
    }
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', stop)
  }
  const pct = valToPct(value)
  return jsxs('div', {
    title: 'Chunk every ' + value + 's',
    style: { display: 'flex', alignItems: 'center', gap: '5px', flex: '0 0 auto' },
    children: [
      jsx('div', {
        ref: trackRef,
        style: { position: 'relative', width: '56px', height: '10px', cursor: 'ew-resize', touchAction: 'none', flex: '0 0 auto' },
        onPointerDown,
        children: [
          jsx('div', { style: { position: 'absolute', left: 0, right: 0, top: '50%', height: '2px', transform: 'translateY(-50%)', background: stroke, borderRadius: '1px' } }),
          ...ticks.map(v => jsx('div', {
            key: v,
            style: { position: 'absolute', left: valToPct(v) + '%', top: '50%', transform: 'translate(-50%, -50%)', width: '1px', height: v % 15 === 0 ? '6px' : '3px', background: tert, borderRadius: '1px' },
          })),
          jsx('div', { style: { position: 'absolute', left: pct + '%', top: '50%', transform: 'translate(-50%, -50%)', width: '8px', height: '8px', borderRadius: '2px', background: 'var(--ui-bg-chrome)', border: '1px solid ' + accent, cursor: 'ew-resize', pointerEvents: 'none' } }),
        ],
      }),
      jsx('span', { style: { fontSize: '9px', color: faint, fontVariantNumeric: 'tabular-nums', flex: '0 0 auto' }, children: value + 's' }),
    ],
  })
}

function RecordToggle({ on, onToggle, hint }) {
  // Recording semantics: OFF = green "RECORD" (press to start), ON = muted red
  // "LIVE" (press to stop). The classic camera idiom, so the listening state
  // reads at a glance without a separate status dot.
  return jsx('button', {
    onClick: () => { haptic('tap'); onToggle(!on) },
    title: hint || (on ? 'Stop recording' : 'Start recording'),
    style: {
      fontSize: '9px', fontWeight: 700, letterSpacing: '0.05em', lineHeight: 1,
      height: '27px', padding: '0 10px', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      userSelect: 'none', WebkitUserSelect: 'none',
      border: on ? '1px solid var(--ui-red)' : '1px solid transparent',
      background: on ? 'color-mix(in srgb, var(--ui-red) 16%, transparent)' : 'var(--ui-accent)',
      color: on ? 'var(--ui-red)' : onAccent,
    },
    children: on ? 'LIVE' : 'RECORD',
  })
}

function ActionButton({ label, onClick, tone, hint, disabled, active }) {
  const primary = tone === 'primary'
  return jsx('button', {
    onClick: disabled ? undefined : () => { haptic('tap'); onClick() },
    title: hint || label,
    disabled,
    style: {
      flex: 1, minWidth: 0, fontSize: '10.5px', fontWeight: 600, lineHeight: 1,
      padding: '5px 4px', borderRadius: '6px',
      cursor: disabled ? 'default' : 'pointer',
      opacity: disabled ? 0.45 : 1,
      userSelect: 'none', WebkitUserSelect: 'none',
      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      // `active` = the PERSISTED selected assist mode. Green fill, same as the
      // phone PWA, so "which mode is on" is unmistakable at a glance.
      border: active ? '1px solid #22c55e'
        : primary ? '1px solid transparent' : '1px solid ' + stroke,
      background: active ? '#22c55e'
        : primary ? 'var(--ui-accent)' : 'transparent',
      color: active ? '#0b0b0f'
        : primary ? onAccent : tone === 'subtle' ? faint : 'var(--ui-text-primary)',
      fontWeight: active ? 800 : 600,
      boxShadow: active ? '0 0 0 2px rgba(34,197,94,0.28)' : 'none',
    },
    children: label,
  })
}

// Inline-text answer action — subtle, no border/background, reads as prose.
function InlineAction({ label, onClick, hint }) {
  return jsx('span', {
    onClick: () => { haptic('tap'); onClick() },
    title: hint || label,
    style: {
      fontSize: '10px', color: faint, cursor: 'pointer',
      textDecoration: 'none', whiteSpace: 'nowrap',
      userSelect: 'none', WebkitUserSelect: 'none',
    },
    children: label,
  })
}

function MeetingPane() {
  const tq = useQuery({
    queryKey: ['meeting-overlay', 'transcript'],
    queryFn: () => (rest.fn ? rest.fn('/transcript') : Promise.resolve({ lines: [] })),
    refetchInterval: 2000,
  })
  const aq = useQuery({
    queryKey: ['meeting-overlay', 'answer'],
    queryFn: () => (rest.fn ? rest.fn('/answer') : Promise.resolve({ text: '' })),
    refetchInterval: 1200,
  })
  const dq = useQuery({
    queryKey: ['meeting-overlay', 'answers'],
    queryFn: () => (rest.fn ? rest.fn('/answers') : Promise.resolve({ answers: [] })),
    refetchInterval: 1200,
  })
  const sq = useQuery({
    queryKey: ['meeting-overlay', 'settings'],
    queryFn: () => (rest.fn ? rest.fn('/settings') : Promise.resolve({})),
    refetchInterval: 3000,
  })
  const sessionsQ = useQuery({
    queryKey: ['meeting-overlay', 'sessions'],
    queryFn: () => (rest.fn ? rest.fn('/sessions') : Promise.resolve({ sessions: [] })),
    refetchInterval: 10000,
  })

  const lines = tq.data?.lines ?? []
  const answer = aq.data?.text ?? ''
  const deck = dq.data?.answers ?? []
  const settings = sq.data ?? {}
  const listening = !!settings.listening
  const model = settings.model || 'host'
  const mode = settings.mode || 'both'
  const autoLocal = !!settings.auto_local
  const autoAssist = !!settings.auto_assist
  const modelOff = model === 'off'
  const chunkSec = Math.max(15, Math.min(60, settings.chunk_sec || 30))
  const stale =
    sq.data?.transcript_age_sec != null && sq.data.transcript_age_sec > 30 && listening
  const sessions = sessionsQ.data?.sessions ?? []
  const hiddenSessions = sessionsQ.data?.hidden ?? []

  const [query, setQuery] = useState('')
  const [cardQuery, setCardQuery] = useState('')
  const [landedId, setLandedId] = useState(null)   // id of the card that just dropped
  const [surfacedId, setSurfacedId] = useState(null) // card expanded full; null = newest
  const [flipped, setFlipped] = useState(true)     // transcript ⇄ answers swap (default: answers/cards on top)
  const [note, setNote] = useState(null)           // transient action feedback label
  const noteTimer = useRef(null)
  // records checked in the Records list: "keep these", committed by Save to vault
  const [checkedRels, setCheckedRels] = useState([])
  const toggleRel = rel => setCheckedRels(p => p.includes(rel) ? p.filter(r => r !== rel) : [...p, rel])
  const transcriptRef = useRef(null)

  // inject the drop-flash keyframes once (a new card fades in on a green fill
  // that decays over ~1s, so a fresh answer visibly lands without a JS timer).
  useEffect(() => {
    if (document.getElementById('meeting-card-drop-css')) return
    const st = document.createElement('style')
    st.id = 'meeting-card-drop-css'
    st.textContent = [
      '@keyframes meetingCardDrop {',
      '  0% { background: var(--ui-accent); }',
      '  60% { background: var(--ui-accent); }',
      '  100% { background: transparent; }',
      '}',
      // spinner for in-flight Save/Recap feedback
      '@keyframes meetingSpin { to { transform: rotate(360deg); } }',
    ].join('\n')
    document.head.appendChild(st)
  }, [])

  useEffect(() => {
    const el = transcriptRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines.length, lines])

  // visible answer cards, NEWEST FIRST: the live streaming answer is the newest,
  // then the completed deck (oldest→newest) reversed so card[0] is always the
  // most recent. No pagination — the deck is one scrollable fanned column.
  const cards = []
  for (const d of deck) cards.push({ ...d, live: false })
  if (answer && (!cards.length || cards[cards.length - 1].text !== answer)) {
    cards.push({ id: 'live', ts: 'streaming', action: 'live', model, text: answer, live: true })
  }
  const newestFirst = [...cards].reverse()
  // when a new answer lands, surface the newest + flash it ON the drop frame.
  // useLayoutEffect runs BEFORE paint, so the flash class is applied to the card
  // in the same frame it first appears (useEffect ran after paint → the flash
  // started a beat late, which read as "broken"). prevNewest must also be
  // updated on every pass, else the condition re-fires on later renders.
  const newestId = newestFirst[0]?.id
  const prevNewest = useRef(null)
  useLayoutEffect(() => {
    const prev = prevNewest.current
    prevNewest.current = newestId
    if (prev && prev !== newestId && newestId !== 'live') {
      setLandedId(newestId)
      setSurfacedId(null)  // newest card surfaces (drops OPEN) on arrival
      const t = setTimeout(() => setLandedId(null), 1100)
      return () => clearTimeout(t)
    }
  }, [newestId])

  const visibleLines = query
    ? lines.filter(l => l.toLowerCase().includes(query.toLowerCase()))
    : lines

  const post = (path, body) => {
    if (!rest.fn) return Promise.resolve({})
    return rest.fn(path, { method: 'POST', body }).then(r => {
      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'settings'] })
      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'status'] })
      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'answer'] })
      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'answers'] })
      return r
    })
  }

  const setListening = on => post('/mode', { listen: on })
  // capture source = TOGGLE. Clicking the already-active source stops it;
  // clicking a different source selects + starts it. The desktop never controls
  // the "phone" source (that's phone-only), so setMode only fires for
  // mic/audio/both here.
  const setMode = m => {
    if (m === mode && listening) return post('/mode', { mode: m, listen: false }) // stop
    return post('/mode', { mode: m, listen: true }) // start this source
  }
  const setModel = m => post('/model', { model: m === model ? 'off' : m })
  const runAction = action => post('/run', { action })
  // record mode: on starts the watch loop, off flips the flag to stop it
  const setAssistMode = am => post('/assist', { assist_mode: am })
  const setChunk = sec => post('/assist', { chunk_sec: sec })
  // The three assist entries are a MUTUALLY-EXCLUSIVE, PERSISTED mode selection
  // (off | what | followup | research). Picking one does NOT start listening —
  // the capture toggles do that; the watch loop only emits a card when the
  // transcript actually grows. Clicking the active mode clears it.
  const assistMode = settings.assist_mode || (autoAssist ? 'what' : 'off')
  const toggleMode = k => setAssistMode(assistMode === k ? 'off' : k)
  // transient action feedback: { text, kind } — 'spin' while in flight, 'check'
  // when done. Short text (no ellipsis — the spinner conveys progress).
  const flash = (text, kind = 'spin', ms = 12000) => {
    setNote({ text, kind })
    if (noteTimer.current) clearTimeout(noteTimer.current)
    noteTimer.current = setTimeout(() => setNote(null), ms)
  }
  // exports run in a detached subprocess; refresh the records list a few times
  // so the new record shows up on its own, then confirm with a check.
  const afterExport = (done) => {
    let n = 0
    const iv = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] })
      if (++n >= 6) { clearInterval(iv); flash(done, 'check', 3200) }
    }, 1500)
  }

  // Export types — both save to the vault, one with an LLM summary, one without.
  // Both give immediate feedback + auto-refresh the records list.
  const saveToVault = () => {
    const keep = checkedRels.slice()
    flash(keep.length ? 'Saving ' + keep.length + ' kept' : 'Saving to Records', 'spin', 60000)
    return post('/run', { action: 'save', model }).then(() =>
      // commit the CHECKED records: they are kept in the vault and drop off the
      // list (soft-hidden, so they never reappear unless explicitly restored).
      Promise.all(keep.map(rel => post('/session/hide', { rel }))).then(() => {
        setCheckedRels([])
        queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] })
        afterExport(keep.length ? keep.length + ' kept' : 'Saved to Records')
      })
    )
  }
  const runRecap = () => {
    flash('Recapping', 'spin', 60000)
    return post('/run', { action: 'recap' }).then(() => afterExport('Recap saved'))
  }
  // Clear actions: wipe the deck (cards) or the transcript. Both are destructive
  // to on-disk state but trivially re-populated by new speech/answers.
  const clearCards = () => post('/clear/deck')
  const clearTranscript = () => post('/clear/transcript')
  // "ask" types — the three MUTUALLY-EXCLUSIVE assist MODES. Selecting one
  // persists the mode (it does NOT start listening — the capture toggles do).
  const askWhat = () => toggleMode('what')
  const askFollowup = () => toggleMode('followup')
  const askResearch = () => toggleMode('research')
  // inline research on a specific answer — hand it to the chat queue with
  // THAT answer as context so a follow-up web/THI run targets the right text.
  const researchAnswer = (kind, text) => post('/request', { kind, context: text })

  // Open a Duckwork session with context. `focus` = 'transcript' or 'answer'.
  const openInDuckwork = async (focus, cardText) => {
    if (typeof host.openSession !== 'function' || typeof host.request !== 'function') {
      host.notify({ kind: 'error', message: 'This desktop build cannot open a session from a plugin.' })
      return
    }
    haptic('tap')
    let context = ''
    try {
      if (rest.fn) {
        // cardText wins (continue = continue THAT answer), else latest answer /
        // full transcript. focus 'answer' with no cardText = newest answer.
        const r = cardText
          ? { text: cardText }
          : focus === 'answer' ? { text: answer } : await rest.fn('/full')
        context = (r.text || '').slice(-8000)
      }
    } catch (e) { /* proceed with empty context */ }
    const intent = focus === 'answer'
      ? 'Continue this meeting analysis. Here is the latest answer; elaborate and tell me what to do next.'
      : 'Here is the live meeting transcript as context. Recap it, then tell me what I should do or ask next.'
    const text = context ? `${intent}\n\n---\n${context}` : intent
    try {
      const created = await host.request('session.create', { title: 'Meeting', hidden: false })
      const sessionId = created?.session_id || created?.stored_session_id
      if (!sessionId) throw new Error('no session id')
      if (created?.stored_session_id) {
        await host.openSession(created.stored_session_id, { intent: 'in-place' })
      }
      await host.request('prompt.submit', { session_id: sessionId, text })
    } catch (e) {
      host.notify({ kind: 'error', message: 'Could not open the meeting session: ' + String(e) })
    }
  }

  const copyText = (text) => {
    if (!text) return
    navigator.clipboard.writeText(text).catch(() => {})
    haptic('tap')
  }

  return jsxs('div', {
    className: 'flex h-full flex-col text-xs',
    style: { gap: '6px', padding: '8px', overflow: 'hidden', minHeight: 0, boxSizing: 'border-box' },
    children: [

      // ── 1. toolbar (fixed) — record indicator · capture source · model ──
      //    (1) REC indicator — click it to STOP recording (red when live).
      //    (2) capture SOURCE selector — phone/mic/audio/both as icon buttons.
      //        phone is disabled on the desktop (phone-only) and glows red when
      //        the phone is the live source. Clicking an active source stops it.
      //    (3) model. Every device shares settings, so they stay in sync.
      jsxs('div', {
        style: { flex: '0 0 auto', order: 1, display: 'flex', gap: '8px', alignItems: 'flex-end', minWidth: 0 },
        children: [
          jsx('button', {
            onClick: () => { haptic('tap'); if (listening && mode !== 'phone') setListening(false) },
            title: mode === 'phone' && listening ? 'Phone is recording — stop it from the phone' : (listening ? 'Stop recording' : 'Not recording'),
            style: {
              display: 'flex', alignItems: 'center', gap: '5px',
              height: '27px', padding: '0 8px', borderRadius: '6px', flexShrink: 0,
              cursor: (listening && mode !== 'phone') ? 'pointer' : 'default',
              border: '1px solid ' + (listening ? 'var(--ui-red)' : stroke),
              background: listening ? 'color-mix(in srgb, var(--ui-red) 12%, transparent)' : 'var(--ui-bg-chrome)',
              userSelect: 'none', WebkitUserSelect: 'none',
            },
            children: [
              jsx('span', {
                style: {
                  width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
                  background: listening ? 'var(--ui-red)' : tert,
                },
              }),
              jsx('span', { style: { fontSize: '9px', fontWeight: 700, letterSpacing: '0.06em', lineHeight: 1, color: listening ? 'var(--ui-red)' : faint }, children: 'REC' }),
            ],
          }),
          jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '3px', flex: 1.4, minWidth: 0 }, children: [
            jsx(Chip, { options: MODES, value: mode, onPick: setMode, recording: listening, disabled: ['phone'] }),
          ] }),
          jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '3px', flex: 1, minWidth: 0 }, children: [
            jsx(Chip, { options: MODELS, value: model, onPick: setModel, tone: 'fill' }),
          ] }),
        ],
      }),

      // ── 2. transcript (flex 1 on top by default; order 3 when flipped) ──
      jsxs('div', { style: { flex: flipped ? '0 0 150px' : '1 1 0', order: flipped ? 3 : 2, minHeight: 0, display: 'flex', flexDirection: 'column', gap: '4px' }, children: [
        jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', flex: '0 0 auto' }, children: [
          jsx('div', { style: { ...labelStyle, flex: 1 }, children: 'Live transcript' + (listening ? ' · live' : '') + (autoLocal ? ' · local model' : '') }),
          jsx('input', {
            value: query, placeholder: 'Search', onInput: e => setQuery(e.target.value),
            style: {
              fontSize: '10px', padding: '2px 6px', borderRadius: '5px', width: '38%',
              border: '1px solid ' + stroke, background: 'var(--ui-bg-chrome)', color: 'var(--ui-text-primary)',
            },
          }),
          jsx('button', {
            onClick: () => { haptic('tap'); clearTranscript() },
            title: 'Clear the transcript',
            style: { padding: '0 6px', height: '18px', cursor: 'pointer', color: 'var(--ui-text-secondary)', background: 'transparent', border: '1px solid ' + stroke, borderRadius: '5px', lineHeight: 1, userSelect: 'none', WebkitUserSelect: 'none', display: 'flex', alignItems: 'center' },
            children: jsx(Icon, { name: 'xcircle', size: 12 }),
          }),
        ] }),
        jsxs('div', {
          ref: transcriptRef,
          style: { flex: '1 1 0', minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' },
          children: visibleLines.length === 0
            ? jsx('div', { style: { fontSize: '11px', color: faint, fontStyle: 'italic' }, children: query ? 'No matches.' : listening ? 'Listening — nothing yet.' : 'Idle.' })
            : visibleLines.slice(-60).map((raw, i) => {
                const m = String(raw).match(/^\[(\d\d:\d\d:\d\d)\]\s?(.*)$/)
                const ts = m ? m[1] : ''
                const txt = m ? m[2] : raw
                return jsxs('div', {
                  key: i, style: { display: 'flex', gap: '6px', fontSize: '11px', lineHeight: '1.4', userSelect: 'text', WebkitUserSelect: 'text', color: tert },
                  children: [
                    jsx('span', { style: { color: faint, fontSize: '9.5px', fontVariantNumeric: 'tabular-nums', flex: '0 0 auto', paddingTop: '1px' }, children: ts }),
                    jsx('span', { children: txt }),
                  ],
                })
              }),
        }),
      ] }),

      // ── 3. answer deck (fixed tall window; inner scroll; newest surfaced) ──
      //    A coherent fanned deck: the newest card is surfaced full and the rest
      //    collapse to thin edge-bars. The window is a tall FIXED viewport that
      //    scrolls internally, so every pile is reachable by scrolling — no
      //    arrow pagination, no hidden overflow.
      jsxs('div', {
        style: { flex: flipped ? '1 1 0' : '0 0 300px', order: flipped ? 2 : 3, display: 'flex', flexDirection: 'column', gap: '4px', minHeight: 0 },
        children: [
          jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '6px', flex: '0 0 auto' }, children: [
            jsx('div', { title: cards.length + ' answers', style: { ...labelStyle, flex: 1 }, children: cards.length + ' answers' }),
            // scrobbler: chunk interval for record mode (15–60s)
            jsx(Scrobber, { value: chunkSec, onChange: setChunk }),
            jsx('button', {
              onClick: () => { haptic('tap'); setFlipped(!flipped) },
              title: flipped ? 'Answers on top — click to put transcript on top' : 'Transcript on top — click to put answers on top',
              style: { fontSize: '12px', padding: '0 6px', cursor: 'pointer', color: 'var(--ui-text-primary)', background: 'transparent', border: '1px solid ' + stroke, borderRadius: '5px', lineHeight: 1, userSelect: 'none', WebkitUserSelect: 'none' },
              children: '⇅',
            }),
            jsx('button', {
              onClick: () => { haptic('tap'); clearCards() },
              title: 'Clear all answer cards',
              style: { padding: '0 6px', height: '18px', cursor: 'pointer', color: 'var(--ui-text-secondary)', background: 'transparent', border: '1px solid ' + stroke, borderRadius: '5px', lineHeight: 1, userSelect: 'none', WebkitUserSelect: 'none', display: 'flex', alignItems: 'center' },
              children: jsx(Icon, { name: 'trash', size: 12 }),
            }),
            jsx('input', {
              value: cardQuery, placeholder: 'Search', onInput: e => setCardQuery(e.target.value),
              style: {
                fontSize: '10px', padding: '2px 6px', borderRadius: '5px', width: '30%',
                border: '1px solid ' + stroke, background: 'var(--ui-bg-chrome)', color: 'var(--ui-text-primary)',
              },
            }),
          ] }),
          cards.length === 0
            ? jsx('div', { style: { fontSize: '11px', color: faint, fontStyle: 'italic', flex: '0 0 auto' }, children: 'Ask something below — answers stream in here as cards.' })
            : jsxs('div', {
                // constrained scroll viewport: the deck area is fixed-height and
                // this inner column scrolls, so older piles stay reachable.
                style: {
                  display: 'flex', flexDirection: 'column', alignItems: 'stretch',
                  flex: '1 1 0', minHeight: 0, overflowY: 'auto', paddingBottom: '4px',
                },
                children: (cardQuery
                  ? newestFirst.filter(c => (c.text || '').toLowerCase().includes(cardQuery.toLowerCase()))
                  : newestFirst
                ).map((c, i) => jsx(AnswerCard, {
                  key: c.id, card: c, index: i, landed: c.id === landedId,
                  surfaced: (surfacedId == null ? i === 0 : c.id === surfacedId),
                  onSurface: () => setSurfacedId(c.id),
                  onMinimize: () => setSurfacedId('none'),
                  onCopy: copyText,
                  onContinue: (t) => openInDuckwork('answer', t),
                  onOpen: () => openInDuckwork('transcript'),
                  onWeb: (t) => researchAnswer('web-research', t),
                  onSqsi: (t) => researchAnswer('thi-research', t),
                })),
              }),
        ],
      }),

      // ── 4. records (compact, capped; hide/restore/clear per record) ──
      jsxs('div', { style: { flex: '0 0 auto', order: 4, borderTop: '1px solid ' + stroke, paddingTop: '5px', maxHeight: '110px', display: 'flex', flexDirection: 'column' }, children: [
        jsxs('div', { style: { position: 'relative', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', flex: '0 0 auto', minWidth: 0 }, children: [
          jsx('div', { style: { ...labelStyle, flex: '0 0 auto' }, children: 'Records (' + sessions.length + ')' }),
          // Feedback is ABSOLUTELY positioned so appearing/disappearing never
          // resizes the header (or shifts the content below). Icon is LEFT of
          // the text: a spinner while in flight, a check when done. No dot.
          note && jsxs('div', {
            style: { position: 'absolute', right: 0, top: '-1px', display: 'flex', alignItems: 'center', gap: '5px', whiteSpace: 'nowrap', fontSize: '9.5px', color: 'var(--ui-text-secondary)' },
            children: [
              note.kind === 'spin'
                ? jsx('span', {
                    style: {
                      width: '9px', height: '9px', borderRadius: '50%', flex: '0 0 auto',
                      border: '1.5px solid ' + stroke, borderTopColor: 'var(--ui-accent)',
                      animation: 'meetingSpin 0.7s linear infinite',
                    },
                  })
                : jsx(Icon, { name: 'check', size: 11 }),
              jsx('span', { children: note.text }),
            ],
          }),
        ] }),
        sessions.length === 0 && hiddenSessions.length === 0
          ? jsx('div', { style: { fontSize: '10.5px', color: faint, fontStyle: 'italic', flex: '0 0 auto' }, children: 'Nothing saved yet — use Save to vault or Recap.' })
          : jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '1px', overflowY: 'auto', minHeight: 0 },
              children: [
                ...sessions.slice(0, 8).map(s => jsx(SessionRow, {
                  key: 'v-' + s.rel, session: s,
                  checked: checkedRels.includes(s.rel),
                  onCheck: () => toggleRel(s.rel),
                  onHide: () => {
                    post('/session/hide', { rel: s.rel }).then(() =>
                      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] }))
                  },
                  onDelete: () => {
                    post('/session/delete', { rel: s.rel }).then(() =>
                      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] }))
                  },
                  onRename: (to) => {
                    post('/session/rename', { rel: s.rel, new_name: to }).then(() =>
                      queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] }))
                  },
                })),
                ...(hiddenSessions.length > 0
                  ? [jsx('div', { key: 'hidden-label', style: { ...labelStyle, color: faint, marginTop: '4px' }, children: 'Hidden (' + hiddenSessions.length + ')' }),
                     ...hiddenSessions.map(s => jsx(SessionRow, {
                       key: 'h-' + s.rel, session: s, hidden: true,
                       onRestore: () => {
                         post('/session/restore', { rel: s.rel }).then(() =>
                           queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] }))
                       },
                       onDelete: () => {
                         post('/session/delete', { rel: s.rel }).then(() =>
                           queryClient.invalidateQueries({ queryKey: ['meeting-overlay', 'sessions'] }))
                       },
                     }))]
                  : []),
              ],
            }),
      ] }),

      // ── 5. action bar (fixed, bottom edge) — assist MODES + export ──
      jsxs('div', { style: { flex: '0 0 auto', order: 5, display: 'flex', flexDirection: 'column', gap: '4px' }, children: [
        // three mutually-exclusive, persisted LISTEN MODES. Selecting one changes
        // the setting only — listening starts from the capture toggles above.
        jsxs('div', { style: { display: 'flex', gap: '4px' }, children: [
          jsx(ActionButton, { label: 'What to say', active: assistMode === 'what', onClick: askWhat, disabled: modelOff, hint: modelOff ? 'No model selected — pick Host or Local' : (assistMode === 'what' ? 'Listening mode ON — auto-chunks "what to say" every ' + chunkSec + 's while the transcript grows. Click to turn off.' : 'Set listening mode: auto-chunk "what to say" every ' + chunkSec + 's') }),
          jsx(ActionButton, { label: 'Follow-up', active: assistMode === 'followup', onClick: askFollowup, disabled: modelOff, hint: modelOff ? 'No model selected — pick Host or Local' : (assistMode === 'followup' ? 'Listening mode ON — auto-chunks "follow-up questions" every ' + chunkSec + 's. Click to turn off.' : 'Set listening mode: auto-chunk follow-up questions every ' + chunkSec + 's') }),
          jsx(ActionButton, { label: 'Research', active: assistMode === 'research', onClick: askResearch, disabled: modelOff, hint: modelOff ? 'No model selected — pick Host or Local' : (assistMode === 'research' ? 'Listening mode ON — auto-chunks "research context" every ' + chunkSec + 's. Click to turn off.' : 'Set listening mode: auto-chunk background/research every ' + chunkSec + 's') }),
        ] }),
        jsxs('div', { style: { display: 'flex', gap: '4px' }, children: [
          jsx(ActionButton, { label: 'Save to vault', onClick: saveToVault, hint: 'Save transcript-only to Records (no summary) — new records appear in Records below' }),
          jsx(ActionButton, { label: 'Recap', onClick: runRecap, disabled: modelOff, hint: modelOff ? 'No model selected — pick Host or Local' : 'LLM summary (decisions/actions/questions) saved to Records' }),
        ] }),
      ] }),
    ],
  })
}

// ── one answer card, rendered as a FANNED DECK. The surfaced card (default:
// the newest) is full; every other card is a thin clickable EDGE-BAR showing
// label · time · one-line peek. Click an edge to surface it; click the surfaced
// card's ✕ to minimize it back. Distinct 2px-separated edges keep it legible. ──
function AnswerCard({ card, index, landed, surfaced, onSurface, onMinimize, onCopy, onContinue, onOpen, onWeb, onSqsi }) {
  const actionLabel = {
    what: 'What to say', followup: 'Follow-up', research: 'Research',
    recap: 'Recap', live: 'Assist', save: 'Saved',
  }[card.action] || card.action

  // ── EDGE BAR (non-surfaced): a thin strip you click to surface the card ──
  if (!surfaced) {
    return jsx('button', {
      onClick: () => { haptic('tap'); onSurface() },
      title: 'Show this answer',
      style: {
        marginTop: '2px',
        zIndex: 1,
        display: 'flex', alignItems: 'center', gap: '8px',
        minWidth: 0, height: '20px', padding: '0 9px', boxSizing: 'border-box',
        border: '1px solid ' + stroke, borderRadius: '6px',
        background: 'var(--ui-bg-chrome)', cursor: 'pointer',
        fontSize: '10px', lineHeight: 1, textAlign: 'left', color: tert,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        userSelect: 'none', WebkitUserSelect: 'none', flex: '0 0 auto',
      },
      children: [
        jsx('span', { style: { ...labelStyle, color: card.live ? accent : faint, flexShrink: 0 }, children: actionLabel }),
        jsx('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, minWidth: 0, color: 'var(--ui-text-primary)' }, children: (card.text || '').slice(0, 80) }),
      ],
    })
  }

  // ── SURFACED CARD (full) ──
  return jsxs('div', {
    style: {
      flex: '0 0 auto', minWidth: 0, position: 'relative', zIndex: 20,
      border: '1px solid ' + stroke, borderRadius: '8px', padding: '7px 9px',
      background: card.live ? 'var(--ui-bg-chrome)' : 'transparent',
      display: 'flex', flexDirection: 'column', minHeight: 0, boxSizing: 'border-box',
      // a card that just dropped flashes green and decays to transparent
      animation: landed ? 'meetingCardDrop 1.1s ease-out forwards' : undefined,
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '3px', flex: '0 0 auto' },
        children: [
          // title is the minimize affordance (tap it to collapse back to an edge);
          // no timestamp — the title alone keeps the top bar aligned and quiet.
          jsx('span', {
            onClick: () => { haptic('tap'); onMinimize() },
            title: 'Minimize this card',
            style: { ...labelStyle, color: card.live ? accent : faint, cursor: 'pointer', userSelect: 'none', WebkitUserSelect: 'none' },
            children: actionLabel,
          }),
          jsxs('div', { style: { display: 'flex', gap: '8px', flexShrink: 0, paddingRight: '2px', alignItems: 'center' }, children: [
            jsx(InlineAction, { label: 'web', hint: 'Research this answer on the web', onClick: () => onWeb(card.text) }),
            jsx(InlineAction, { label: 'thi', hint: 'Launch THI research on this answer', onClick: () => onSqsi(card.text) }),
            jsx(InlineAction, { label: 'copy', hint: 'Copy this answer', onClick: () => onCopy(card.text) }),
            jsx(InlineAction, { label: 'chat', hint: 'Open a Duckwork chat continuing this answer', onClick: () => onContinue(card.text) }),
            jsx(InlineAction, { label: 'transcript', hint: 'Open a Duckwork chat with the full transcript as context', onClick: onOpen }),
            jsx('span', {
              onClick: () => { haptic('tap'); onMinimize() },
              title: 'Minimize this card',
              'aria-label': 'Minimize',
              style: { fontSize: '11px', lineHeight: '10px', padding: '0 1px', cursor: 'pointer', color: faint, userSelect: 'none', WebkitUserSelect: 'none', display: 'inline-flex', alignItems: 'center' },
              children: '✕',
            }),
          ] }),
        ],
      }),
      jsx('div', {
        style: {
          fontSize: '11px', lineHeight: '1.45', whiteSpace: 'pre-wrap', flex: 1, minHeight: 0,
          paddingRight: '8px',
          userSelect: 'text', WebkitUserSelect: 'text', cursor: 'text',
          color: 'var(--ui-text-primary)',
        },
        children: card.text,
      }),
    ],
  })
}

// ── a record row: name/date, reveal, rename, hide/restore, two-click clear ──
function SessionRow({ session, hidden, checked, onCheck, onDelete, onRename, onHide, onRestore }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [arming, setArming] = useState(false)

  const base = session.name.replace(/\.md$/, '')
  const date = session.modified
    ? new Date(session.modified * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : ''

  function reveal() {
    haptic('tap')
    if (os.fn && os.fn.revealPath) os.fn.revealPath(session.path).catch(() => {})
  }
  function commitRename() {
    setEditing(false)
    const clean = draft.trim()
    if (!clean) return
    onRename(clean + '.md')
  }

  return jsxs('div', {
    style: { display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10.5px', padding: '2px 2px', borderRadius: '5px', opacity: hidden ? 0.55 : 1 },
    children: editing ? [
      jsx('input', {
        value: draft, autoFocus: true,
        onInput: e => setDraft(e.target.value),
        onKeyDown: e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setEditing(false) },
        style: { flex: 1, minWidth: 0, fontSize: '10.5px', padding: '2px 5px', borderRadius: '4px', border: '1px solid ' + accent, background: 'var(--ui-bg-chrome)', color: 'var(--ui-text-primary)' },
      }),
      jsx('button', { onClick: commitRename, style: { fontSize: '10px', padding: '0 4px', cursor: 'pointer', color: accent, background: 'transparent', border: 'none' }, children: 'ok' }),
      jsx('button', { onClick: () => setEditing(false), style: { fontSize: '10px', padding: '0 4px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: 'cancel' }),
    ] : [
      // checkbox (visible rows only): check the records you want to KEEP, then
      // press Save to vault — the checked ones are committed and drop off the list.
      !hidden && jsx('input', {
        type: 'checkbox',
        checked: !!checked,
        onChange: () => { haptic('tap'); onCheck() },
        title: 'Check to keep this record, then press Save to vault',
        style: { flex: '0 0 auto', margin: 0, width: '12px', height: '12px', cursor: 'pointer', accentColor: '#22c55e' },
      }),
      jsx('span', {
        onClick: () => { if (!hidden) { setEditing(true); setDraft(base) } },
        title: hidden ? base : 'Rename ' + base,
        style: { flex: 1, minWidth: 0, color: hidden ? faint : 'var(--ui-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', cursor: 'default' },
        children: base,
      }),
      jsx('span', { style: { flex: '0 0 auto', color: faint, fontSize: '9.5px' }, children: date }),
      hidden
        ? jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '2px', flex: '0 0 auto' }, children: [
            jsx('button', { onClick: () => { haptic('tap'); onRestore() }, title: 'Restore this record', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: accent, background: 'transparent', border: 'none' }, children: '↩' }),
            arming
              ? jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '2px', flex: '0 0 auto' }, children: [
                  jsx('span', { style: { fontSize: '9px', color: faint }, children: 'clear?' }),
                  jsx('button', { onClick: () => { setArming(false); onDelete() }, style: { fontSize: '9.5px', fontWeight: 700, padding: '0 3px', cursor: 'pointer', color: 'var(--ui-text-primary)', background: 'transparent', border: 'none' }, children: 'yes' }),
                  jsx('button', { onClick: () => setArming(false), style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: 'no' }),
                ] })
              : jsx('button', { onClick: () => setArming(true), title: 'Clear (delete) this record', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: '×' }),
          ] })
        : jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '2px', flex: '0 0 auto' }, children: [
            jsx('button', { onClick: reveal, title: 'Reveal in Finder', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: 'find' }),
            jsx('button', { onClick: () => { setEditing(true); setDraft(base) }, title: 'Rename', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: '✎' }),
            jsx('button', { onClick: () => { haptic('tap'); onHide() }, title: 'Hide this record (restorable)', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: '⊘' }),
            arming
              ? jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '2px', flex: '0 0 auto' }, children: [
                  jsx('span', { style: { fontSize: '9px', color: faint }, children: 'clear?' }),
                  jsx('button', { onClick: () => { setArming(false); onDelete() }, style: { fontSize: '9.5px', fontWeight: 700, padding: '0 3px', cursor: 'pointer', color: 'var(--ui-text-primary)', background: 'transparent', border: 'none' }, children: 'yes' }),
                  jsx('button', { onClick: () => setArming(false), style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: 'no' }),
                ] })
              : jsx('button', { onClick: () => setArming(true), title: 'Clear (delete) this record', style: { fontSize: '9.5px', padding: '0 3px', cursor: 'pointer', color: faint, background: 'transparent', border: 'none' }, children: '×' }),
          ] }),
    ],
  })
}

export default {
  id: 'meeting-overlay',
  name: 'Meeting Overlay',
  description: 'Live meeting transcript + answer pane for the meeting-mode copilot.',
  defaultEnabled: true,
  register(ctx) {
    rest.fn = (path, opts) => ctx.rest(path, opts)
    os.fn = ctx.os || null

    const disposePane = ctx.register({
      id: 'pane', area: 'panes', title: 'Meeting',
      data: { placement: 'right', width: '340px' },
      render: () => jsx(MeetingPane, {}),
    })

    ctx.onDispose(() => { disposePane(); rest.fn = null; os.fn = null })
  },
}