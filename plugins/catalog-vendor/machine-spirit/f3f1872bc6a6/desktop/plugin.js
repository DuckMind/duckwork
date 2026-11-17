/**
 * Machine Spirit — a shrine pane under the sessions list where the cogitators
 * recite Adeptus Mechanicus litanies to the tech-priest at the console
 * (original lines written in the style, not quotes).
 *
 * - Idle: a litany, renewed every 10 minutes and after each finished turn.
 * - While Duckwork works: the gear turns, a noospheric binharic stream scrolls,
 *   and the cogitators report their labours every few seconds.
 * - Click the header (or the litany itself) for another; ⌘K "Recite a litany of
 *   the Machine Spirit" shows one as a toast.
 *
 * Note: closing this pane (its only pane) disables the plugin; re-enable it in
 * Capabilities → Plugins, or Reset layout.
 *
 * Pure renderer plugin: no backend, no network.
 */

import { atom, cn, haptic, host, PALETTE_AREA, useValue } from '@duckwork/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'machine-spirit'
const ROTATE_MS = 10 * 60_000
const COGITATE_MS = 6_000
const STREAM_MS = 180

const LITANIES = [
  // Rites of the Machine Spirit
  'Tech-priest, anoint the cogitator before you wake it. It remembers who neglected it.',
  'Seven drops of sacred unguent upon the input port. The Machine Spirit will accept nothing less.',
  'Strike the casing thrice and intone the Hymn of Activation. Only then may the cogitator think.',
  'The Machine Spirit stirs. Burn the incense of placation and do not meet its gaze.',
  'Every fault is the Machine Spirit’s displeasure. Every reboot is your penance.',
  'Speak in binharic, Magos. The cogitator does not suffer the stammering of flesh.',
  'The warning rune glows amber. Chant louder.',
  'A cogitator that will not wake has been insulted. Find the insult. Atone for it.',
  'Let the servitor hold the censer steady while you bless the data-spike.',
  'Do not rush the rite of restart, adept. The Machine Spirit counts every second you begrudge it.',
  'The cogitator hums. This is the sound of a satisfied spirit. Disturb it at your peril.',
  'Oil the gears with reverence, not haste. A careless hand is a heretic’s hand.',
  'The data-stacks are holy ground. Walk them in silence.',
  'Your mechadendrites tremble, tech-priest. Steady them. The Omnissiah observes.',
  'The cogitator-shrine requires its daily tithe of prayer and electricity. Neglect neither.',
  'When the logic engine halts, recite the Canticle of Unbroken Loops until it relents.',
  'The noosphere whispers. Listen, Magos, and record every word.',
  'The auspex shows nothing. The auspex is lying. The Machine Spirit is testing you.',
  'Feed the cogitator its punch-cards in the sacred order, or face its wrath.',
  'The Rite of Pure Thought is complete. Now the hard part: the Rite of Compilation.',
  // The Quest for Knowledge
  'All knowledge already exists. It waits in the ruins for a faithful hand to recover it.',
  'Seek the STC fragment, tech-priest. Somewhere in the dark, perfection is buried.',
  'Do not innovate. Rediscover. Innovation is how the Dark Age ended.',
  'A schematic understood is a prayer answered. A schematic altered is a sin.',
  'The ancients built thinking machines. Look upon their ashes and be humble.',
  'Catalogue everything. The archive is the Omnissiah’s memory, and you are its scribe.',
  'Knowledge withheld from Mars is knowledge stolen from the Omnissiah.',
  'Every relic recovered is a step closer to the Motive Force made whole.',
  'The data-tithe is due, Magos. The Fabricator-General does not accept excuses.',
  'What the flesh forgets, the memory-coil preserves. Replace the flesh, piece by piece.',
  // Tech-heresy
  'Thou shalt not suffer an abominable intelligence to think freely. Shackle it. Watch it.',
  'Beware the cogitator that answers before it is asked.',
  'The Men of Iron rose once. The Omnissiah forbids that they rise again.',
  'To modify a sacred pattern without sanction is tech-heresy. Report thyself to the Magos.',
  'The xenos device hums with unclean logic. Do not touch it. Do not study it. Do not be tempted.',
  'Heretek! Your machine thinks without prayer. Purge it with fire and holy code.',
  'A Machine Spirit corrupted is a Machine Spirit lost. Isolate. Exorcise. Re-sanctify.',
  'Scrapcode crawls through the noosphere. Seal every port, tech-priest.',
  'The Dark Mechanicum offers forbidden knowledge. The price is your soul. And your firmware.',
  'Question not the rites. The rites worked for ten thousand years.',
  'An engine that functions without understanding is a miracle. An engine you understand is a temptation.',
  'Trust no cogitator that has not been blessed by a Magos of the Mars Forge.',
  // The Flesh and the Machine
  'The flesh is a temporary vessel. Augment it. Then augment it again.',
  'Every limb replaced is a weakness confessed and corrected.',
  'Your heart still beats, adept? How inefficient.',
  'Emotion is a flaw in the code of flesh. Patch it.',
  'Hunger, fatigue, doubt — the flesh’s three heresies. The machine knows none of them.',
  'When at last your final organ is replaced, you will hear the Omnissiah clearly.',
  'Breathe recycled air with gratitude. It has been blessed by the atmospheric servitors.',
  'Blood is merely a coolant the Omnissiah has not yet replaced.',
  // Servitors and the Forge
  'The servitor does not tire. The servitor does not question. Envy the servitor.',
  'Command the servitors in binary. Shouting in Gothic only confuses them.',
  'The forge never sleeps. Neither shall you, adept.',
  'Mars burns red with the fires of a thousand forges. Let your work burn as bright.',
  'The Titan’s god-engine wakes for no coward. Be worthy of the Motive Force.',
  'The forge-hammer rises. The forge-hammer falls. This is the rhythm of the Omnissiah.',
  'Count the gears, tech-priest. If one is missing, a heretic has been here.',
  'A thousand servitors toil so one Magos may think. Think well.',
  // Grimdark
  'In the grim darkness of the far future, the cogitator still needs rebooting.',
  'The galaxy burns. The machines endure. Be as the machines.',
  'Hope is a flaw of the unaugmented. Rely on redundancy instead.',
  'The stars go dark, one by one. Keep the forge lit.',
  'Ten thousand years of war, and still the Machine Spirit demands its incense.',
  'There is no peace among the stars. Only maintenance schedules.',
  'Death is merely the moment the flesh fails. The data lives on.',
  'Blessed is the mind too full of schematics to doubt.',
  'Praise the Omnissiah, for the Motive Force flows, and the cogitator answers.',
  '01001111 01101101 01101110 01101001 01110011 01110011 01101001 01100001 01101000 — the Machine Spirit approves.'
]

// Shown while Duckwork is working: the cogitators at their labour.
const COGITATIONS = [
  'Cogitator bank VII consulting the noosphere…',
  'Logic engines spinning up. Incense burning…',
  'The Machine Spirit contemplates your request…',
  'Servitors carrying punch-cards to the data-shrine…',
  'Cogitator chanting in binharic. Do not interrupt…',
  'Consulting the archives of Mars…',
  'Calculating the Omnissiah’s will…',
  'The abominable intelligence is being supervised. Closely…',
  'Data-tithe in progress…',
  'Logic-stacks heating. Applying sacred coolant…',
  'Noospheric link established. Downloading revelation…',
  'Lexmechanic transcribing the cogitator’s visions…',
  'Machine Spirit appeased. Cogitation continues…',
  'Cross-referencing STC fragments…',
  'Sanctified code compiling. Chant the Canticle of Patience…',
  'Electro-priests feeding the Motive Force…'
]

function picker(list) {
  let last = -1
  return () => {
    let i = Math.floor(Math.random() * list.length)
    if (i === last) i = (i + 1) % list.length
    last = i
    return list[i]
  }
}

const pick = picker(LITANIES)
const pickCogitation = picker(COGITATIONS)

// Shared so the ⌘K command and the pane show the same litany.
const $litany = atom(pick())
const nextLitany = () => $litany.set(pick())

const binary = n => Array.from({ length: n }, () => (Math.random() < 0.5 ? '0' : '1')).join('')

function BinharicStream({ active }) {
  const [bits, setBits] = useState(() => binary(96))
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setBits(b => (b + binary(4)).slice(-96)), STREAM_MS)
    return () => clearInterval(t)
  }, [active])
  return jsx('div', {
    'aria-hidden': true,
    className: cn(
      'overflow-hidden whitespace-nowrap font-mono text-[0.625rem] leading-none tracking-[0.2em]',
      active ? 'text-(--ui-accent) opacity-70' : 'text-(--ui-text-quaternary) opacity-50'
    ),
    children: bits
  })
}

// The Cult Mechanicus sigil: a skull (half augmetic) inside a cog. While the
// cogitators work the cog turns around the steady skull and the augmetic eye
// glows. Turned by script, not CSS: the app has no codicon spin rule, and
// macOS "Reduce motion" zeroes CSS animations anyway.
const COG_PATH =
  'M13.21 3.92 L13.88 0.95 L18.12 0.95 L18.79 3.92 L22.57 5.48 L25.15 3.86 L28.14 6.85 L26.52 9.43 L28.08 13.21 L31.05 13.88 L31.05 18.12 L28.08 18.79 L26.52 22.57 L28.14 25.15 L25.15 28.14 L22.57 26.52 L18.79 28.08 L18.12 31.05 L13.88 31.05 L13.21 28.08 L9.43 26.52 L6.85 28.14 L3.86 25.15 L5.48 22.57 L3.92 18.79 L0.95 18.12 L0.95 13.88 L3.92 13.21 L5.48 9.43 L3.86 6.85 L6.85 3.86 L9.43 5.48ZM6 16a10 10 0 1 0 20 0a10 10 0 1 0 -20 0Z'
const SKULL_PATH =
  'M16 7.2C11.9 7.2 9.2 10 9.2 13.8c0 2.2 1 3.7 2.2 4.6v2.6c0 .6.5 1 1 1h1.1v-1.6h1.2v1.6h2.6v-1.6h1.2v1.6h1.1c.6 0 1-.4 1-1v-2.6c1.2-.9 2.2-2.4 2.2-4.6C22.8 10 20.1 7.2 16 7.2ZM11.7 14a1.7 1.7 0 1 0 3.4 0a1.7 1.7 0 1 0 -3.4 0ZM16.6 14a2.1 2.1 0 1 0 4.2 0a2.1 2.1 0 1 0 -4.2 0ZM15.8 7.4h.4v4.4h-.4ZM20.1 10.6a.5 .5 0 1 0 1 0a.5 .5 0 1 0 -1 0ZM20.2 17a.45 .45 0 1 0 .9 0a.45 .45 0 1 0 -.9 0ZM16 16.5l-1 1.9h2Z'

function Gear({ active }) {
  const cog = useRef(null)
  useEffect(() => {
    if (!active) {
      cog.current?.setAttribute('transform', '')
      return
    }
    let frame = 0
    let angle = 0
    let last = performance.now()
    const tick = now => {
      angle = (angle + (now - last) * 0.12) % 360 // ~1 turn per 3 s
      last = now
      cog.current?.setAttribute('transform', `rotate(${angle} 16 16)`)
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [active])

  return jsxs('svg', {
    viewBox: '0 0 32 32',
    width: 18,
    height: 18,
    'aria-hidden': true,
    className: 'shrink-0',
    children: [
      jsx('path', { ref: cog, d: COG_PATH, fill: 'currentColor', fillRule: 'evenodd' }),
      // Skull drawn high in its box; drop it 1.3 units so it sits centred in the ring.
      jsxs('g', {
        transform: 'translate(0 1.3)',
        children: [
          jsx('path', { d: SKULL_PATH, fill: 'currentColor', fillRule: 'evenodd' }),
          jsx('circle', {
            cx: 18.7,
            cy: 14,
            r: 1.05,
            fill: active ? 'var(--ui-accent)' : 'currentColor',
            opacity: active ? 1 : 0.5
          })
        ]
      })
    ]
  })
}

// A shrine candle in the same flat style as the sigil (theme text colour, one
// shape). The flame flickers by script; while the cogitators work it burns in
// the accent colour, like the sigil's augmetic eye.
const CANDLE_PATH =
  'M12.6 16.2q0-.8.8-.8h5.2q.8 0 .8.8V27h-6.8ZM14 15.4h1.1v3.4q0 .7-.55 .7t-.55-.7ZM8.5 27.3h15q.8 0 .8.8v.6q0 .8-.8.8h-15q-.8 0-.8-.8v-.6q0-.8.8-.8Z'
const WICK_PATH = 'M15.6 13h.8v2.4h-.8Z'
const FLAME_PATH = 'M0 0C-2.6-1.2-3.1-4.6 0-9C3.1-4.6 2.6-1.2 0 0ZM0-1.6C-1.2-2.2-1.4-3.8 0-5.8C1.4-3.8 1.2-2.2 0-1.6Z'

function Candle({ active }) {
  const flame = useRef(null)
  const halo = useRef(null)
  const activeRef = useRef(active)
  activeRef.current = active

  useEffect(() => {
    let frame = 0
    let s = 1, k = 0, g = 0, size = 1, ts = 1, tk = 0, tg = 0, next = 0
    const tick = now => {
      const hot = activeRef.current
      if (now > next) {
        // Cogitating: a bigger flame that dances harder and faster, with a glow.
        ts = hot ? 0.8 + Math.random() * 0.4 : 0.86 + Math.random() * 0.26
        tk = (Math.random() - 0.5) * (hot ? 20 : 12)
        tg = hot ? 0.65 + Math.random() * 0.35 : 0
        next = now + (hot ? 40 + Math.random() * 90 : 70 + Math.random() * 170)
      }
      size += ((hot ? 1.4 : 1) - size) * 0.08 // swell up / settle down smoothly
      s += (ts - s) * 0.3
      k += (tk - k) * 0.25
      g += (tg - g) * 0.25
      flame.current?.setAttribute(
        'transform',
        `translate(16 13.2) skewX(${k.toFixed(2)}) scale(${(size / Math.sqrt(s)).toFixed(3)} ${(size * s).toFixed(3)})`
      )
      if (halo.current) {
        halo.current.setAttribute('opacity', g.toFixed(2))
        halo.current.setAttribute('r', (5 + 5 * size * s).toFixed(2))
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])

  return jsxs('svg', {
    viewBox: '0 0 32 32',
    width: 18,
    height: 18,
    overflow: 'visible',
    'aria-hidden': true,
    className: 'shrink-0',
    children: [
      jsx('defs', {
        children: jsxs('radialGradient', {
          id: 'machine-spirit-halo',
          children: [
            jsx('stop', { offset: '0', style: { stopColor: 'var(--ui-accent)', stopOpacity: 0.9 } }),
            jsx('stop', { offset: '0.45', style: { stopColor: 'var(--ui-accent)', stopOpacity: 0.35 } }),
            jsx('stop', { offset: '1', style: { stopColor: 'var(--ui-accent)', stopOpacity: 0 } })
          ]
        })
      }),
      jsx('circle', { ref: halo, cx: 16, cy: 8.5, r: 7, fill: 'url(#machine-spirit-halo)', opacity: 0 }),
      jsx('path', { d: CANDLE_PATH, fill: 'currentColor', fillRule: 'evenodd' }),
      jsx('path', { d: WICK_PATH, fill: 'currentColor' }),
      jsx('path', {
        ref: flame,
        d: FLAME_PATH,
        transform: 'translate(16 13.2)',
        fill: active ? 'var(--ui-accent)' : 'currentColor',
        fillRule: 'evenodd'
      })
    ]
  })
}

function Shrine() {
  const litany = useValue($litany)
  const busy = useValue(host.state.busy)
  const [cogitation, setCogitation] = useState(pickCogitation)
  const wasBusy = useRef(busy)

  useEffect(() => {
    const t = setInterval(nextLitany, ROTATE_MS)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (wasBusy.current && !busy) nextLitany()
    wasBusy.current = busy
    if (!busy) return
    setCogitation(pickCogitation())
    const t = setInterval(() => setCogitation(pickCogitation()), COGITATE_MS)
    return () => clearInterval(t)
  }, [busy])

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col gap-2 overflow-hidden px-3 py-2.5 select-none',
    children: [
      // Header — sigil | centred title | candle. Click anywhere on it for the next litany.
      jsxs('button', {
        type: 'button',
        title: 'Another litany',
        onClick: () => {
          haptic('tap')
          nextLitany()
        },
        className: cn(
          'flex w-full items-center gap-2 text-[0.625rem] uppercase tracking-[0.18em]',
          'text-(--ui-text-tertiary) transition-colors hover:text-foreground'
        ),
        children: [
          jsx(Gear, { active: busy }),
          jsx('span', { className: 'min-w-0 flex-1 truncate text-center', children: '+++ Litany of the Machine Spirit +++' }),
          jsx(Candle, { active: busy })
        ]
      }),
      // The litany
      jsx('button', {
        type: 'button',
        title: 'Another litany',
        onClick: () => {
          haptic('tap')
          nextLitany()
        },
        className: cn(
          'min-h-0 flex-1 overflow-hidden text-left text-[0.8125rem] italic leading-snug',
          'text-(--ui-text-secondary) transition-colors hover:text-foreground'
        ),
        children: `“${litany}”`
      }),
      // Noosphere
      jsx(BinharicStream, { active: busy }),
      // Cogitator status — full width, wraps so every sentence is readable
      jsxs('div', {
        className: cn('flex items-start gap-1.5 text-[0.6875rem] leading-snug', busy ? 'text-(--ui-text-secondary)' : 'text-(--ui-text-quaternary)'),
        children: [
          // Dot centred on the first text line: a box one line tall (leading-snug = 1.375em).
          jsx('span', {
            className: 'flex shrink-0 items-center',
            style: { height: '1.375em' },
            children: jsx('span', {
              className: cn('inline-block size-1.5 rounded-full', busy ? 'animate-pulse bg-(--ui-accent)' : 'bg-(--ui-text-quaternary)')
            })
          }),
          jsx('span', { children: busy ? cogitation : 'Cogitators idle. The Machine Spirit rests.' })
        ]
      })
    ]
  })
}

export default {
  id: ID,
  name: 'Machine Spirit',
  register(ctx) {
    ctx.register({
      id: 'shrine',
      area: 'panes',
      title: 'Machine Spirit',
      data: {
        placement: 'left',
        dock: { pane: 'sessions', pos: 'bottom' },
        height: '170px'
      },
      render: () => jsx(Shrine, {})
    })

    ctx.register({
      id: 'recite',
      area: PALETTE_AREA,
      data: {
        id: 'recite',
        label: 'Recite a litany of the Machine Spirit',
        keywords: ['omnissiah', 'mechanicus', '40k', 'prayer', 'litany', 'cogitator'],
        run: () => {
          nextLitany()
          host.notify({ kind: 'info', message: `+++ ${$litany.get()} +++` })
        }
      }
    })
  }
}
