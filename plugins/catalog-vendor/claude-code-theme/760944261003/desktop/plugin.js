import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import {
  COMPOSER_AREAS, host, Popover, PopoverContent, PopoverTrigger,
  atom, Input, STATUSBAR_AREAS, setAccentOverride, Switch, useTheme, useValue
} from '@duckwork/plugin-sdk'

// Claude Code Theme: a Claude Code-inspired look for Duckwork Desktop. CSS + SDK slots only.
const STYLE_ID = 'claude-code-theme-css'

const CSS = `
/* Palette: light and dark palettes */
:root {
  --ccl-bg: #fbfbf9; --ccl-card: #ffffff; --ccl-subtle: #f7f7f6; --ccl-hover: #f3f3f2;
  --ccl-bubble: #f1f1f0; --ccl-row-active: #eeedeb; --ccl-row-open: #f4f3f1;
  --ccl-border: #e2e1de; --ccl-border-strong: #d3d2ce; --ccl-divider: #ecebe8;
  --ccl-text: #171717; --ccl-code: #1f2328; --ccl-muted: #888783; --ccl-icon: #555653;
  --ccl-check: var(--ccl-text); --ccl-selection: #d9e7fb;
  --ccl-send-bg: #1a1a1a; --ccl-send-fg: #ffffff;
  --ccl-shadow: rgba(0,0,0,0.08); --ccl-shadow-sm: rgba(0,0,0,0.06); --ccl-shadow-xs: rgba(0,0,0,0.04);
}
:root.dark {
  --ccl-bg: #151515; --ccl-card: #1e1e1e; --ccl-subtle: #232323; --ccl-hover: #2a2a2a;
  --ccl-bubble: #262626; --ccl-row-active: #303030; --ccl-row-open: #242424;
  --ccl-border: #2f2f2f; --ccl-border-strong: #3d3d3d; --ccl-divider: #2b2b2b;
  --ccl-text: #e7e7e7; --ccl-code: #e6edf3; --ccl-muted: #9b9b9b; --ccl-icon: #a3a3a3;
  --ccl-selection: #264f78;
  --ccl-send-bg: #e7e7e7; --ccl-send-fg: #151515;
  --ccl-shadow: rgba(0,0,0,0.45); --ccl-shadow-sm: rgba(0,0,0,0.35); --ccl-shadow-xs: rgba(0,0,0,0.25);
}
/* One surface colour everywhere */
:root, .dark {
  --ui-chat-surface-background: var(--ccl-bg) !important;
  --ui-sidebar-surface-background: var(--ccl-bg) !important;
  --dt-background: var(--ccl-bg) !important;
}
/* Hide the statue chat backdrop regardless of the Appearance toggle */
img[src*='filler-bg0'] {
  display: none !important;
}
/* Side-panel file viewer. The whole ZONE (tab strip + editor) is the card;
   [data-tree-group] wraps both. Only zones holding a file viewer qualify. */
[data-tree-group]:has(aside :is(.cm-editor, .preview-source-code, [data-preview-markdown])) {
  background: var(--ccl-card) !important;
  border: 1px solid var(--ccl-border) !important;
  border-radius: 16px !important;
  box-shadow: 0 2px 12px var(--ccl-shadow) !important;
  margin: 6px 12px 8px 4px !important;
  overflow: hidden !important;
}
[data-tree-group]:has(aside :is(.cm-editor, .preview-source-code, [data-preview-markdown])) :is([data-zone-tabstrip], [data-panel-header], [data-zone-body], aside) {
  background: var(--ccl-card) !important;
}
/* The inner editor goes flat: no second card inside the first. */
aside:is(:has(.cm-editor), :has(.preview-source-code), :has([data-preview-markdown])) {
  background: var(--ccl-card) !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  margin: 0 !important;
}
aside:is(:has(.cm-editor), :has(.preview-source-code), :has([data-preview-markdown])) .border-b {
  border-bottom-color: var(--ccl-divider) !important;
}
aside .bg-background,
aside .cm-editor,
aside .cm-editor .cm-gutters,
aside .cm-scroller,
aside .preview-source-code,
aside .preview-source-code pre,
aside [data-preview-markdown] {
  background: var(--ccl-card) !important;
}
aside .cm-editor .cm-gutters {
  border-right: 0 !important;
  color: var(--ccl-muted) !important;
}
aside .cm-editor .cm-content,
aside .preview-source-code {
  font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace !important;
}
aside .cm-editor .cm-content { color: var(--ccl-code) !important; caret-color: var(--ccl-code) !important; }
aside .cm-editor .cm-cursor { border-left-color: var(--ccl-code) !important; }
aside .cm-editor .cm-activeLine,
aside .cm-editor .cm-activeLineGutter {
  background: var(--ccl-subtle) !important;
}
aside .cm-editor .cm-selectionBackground,
aside .cm-editor.cm-focused .cm-selectionBackground {
  background: var(--ccl-selection) !important;
}
/* Left sidebar: selected row + icon colours */
:root, .dark {
  --ui-row-active-background: var(--ccl-row-active) !important;
  --ui-row-open-background: var(--ccl-row-open) !important;
}
[data-tour='sessions-sidebar'] :is(.bg-\\(--ui-row-active-background\\), .bg-\\(--ui-row-open-background\\)) {
  border-radius: 6px !important;
}
[data-tour='sessions-sidebar'] .bg-\\(--ui-row-active-background\\) {
  color: var(--ccl-text) !important;
}
[data-tour='sessions-sidebar'] button:not([data-row-actions] button) svg {
  color: var(--ccl-icon) !important;
}
/* Working-session arc: same corners as the selected row */
.arc-border.arc-row, :root.dark .arc-border.arc-row {
  --arc-radius: 6px !important;
}
[data-tour='sessions-sidebar'] [data-working='true'],
.arc-border.arc-row { border-radius: 6px !important; }
/* Dropdown menus (filter/sort etc.): white rounded popover */
:is([data-slot='dropdown-menu-content'], [data-slot='dropdown-menu-sub-content'], [role='menu'][data-radix-menu-content]) {
  background: var(--ccl-card) !important;
  border: 1px solid var(--ccl-border) !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 4px var(--ccl-shadow-sm), 0 6px 16px var(--ccl-shadow) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  padding: 4px !important;
  min-width: 200px !important;
}
:is([data-slot='dropdown-menu-item'], [data-slot='dropdown-menu-checkbox-item'], [data-slot='dropdown-menu-radio-item'], [data-slot='dropdown-menu-sub-trigger']) {
  border-radius: 8px !important;
  min-height: 28px !important;
  padding-inline: 8px !important;
  font-size: 13px !important;
  color: var(--ccl-text) !important;
}
:is([data-slot='dropdown-menu-item'], [data-slot='dropdown-menu-checkbox-item'], [data-slot='dropdown-menu-radio-item'], [data-slot='dropdown-menu-sub-trigger']):is([data-highlighted], [data-state='open']) {
  background: var(--ccl-hover) !important;
  color: var(--ccl-text) !important;
}
[role='menu'] :is([data-slot='dropdown-menu-item'], [data-slot='dropdown-menu-sub-trigger']) svg { color: var(--ccl-muted) !important; }
[role='menu'] :is([data-slot='dropdown-menu-checkbox-item'], [data-slot='dropdown-menu-radio-item']) [data-state='checked'] svg,
[role='menu'] [data-state='checked'] > span svg { color: var(--ccl-check) !important; }
[data-slot='dropdown-menu-label'] {
  color: var(--ccl-muted) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  padding: 6px 8px 2px !important;
}
[data-slot='dropdown-menu-separator'] {
  background: var(--ccl-divider) !important;
  margin: 4px 6px !important;
  height: 1px !important;
}
/* User message: right-aligned, fit-content, soft grey, no border */
[data-slot='aui_user-message-root'] {
  align-items: flex-end !important;
}
[data-slot='aui_user-message-root'] .composer-human-message {
  width: fit-content !important;
  max-width: min(85%, 640px) !important;
  margin-left: auto !important;
  background: var(--ccl-bubble) !important;
  border: 0 !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  padding: 10px 18px !important;
  color: var(--ccl-text) !important;
}
[data-slot='aui_user-message-root'] .composer-human-message::before,
[data-slot='aui_user-message-root'] .composer-human-message::after {
  display: none !important;
}

/* Composer: style ONLY the inner surface (root wrapper stays untouched,
   otherwise you get two borders). White, one pale border, soft halo. */
[data-slot='composer-root'] {
  --composer-fill: var(--ccl-card) !important;
}
[data-slot='composer-surface'] {
  background: var(--ccl-card) !important;
  border: 1px solid var(--ccl-border) !important;
  border-radius: 16px !important;
  box-shadow: 0 1px 3px var(--ccl-shadow-xs), 0 4px 16px var(--ccl-shadow-xs) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  outline: none !important;
}
[data-slot='composer-surface']:focus-within {
  border-color: var(--ccl-border-strong) !important;
}
[data-slot='composer-surface'] button[type='submit'] {
  background: var(--ccl-send-bg) !important;
  color: var(--ccl-card) !important;
  border-radius: 9999px !important;
}
`

function apply() {
  let el = document.getElementById(STYLE_ID)
  if (!el) {
    el = document.createElement('style')
    el.id = STYLE_ID
    document.head.appendChild(el)
  }
  el.textContent = CSS
  return () => el.remove()
}


// ── Context window + plan limits (context ring + popover) ──
const fmtK = n => n >= 1e6 ? (n / 1e6).toFixed(n % 1e6 ? 1 : 0) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n || 0)

function Bar({ pct, color }) {
  return jsx('div', { style: { height: 6, borderRadius: 3, background: 'var(--ccl-divider)', overflow: 'hidden' },
    children: jsx('div', { style: { width: Math.min(100, Math.max(0, pct)) + '%', height: '100%', background: color || 'var(--ccl-text)' } }) })
}

function Ring({ pct }) {
  const r = 7, c = 2 * Math.PI * r
  return jsxs('svg', { width: 18, height: 18, viewBox: '0 0 18 18', children: [
    jsx('circle', { cx: 9, cy: 9, r, fill: 'none', stroke: 'var(--ccl-border)', strokeWidth: 2.2 }),
    jsx('circle', { cx: 9, cy: 9, r, fill: 'none', stroke: pct > 85 ? '#d81b60' : 'var(--ccl-text)', strokeWidth: 2.2,
      strokeDasharray: c, strokeDashoffset: c * (1 - Math.min(1, pct / 100)), strokeLinecap: 'round', transform: 'rotate(-90 9 9)' })
  ] })
}

// account_lines are pre-rendered text from Duckwork; keep only the useful rows.
function parseLimits(lines) {
  if (!lines || !lines.length) return { rows: [], note: 'No limit data from this provider.' }
  const rows = [], notes = []
  for (const raw of lines.slice(1)) {
    const l = raw.replace(/\*\*/g, '').trim()
    if (/^Provider:/i.test(l)) continue
    if (/^Unavailable:/i.test(l)) { notes.push(l.replace(/^Unavailable:\s*/i, 'Unavailable: ')); continue }
    // Duckwork format: "Label: 97% remaining (3% used) • resets in 35m"
    const m = l.match(/^(.*?):\s*\d+%\s*remaining\s*\((\d+)%\s*used\)(?:\s*•\s*(.*))?$/i)
    if (m) rows.push({ label: m[1], pct: parseFloat(m[2]), reset: m[3] ? m[3].replace(/^resets/i, 'Resets') : '' })
    else notes.push(l)
  }
  return { rows, note: notes.join(' ') }
}

function UsageMeter() {
  const usage = useValue(host.state.focusedUsage)
  const sid = useValue(host.state.focusedSessionId)
  const [limits, setLimits] = useState(null)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open || !sid) return
    let live = true
    host.request('session.usage', { session_id: sid })
      .then(r => { if (live) setLimits(parseLimits(r?.account_lines)) })
      .catch(() => { if (live) setLimits({ rows: [], note: 'Could not fetch limits.' }) })
    return () => { live = false }
  }, [open, sid])
  if (!usage || !usage.context_max) return null
  const used = usage.context_used || 0, max = usage.context_max
  const pct = usage.context_percent ?? (used / max) * 100
  const muted = { color: 'var(--ccl-muted)', fontSize: 12 }
  return jsxs(Popover, { open, onOpenChange: setOpen, children: [
    jsx(PopoverTrigger, { asChild: true, children: jsx('button', {
      type: 'button', title: 'Context window', 'data-slot': 'ccl-usage-trigger',
      style: { display: 'grid', placeItems: 'center', width: 26, height: 26, borderRadius: 8, background: 'transparent', border: 0, cursor: 'pointer' },
      children: jsx(Ring, { pct }) }) }),
    jsx(PopoverContent, { side: 'top', align: 'end', 'data-slot': 'ccl-usage-popover',
      style: { width: 340, padding: 14, background: 'var(--ccl-card)', border: '1px solid var(--ccl-border)', borderRadius: 12,
        boxShadow: '0 2px 4px var(--ccl-shadow-sm), 0 6px 16px var(--ccl-shadow)', color: 'var(--ccl-text)', fontSize: 13 },
      children: jsxs('div', { style: { display: 'grid', gap: 10 }, children: [
        jsxs('div', { style: { display: 'flex', justifyContent: 'space-between' }, children: [
          jsx('span', { style: muted, children: 'Context window' }),
          jsx('span', { style: { fontVariantNumeric: 'tabular-nums' },
            children: `${usage.context_estimated ? '~' : ''}${fmtK(used)} / ${fmtK(max)} (${Math.round(pct)}%)` })] }),
        jsx(Bar, { pct }),
        jsx('div', { style: { height: 1, background: 'var(--ccl-divider)', margin: '2px 0' } }),
        jsx('span', { style: muted, children: 'Your usage limits' }),
        !limits ? jsx('span', { style: muted, children: 'Loading…' }) :
          jsxs('div', { style: { display: 'grid', gap: 10 }, children: [
            ...limits.rows.map(r => jsxs('div', { style: { display: 'grid', gap: 5 }, children: [
              jsxs('div', { style: { display: 'flex', gap: 8, alignItems: 'baseline' }, children: [
                jsx('span', { style: { flex: 1 }, children: r.label }),
                r.reset ? jsx('span', { style: muted, children: r.reset }) : null,
                jsx('span', { style: { fontVariantNumeric: 'tabular-nums', minWidth: 32, textAlign: 'right' }, children: Math.round(r.pct) + '%' })] }),
              jsx(Bar, { pct: r.pct, color: r.pct > 85 ? '#d81b60' : 'var(--ccl-text)' })] }, r.label)),
            limits.note ? jsx('span', { style: muted, children: limits.note }) : null] })
      ] }) })
  ] })
}

// ── Accent setting (per light/dark, stored per user) ──
const DEFAULTS = { accentEnabled: false, accentLight: '#2d2d2b', accentDark: '#e7e7e7' }
const HEX = /^#[0-9a-f]{6}$/i
let store = null
const $prefs = atom(DEFAULTS)
function setPref(key, value) {
  const next = { ...$prefs.get(), [key]: value }
  $prefs.set(next)
  store && store.set('prefs', next)
}

function AccentSync() {
  const prefs = useValue($prefs)
  const { resolvedMode } = useTheme()
  useEffect(() => {
    const hex = resolvedMode === 'dark' ? prefs.accentDark : prefs.accentLight
    setAccentOverride(prefs.accentEnabled && HEX.test(hex) ? hex : null)
  }, [prefs, resolvedMode])
  return null
}

function ColorField({ label, prefKey }) {
  const prefs = useValue($prefs)
  const value = prefs[prefKey]
  return jsxs('label', { style: { display: 'flex', alignItems: 'center', gap: 10 }, children: [
    jsx('span', { style: { width: 120, fontSize: 13 }, children: label }),
    jsx('input', { type: 'color', value: HEX.test(value) ? value : '#000000', disabled: !prefs.accentEnabled,
      onChange: e => setPref(prefKey, e.target.value),
      style: { width: 32, height: 28, padding: 0, border: '1px solid var(--ccl-border)', borderRadius: 6, background: 'none' } }),
    jsx(Input, { value, disabled: !prefs.accentEnabled, style: { width: 110 },
      onChange: e => setPref(prefKey, e.target.value.trim()) })
  ] })
}

function SettingsPage() {
  const prefs = useValue($prefs)
  return jsxs('div', { style: { display: 'grid', gap: 16, maxWidth: 480 }, children: [
    jsxs('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' }, children: [
      jsxs('div', { children: [
        jsx('div', { style: { fontSize: 14, fontWeight: 500 }, children: 'Custom accent colour' }),
        jsx('div', { style: { fontSize: 12, color: 'var(--ccl-muted)' }, children: 'Off: use the active skin\'s accent.' })] }),
      jsx(Switch, { checked: prefs.accentEnabled, onCheckedChange: v => setPref('accentEnabled', v) })] }),
    jsx(ColorField, { label: 'Light mode', prefKey: 'accentLight' }),
    jsx(ColorField, { label: 'Dark mode', prefKey: 'accentDark' }),
    jsx('button', { type: 'button', onClick: () => { $prefs.set(DEFAULTS); store && store.set('prefs', DEFAULTS) },
      style: { justifySelf: 'start', fontSize: 12, color: 'var(--ccl-muted)', background: 'none', border: 0, cursor: 'pointer', textDecoration: 'underline' },
      children: 'Reset to defaults' })
  ] })
}

export default {
  id: 'claude-code-theme',
  name: 'Claude Code Theme',
  register(ctx) {
    store = ctx.storage
    $prefs.set({ ...DEFAULTS, ...store.get('prefs', {}) })
    ctx.onDispose(apply())
    ctx.register({ id: 'usage-meter', area: COMPOSER_AREAS.actions, order: 100, render: () => jsx(UsageMeter, {}) })
    ctx.register({ id: 'accent-sync', area: STATUSBAR_AREAS.right, order: 999, render: () => jsx(AccentSync, {}) })
    ctx.onDispose(() => setAccentOverride(null))
    ctx.registerSettingsPage({ id: 'appearance', title: 'Claude Code Theme', icon: 'paintcan', render: () => jsx(SettingsPage, {}) })
  }
}
