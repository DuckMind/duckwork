/**
 * duckwork-boot-screen — Duckwork desktop boot animation plugin
 * ============================================================================
 * Adapted from dsh-startup-screen (DeepSeek Harness boot animation, MIT © Shen Honghong).
 * Six-act boot animation: black-screen mark → overexposed wash → warm-white technical
 * dossier backdrop → five-step interactive access authorization → chromatic-aberration
 * glitch reveal. The original injected itself via index.html; this adaptation uses the
 * desktop plugin SDK instead: register() synchronously injects the styles and the
 * black-screen root node, and the runtime is wrapped as the runSplash() function.
 *
 * Audio assets (five spoken lines + finale + UI sound effects) are embedded as base64 —
 * a desktop plugin loads as a single file with no HTTP route available; when an asset is
 * missing it falls back to Web Speech TTS / WebAudio synthesis, so no feature depends on
 * the assets being present.
 *
 * This file is assembled by build.py from src/ — edit src/ then re-run build.py.
 */

import {
  host,
  haptic,
  APPEARANCE_AREAS,
  PALETTE_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  ToggleRow,
  ListRow,
  SegmentedControl,
  Input,
  Button
} from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState } from 'react'

const ID = 'duckwork-boot-screen'
const ROOT_ID = 'duckwork-startup-root'
const STYLE_ID = 'duckwork-boot-screen-style'
const STORAGE_KEY = 'config'
/** Kept in sync with the key written by the runtime's finish() (build-verified). */
const SHOWN_KEY = 'duckwork-boot-screen:shown'
const DAY_KEY = 'duckwork-boot-screen:day'

/* ── Config model (DEFAULTS is extracted from the runtime source by the build script — single source of truth) ── */
/*@DEFAULTS_AND_NORMALIZE@*/

/* ── Embedded assets ───────────────────────────────────────────────────────────── */
const SPLASH_CSS = /*@SPLASH_CSS@*/
const ASSET_URIS = /*@ASSET_URIS@*/
const GLYPH_D = /*@GLYPH_D@*/

/* ── Boot animation runtime (reshaped from src/splash.js and injected by the build script) ── */
/*@RUN_SPLASH@*/

/* ── Config read/write ───────────────────────────────────────────────────────────── */

function readCfg(ctx) {
  try {
    return normalize(ctx.storage.get(STORAGE_KEY, null))
  } catch (e) {
    return normalize(null)
  }
}

function writeCfg(ctx, next) {
  const cfg = normalize(next)
  try {
    ctx.storage.set(STORAGE_KEY, cfg)
  } catch (e) {
    /* when storage is unavailable the config only lives for this window */
  }
  return cfg
}

/* ── Playback control ───────────────────────────────────────────────────────────── */

let gCtx = null
let styleInjected = false

/** Injects styles: the full splash.css + the critical black-screen rules (equivalent to the original CRITICAL_CSS). */
function injectStyle() {
  if (document.getElementById(STYLE_ID)) return
  const el = document.createElement('style')
  el.id = STYLE_ID
  el.textContent =
    'html.dsu-lock,html.dsu-lock body{overflow:hidden!important}' +
    '#' + ROOT_ID + '.dsu-boot{position:fixed;inset:0;z-index:2147483000;background:#000}' +
    SPLASH_CSS
  document.head.appendChild(el)
  styleInjected = true
}

/** Asset lookup: base64 data URI table → fetch; a missing entry rejects and the caller's .catch falls back naturally. */
function fetchAsset(name) {
  const u = ASSET_URIS[name]
  if (!u) return Promise.reject(new Error('missing asset: ' + name))
  return fetch(u)
}

/** Whether this launch should play — the decision matches the original BOOTSTRAP_JS semantics. */
function shouldPlay(cfg) {
  if (!cfg.enabled) return false
  try {
    if (cfg.mode === 'session' && window.sessionStorage.getItem(SHOWN_KEY) === '1') return false
    if (cfg.mode === 'daily' && window.localStorage.getItem(DAY_KEY) === new Date().toISOString().slice(0, 10)) return false
  } catch (e) {
    /* private mode can't be read — treat it as playable */
  }
  return true
}

/**
 * Plays the boot animation once. force=true bypasses the mode gate (settings preview / palette command).
 * Timing matches the original Host injection: critical styles + the black-screen root node go first
 * (synchronously), then the runtime reuses that root node to fill the DOM and reveal.
 */
function play(ctx, force) {
  const cfg = readCfg(ctx)
  if (!force && !shouldPlay(cfg)) return false

  stopInternal(false)

  window.__DSH_STARTUP__ = cfg
  window.__DSH_STARTUP_LOADED__ = false
  window.__DSH_STARTUP_SKIP__ = false

  injectStyle()

  let root = document.getElementById(ROOT_ID)
  if (!root) {
    root = document.createElement('div')
    root.id = ROOT_ID
    root.className = 'dsu-root dsu-boot'
    document.body.appendChild(root)
  } else {
    root.classList.add('dsu-boot')
  }
  document.documentElement.classList.add('dsu-lock')
  document.documentElement.style.overflow = 'hidden'

  /* Bridge for the runtime's API.replay: hands "replay after a config change" to the plugin's full lifecycle. */
  window.__HS_REPLAY__ = function () {
    if (gCtx) replay(gCtx)
  }

  try {
    runSplash()
  } catch (err) {
    console.error('[duckwork-boot-screen] animation failed to start:', err)
    teardown()
    host.notify({ kind: 'error', message: 'Startup animation failed to load — this playback was skipped' })
    return false
  }

  /* Fallback: if the runtime hasn't taken over within 12 seconds (its own 9-second timeout plus slack),
     let the user through unconditionally — never trap them behind a black screen. */
  window.setTimeout(function () {
    try {
      const r = document.getElementById(ROOT_ID)
      if (r && r.classList.contains('dsu-boot')) teardown()
    } catch (e) { /* noop */ }
  }, 12000)

  return true
}

/** Immediately stops the current animation and cleans up its DOM (styles are left in place). */
function stopInternal(removeStyle) {
  try {
    const api = window.__DSH_STARTUP_API__
    if (api && typeof api.finish === 'function') api.finish()
  } catch (e) { /* noop */ }
  const old = document.getElementById(ROOT_ID)
  if (old && old.parentNode) old.parentNode.removeChild(old)
  document.documentElement.classList.remove('dsu-lock')
  document.documentElement.style.overflow = ''
  if (document.body) document.body.style.overflow = ''
  if (removeStyle) {
    const st = document.getElementById(STYLE_ID)
    if (st && st.parentNode) st.parentNode.removeChild(st)
    styleInjected = false
  }
}

/** Full cleanup: called when the plugin is unloaded or disabled. */
function teardown() {
  stopInternal(true)
}

/** Forced replay (palette command / settings preview). */
function replay(ctx) {
  return play(ctx, true)
}

/* ── Settings card (Settings → Appearance, bottom of page) ───────────────────────── */

const GROUP_LABEL = {
  fontSize: '11px',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--ui-text-tertiary)',
  marginTop: '18px',
  marginBottom: '2px'
}

const ROW_HINT = {
  fontSize: '11px',
  lineHeight: 1.55,
  color: 'var(--ui-text-quaternary)'
}

const RANGE_WRAP = { display: 'flex', alignItems: 'center', gap: '10px', width: '100%' }
const RANGE_INPUT = { flex: 1, accentColor: 'var(--ui-accent)' }
const RANGE_VAL = {
  fontFamily: 'ui-monospace, Consolas, monospace',
  fontSize: '11px',
  color: 'var(--ui-text-tertiary)',
  minWidth: '42px',
  textAlign: 'right'
}
const COLOR_INPUT = {
  width: '46px',
  height: '26px',
  padding: 0,
  border: '1px solid var(--ui-stroke-secondary)',
  borderRadius: '6px',
  background: 'transparent',
  cursor: 'pointer'
}
const TEXT_INPUT = { width: '100%', maxWidth: '360px' }

function RangeRow({ label, hint, min, max, step, value, onChange, fmt }) {
  return jsx(ListRow, {
    title: label,
    description: hint ? jsx('span', { style: ROW_HINT, children: hint }) : undefined,
    action: jsx('div', { style: RANGE_WRAP, children: [
      jsx('input', {
        type: 'range',
        min: min,
        max: max,
        step: step,
        value: value,
        style: RANGE_INPUT,
        onInput: e => onChange(Number(e.target.value))
      }),
      jsx('span', { style: RANGE_VAL, children: fmt ? fmt(value) : String(value) })
    ] })
  })
}

function TextRow({ label, hint, value, mono, onChange }) {
  return jsx(ListRow, {
    title: label,
    description: hint ? jsx('span', { style: ROW_HINT, children: hint }) : undefined,
    action: jsx(Input, {
      value: value == null ? '' : String(value),
      maxLength: 64,
      style: TEXT_INPUT,
      className: mono ? 'font-mono text-xs' : undefined,
      onChange: e => onChange(e.target.value)
    })
  })
}

function ColorRow({ label, hint, value, onChange }) {
  return jsx(ListRow, {
    title: label,
    description: hint ? jsx('span', { style: ROW_HINT, children: hint }) : undefined,
    action: jsx('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' }, children: [
      jsx('input', {
        type: 'color',
        value: value,
        style: COLOR_INPUT,
        onInput: e => onChange(e.target.value)
      }),
      jsx('span', { style: RANGE_VAL, children: value })
    ] })
  })
}

function Group({ title, children }) {
  return jsxs('div', { children: [
    jsx('div', { style: GROUP_LABEL, children: title }),
    jsx('div', { style: { display: 'flex', flexDirection: 'column' }, children: children })
  ] })
}

/* ── Standalone settings page (route /startup-animation, reached directly from the sidebar) ──────────────
   The official APPEARANCE_AREAS.extra mount condition `subpage === undefined` is unreachable in the
   current build (resolveSettingsSubpage always returns a subpage id), so the config panel uses ROUTES_AREA. */
function SettingsPage() {
  return jsxs('div', { style: { padding: '20px 24px 32px', maxWidth: 720 }, children: [
    jsxs('div', { style: { marginBottom: 16 }, children: [
      jsx('h1', { style: { fontSize: 18, fontWeight: 650, margin: '0 0 4px' }, children: 'Startup Animation' }),
      jsx('p', { style: { fontSize: 12.5, opacity: 0.65, margin: 0 }, children: 'Six-act boot sequence: black mark → overexposed wash → dossier backdrop → five-step authorization → chromatic-aberration reveal.' })
    ] }),
    jsx(AppearanceCard, {})
  ] })
}

function AppearanceCard() {
  const [cfg, setCfg] = useState(() => (gCtx ? readCfg(gCtx) : normalize(null)))
  const [playing, setPlaying] = useState(false)

  if (!gCtx) return null

  function set(key, value) {
    const next = writeCfg(gCtx, { ...cfg, [key]: value })
    setCfg(next)
  }

  function preview() {
    haptic('tap')
    setPlaying(true)
    const ok = replay(gCtx)
    if (!ok) setPlaying(false)
    window.setTimeout(() => setPlaying(false), 1200)
  }

  function reset() {
    haptic('tap')
    const next = writeCfg(gCtx, { ...DEFAULTS })
    setCfg(next)
  }

  const modeOptions = [
    { id: 'always', label: 'Always' },
    { id: 'session', label: 'Each launch' },
    { id: 'daily', label: 'Daily' }
  ]

  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', paddingTop: '10px' },
    children: [
      /* Page header: title + version + actions */
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' },
        children: [
          jsxs('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px' }, children: [
            jsx('div', { style: { fontSize: '14px', fontWeight: 600, color: 'var(--ui-text-primary)' }, children: 'Startup Animation' }),
            jsx('div', {
              style: { fontSize: '11px', color: 'var(--ui-text-quaternary)' },
              children: 'Six-act boot: black mark → overexposed wash → dossier backdrop → five-step authorization → reveal'
            })
          ] }),
          jsxs('div', { style: { display: 'flex', gap: '8px' }, children: [
            jsx(Button, {
              size: 'sm',
              disabled: playing,
              onClick: preview,
              children: playing ? 'Playing…' : 'Play now'
            }),
            jsx(Button, {
              variant: 'outline',
              size: 'sm',
              onClick: reset,
              children: 'Reset to defaults'
            })
          ] })
        ]
      }),

      /* ── Playback ── */
      jsx(Group, {
        title: 'Playback',
        children: [
          jsx(ToggleRow, {
            label: 'Enabled',
            description: 'When off, the boot animation never plays (settings and commands stay available)',
            checked: cfg.enabled,
            onChange: v => set('enabled', v)
          }),
          jsx(ListRow, {
            title: 'When to play',
            description: jsx('span', { style: ROW_HINT, children: 'Always = every time you open the app / Each launch = once per session / Daily = first time each day' }),
            action: jsx(SegmentedControl, { options: modeOptions, value: cfg.mode, onChange: v => set('mode', v) })
          }),
          jsx(ListRow, {
            title: 'Theme',
            action: jsx(SegmentedControl, {
              options: [{ id: 'light', label: 'Warm white' }, { id: 'dark', label: 'Dark' }],
              value: cfg.theme,
              onChange: v => set('theme', v)
            })
          }),
          jsx(RangeRow, {
            label: 'Speed',
            hint: 'Playback speed for the whole animation',
            min: 0.35, max: 3, step: 0.05,
            value: cfg.speed,
            fmt: v => v.toFixed(2) + '×',
            onChange: v => set('speed', v)
          }),
          jsx(ToggleRow, {
            label: 'Require confirmation',
            description: 'Steps 1 and 2 wait for you to click a button or press Enter',
            checked: cfg.requireInteraction,
            onChange: v => set('requireInteraction', v)
          }),
          jsx(ToggleRow, {
            label: 'Allow skip',
            description: 'Shows a SKIP button in the top-right corner and responds to Esc',
            checked: cfg.allowSkip,
            onChange: v => set('allowSkip', v)
          })
        ]
      }),

      /* ── Identity ── */
      jsx(Group, {
        title: 'Identity',
        children: [
          jsx(TextRow, {
            label: 'Name',
            hint: 'The name used in the finale "welcome, <name>"',
            value: cfg.identity,
            onChange: v => set('identity', v)
          }),
          jsx(TextRow, {
            label: 'ID',
            hint: 'The ID shown on the step-2 identity card — derived from the name when left blank',
            value: cfg.identityId,
            mono: true,
            onChange: v => set('identityId', v)
          }),
          jsx(TextRow, {
            label: 'Access level',
            hint: 'Access level shown on the identity card',
            value: cfg.accessLevel,
            mono: true,
            onChange: v => set('accessLevel', v)
          })
        ]
      }),

      /* ── Voice ── */
      jsx(Group, {
        title: 'Voice',
        children: [
          jsx(ToggleRow, {
            label: 'Spoken narration',
            description: 'Speaks the five authorization lines (falls back to system TTS when assets are missing)',
            checked: cfg.voice,
            onChange: v => set('voice', v)
          }),
          jsx(ListRow, {
            title: 'Voice source',
            action: jsx(SegmentedControl, {
              options: [{ id: 'asset', label: 'Recorded assets' }, { id: 'tts', label: 'System TTS' }],
              value: cfg.voiceSource,
              onChange: v => set('voiceSource', v)
            })
          }),
          jsx(ListRow, {
            title: 'Language',
            description: jsx('span', { style: ROW_HINT, children: 'Only affects what gets spoken when falling back to TTS' }),
            action: jsx(SegmentedControl, {
              options: [{ id: 'en', label: 'English' }, { id: 'zh', label: 'Chinese' }, { id: 'both', label: 'Both' }],
              value: cfg.voiceLang,
              onChange: v => set('voiceLang', v)
            })
          }),
          jsx(ToggleRow, {
            label: 'Chime before speaking',
            description: 'Plays a soft double chime before each line, like a system announcement',
            checked: cfg.voiceCue,
            onChange: v => set('voiceCue', v)
          }),
          jsx(RangeRow, {
            label: 'Speech rate',
            min: 0.5, max: 2, step: 0.01,
            value: cfg.voiceRate,
            fmt: v => v.toFixed(2),
            onChange: v => set('voiceRate', v)
          }),
          jsx(RangeRow, {
            label: 'Pitch',
            hint: 'Lower sounds steadier; above 1.0 sounds like a call-center readout',
            min: 0, max: 2, step: 0.01,
            value: cfg.voicePitch,
            fmt: v => v.toFixed(2),
            onChange: v => set('voicePitch', v)
          }),
          jsx(RangeRow, {
            label: 'Voice volume',
            min: 0, max: 1, step: 0.01,
            value: cfg.voiceVolume,
            fmt: v => Math.round(v * 100) + '%',
            onChange: v => set('voiceVolume', v)
          }),
          jsx(RangeRow, {
            label: 'Delay before speaking',
            hint: 'How long to wait after the chime before the first word',
            min: 0, max: 1200, step: 20,
            value: cfg.voiceLead,
            fmt: v => v + ' ms',
            onChange: v => set('voiceLead', v)
          })
        ]
      }),

      /* ── UI sounds ── */
      jsx(Group, {
        title: 'UI Sounds',
        children: [
          jsx(ToggleRow, {
            label: 'UI sounds',
            description: 'The "tick" played when text appears, a stage advances, and a button is confirmed',
            checked: cfg.sound,
            onChange: v => set('sound', v)
          }),
          jsx(RangeRow, {
            label: 'Sound volume',
            hint: 'Does not affect the spoken voice',
            min: 0, max: 1, step: 0.01,
            value: cfg.soundVolume,
            fmt: v => Math.round(v * 100) + '%',
            onChange: v => set('soundVolume', v)
          }),
          jsx(ListRow, {
            title: 'Sound source',
            action: jsx(SegmentedControl, {
              options: [{ id: 'audio', label: 'Bundled assets' }, { id: 'synth', label: 'Live synthesis' }],
              value: cfg.sfx,
              onChange: v => set('sfx', v)
            })
          })
        ]
      }),

      /* ── Appearance ── */
      jsx(Group, {
        title: 'Appearance',
        children: [
          jsx(ColorRow, {
            label: 'Accent color',
            hint: 'Theme color for the stage bar, progress bar, and reticle',
            value: cfg.accent,
            onChange: v => set('accent', v)
          }),
          jsx(ColorRow, {
            label: 'Glitch color A',
            hint: 'The red in the reveal chromatic-aberration glitch',
            value: cfg.glitchA,
            onChange: v => set('glitchA', v)
          }),
          jsx(ColorRow, {
            label: 'Glitch color B',
            hint: 'The blue in the reveal chromatic-aberration glitch',
            value: cfg.glitchB,
            onChange: v => set('glitchB', v)
          })
        ]
      }),

      /* ── Copy ── */
      jsx(Group, {
        title: 'Copy',
        children: [
          jsx(TextRow, { label: 'Brand line 1', value: cfg.brand1, onChange: v => set('brand1', v) }),
          jsx(TextRow, { label: 'Brand line 2', value: cfg.brand2, onChange: v => set('brand2', v) }),
          jsx(TextRow, { label: 'Brand line 3 (left)', value: cfg.brand3a, onChange: v => set('brand3a', v) }),
          jsx(TextRow, { label: 'Brand line 3 (right)', value: cfg.brand3b, onChange: v => set('brand3b', v) }),
          jsx(TextRow, { label: 'Black screen (Chinese line)', value: cfg.orgZh, onChange: v => set('orgZh', v) }),
          jsx(TextRow, { label: 'Black screen (English line)', value: cfg.orgEn, onChange: v => set('orgEn', v) }),
          jsx(TextRow, { label: 'Black screen (subtitle)', value: cfg.orgSub, onChange: v => set('orgSub', v) }),
          jsx(TextRow, { label: 'Finale box', hint: 'The black box with white text at the center of the reveal', value: cfg.welcomeBox, onChange: v => set('welcomeBox', v) }),
          jsx(TextRow, { label: 'Footer', value: cfg.footer, onChange: v => set('footer', v) })
        ]
      })
    ]
  })
}

/* ── Plugin entry point ───────────────────────────────────────────────────────────── */

export default {
  id: ID,
  name: 'Startup Animation',
  description: 'Six-act boot animation: black mark → overexposed wash → dossier backdrop → five-step authorization → reveal.',
  register(ctx) {
    /* Announces itself on load: the toast appearing means the plugin loaded and registered successfully (verification signal + pointer) */
    host.notify({ kind: 'info', message: '🚀 Startup Animation plugin loaded · Settings entry: sidebar "Startup Animation"' })
    gCtx = ctx

    /* Settings card: Settings → Appearance, bottom of page */
    ctx.register({
      id: 'appearance',
      area: APPEARANCE_AREAS.extra,
      render: () => jsx(AppearanceCard, {})
    })

    /* Settings page: a dedicated route rendering the full page (appearance.extra is unreachable in this build, so use this) */
    ctx.register({
      id: 'page',
      area: ROUTES_AREA,
      data: { path: '/startup-animation', title: 'Startup Animation' },
      render: () => jsx(SettingsPage, {})
    })

    /* Sidebar entry: paired with the route page (the official kanban pattern) */
    ctx.register({
      id: 'nav',
      area: SIDEBAR_NAV_AREA,
      order: 60,
      data: { codicon: 'play', label: 'Startup Animation', path: '/startup-animation' }
    })

    /* ⌘K command: open settings */
    ctx.register({
      id: 'open-settings',
      area: PALETTE_AREA,
      data: {
        id: 'startup-screen.settings',
        label: 'Startup Animation: Open Settings',
        keywords: ['startup', 'animation', 'settings', 'splash'],
        run: () => host.navigate('/startup-animation')
      }
    })

    /* ⌘K command: play now */
    ctx.register({
      id: 'replay',
      area: PALETTE_AREA,
      data: {
        id: 'startup-screen.replay',
        label: 'Startup Animation: Play Now',
        keywords: ['startup', 'animation', 'boot', 'splash'],
        run: () => {
          if (!replay(gCtx)) {
            host.notify({ kind: 'info', message: 'Startup animation is currently disabled (you can turn it on in Settings)' })
          }
        }
      }
    })

    /* Cold-start playback: register runs synchronously, so the black screen appears before app content */
    try {
      play(ctx, false)
    } catch (err) {
      console.error('[duckwork-boot-screen] boot playback error:', err)
    }

    ctx.onDispose(() => {
      try {
        teardown()
      } catch (e) { /* noop */ }
      gCtx = null
    })
  }
}
