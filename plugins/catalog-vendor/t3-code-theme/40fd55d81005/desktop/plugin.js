import { CHAT_EMPTY_AREA, THEMES_AREA, requestTheme } from '@duckwork/plugin-sdk'
import { useEffect } from 'react'
import { jsx } from 'react/jsx-runtime'
import * as sdk from '@duckwork/plugin-sdk'

// This plugin extends Duckwork Desktop only through the plugin SDK: a theme with
// its stylesheet, a model pill label, session row decorations and the empty
// chat headline. It never queries, observes or changes the app's document.

// Unofficial port of T3 Code's standard dark theme (not its optional "T3 Chat" theme).
// pingdotgg/t3code@da6a85b1365993d0ff2a79698cd82498de247d8a
// themePalettes.ts / index.css; Copyright (c) 2026 T3 Tools Inc., MIT.
// Full notice in LICENSE-T3-Code; geometry and limits in README.md.
const colors = {
  background: '#0a0a0a', foreground: '#f5f5f5',
  card: '#111111', cardForeground: '#f5f5f5',
  muted: '#111111', mutedForeground: '#818181',
  popover: '#111111', popoverForeground: '#f5f5f5',
  primary: '#346bf1', primaryForeground: '#ffffff',
  secondary: '#111111', secondaryForeground: '#f5f5f5',
  accent: '#141414', accentForeground: '#f5f5f5',
  border: '#191919', input: '#1e1e1e', ring: '#346bf1',
  midground: '#818181', midgroundForeground: '#ffffff', composerRing: '#ffffff',
  destructive: '#fb414a', destructiveForeground: '#ff6467',
  sidebarBackground: '#000000', sidebarBorder: '#141414',
  userBubble: '#141414', userBubbleBorder: '#141414'
}
const typography = {
  fontSans: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", emoji',
  fontMono: 'ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", emoji'
}

// Lucide icons (ISC), as masks so they stay on currentColor.
const lucide = inner => `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`)}")`
const paperclipIcon = lucide('<path d="m16 6-8.414 8.586a2 2 0 0 0 2.829 2.829l8.414-8.586a4 4 0 1 0-5.657-5.657l-8.379 8.551a6 6 0 1 0 8.485 8.485l8.379-8.551"/>')
const serverIcon = lucide('<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>')
const homeIcon = lucide('<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>')

// The theme's stylesheet, handed to Duckwork as the theme's customCSS: Duckwork adds
// it while this theme is painted and removes it with any other theme.
// Keep the native viewport/scroll/sticky positioning and floating composer.
const css = `
/* Explicit tokens: Duckwork synthesizes colors from seeds.
   !important only on the solid primary, which the host writes inline.
   No preferences are written; typography respects the user's chosen font. */
:root[data-duckwork-theme="t3-code-theme"] {
  --composer-width: 48rem;
  --ui-bg-chrome: #0a0a0a; --ui-bg-sidebar: #000000;
  --ui-bg-editor: #111111; --ui-bg-elevated: #111111;
  --ui-chat-surface-background: #0a0a0a;
  --ui-sidebar-surface-background: #000000;
  --ui-editor-surface-background: #0a0a0a;
  --ui-terminal-surface-background: #0a0a0a;
  --ui-widget-surface-background: #111111;
  --ui-text-primary: #f5f5f5;
  --ui-text-secondary: rgb(245 245 245 / 80%);
  --ui-text-tertiary: #818181;
  --ui-accent: #346bf1;
  --ui-bg-primary: rgb(255 255 255 / 8%);
  --ui-bg-secondary: rgb(255 255 255 / 6%);
  --ui-bg-tertiary: rgb(255 255 255 / 3%);
  --ui-bg-quaternary: rgb(255 255 255 / 4%);
  --ui-bg-quinary: rgb(255 255 255 / 3%);
  --ui-row-hover-background: #141414;
  --ui-row-active-background: rgb(245 245 245 / 8%);
  --ui-control-hover-background: #141414;
  --ui-control-active-background: rgb(245 245 245 / 8%);
  --ui-stroke-primary: rgb(255 255 255 / 8%);
  --ui-stroke-secondary: rgb(255 255 255 / 6%);
  --ui-stroke-tertiary: rgb(255 255 255 / 5%);
  --dt-card: #111111; --dt-popover: #111111;
  --dt-primary: #346bf1; --dt-primary-foreground: #ffffff;
  --dt-primary-solid: #346bf1 !important;
  --dt-primary-solid-foreground: #ffffff !important;
  --dt-secondary: #111111; --dt-secondary-foreground: #f5f5f5;
  --dt-accent: #141414; --dt-accent-foreground: #f5f5f5;
  --dt-ring: #346bf1;
  --dt-destructive: #fb414a; --dt-destructive-foreground: #ff6467;
  --dt-input: rgb(255 255 255 / 8%);
  --dt-sidebar-border: rgb(255 255 255 / 8%);
  --ui-chat-bubble-background: #141414;
  --ui-chat-bubble-opaque-background: #141414;
  --ui-inline-code-background: #111111; --ui-inline-code-foreground: #f5f5f5;
  --conversation-text-font-size: .875rem;
  /* Duckwork also multiplies this variable into heights: it must be a length. */
  --conversation-line-height: calc(var(--conversation-text-font-size) * 1.625);
  --paragraph-gap: .65rem;
  /* Palette for this plugin's own rules. */
  --t3-fg: #f5f5f5; --t3-muted-fg: #818181; --t3-sidebar-muted-fg: #a3a3a3;
  --t3-surface: #111111; --t3-primary: #346bf1;
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] {
  --ui-text-primary: #f1f3f7; --ui-text-secondary: #a3a3a3;
  --ui-text-tertiary: #a3a3a3;
  --ui-row-hover-background: #131313;
  --ui-row-active-background: #1a1b1b;
  --ui-row-open-background: #111111;
  --ui-control-hover-background: #191a1d;
  --ui-stroke-secondary: rgb(255 255 255 / 8%);
  --dt-foreground: #f1f3f7; --dt-muted-foreground: #a3a3a3;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_thread-content"] {
  /* No side padding, so the bubble edge matches the composer. */
  width: 100%; max-width: var(--composer-width); margin-inline: auto; padding-inline: 0;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-bubble-actions"] {
  width: fit-content; max-width: 80%; margin-inline-start: auto;
}
:root[data-duckwork-theme="t3-code-theme"] .composer-human-message {
  --human-msg-line-height: 1.625;
  --dt-line-height: 1.625;
  border-radius: 18px; padding: 12px; border: 0;
  font-size: var(--conversation-text-font-size); line-height: 1.625; color: var(--t3-fg);
  box-shadow: none; backdrop-filter: none;
}
/* T3's user row: restore/stop sit in a hover row under the bubble, not inside it.
   The row always takes its space, so hovering never shifts the thread. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-bubble-actions"] .composer-human-message ~ div {
  position: static; justify-content: flex-end; height: 24px; margin-top: 4px; padding-inline-end: 4px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-bubble-actions"] .composer-human-message ~ div > button {
  width: 26px; height: 24px; border-radius: 8px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-bubble-actions"] .composer-human-message ~ div .codicon {
  font-size: 12px !important;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-root"] {
  border-radius: 22px; margin-bottom: 6px;
  --composer-fill: color-mix(in srgb, var(--dt-card) 80%, transparent);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-surface"] {
  /* The host paints this border with !important: override its local token. */
  --ui-stroke-secondary: rgb(255 255 255 / 5%);
  border-radius: 22px; border-color: rgb(255 255 255 / 5%);
  box-shadow: inset 0 1px rgb(255 255 255 / 3%);
}
/* Reflow native controls only: no cloned inputs, listeners or model state.
   display:contents keeps React ownership, refs, menus and keyboard handlers. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] {
  padding: 14px 16px 12px;
  --composer-control-size: 28px;
  --composer-control-primary-size: 32px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] > .grid {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px var(--t3-control-gap);
  --t3-control-gap: 6px; --t3-separator-space: 9px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:input"] {
  order: 0; flex: 1 0 100%; min-width: 0;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-rich-input"] {
  /* 70px is T3's min-h-17.5. Zero side padding keeps one 16px left edge for
     text, attachments and the model icon; Duckwork adds pl-3 in the "stacked"
     (multiline) layout, which made the text jump 12px. */
  min-height: 70px; padding-top: 2px; padding-left: 0 !important; padding-right: 0;
  line-height: 1.625; font-size: var(--conversation-text-font-size);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:controls"],
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:controls"] > div:last-child {
  display: contents;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:controls"] > *,
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:controls"] > div:last-child > * {
  order: 4;
}
/* Duckwork tags only the primary chat's model pill (data-tour). In a tile the
   pill is the button right before the reasoning pill, or the first menu button
   of the controls when the model has no reasoning levels. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"])) {
  order: 1 !important; max-width: min(260px, 50%); min-width: 0;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [data-testid="reasoning-pill"] {
  order: 2 !important;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:menu"] {
  order: 3; margin-inline-start: auto; align-self: center;
  translate: none; transform: none;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] :is(button[type="submit"], button[data-variant="default"][data-size="icon"]) {
  /* T3's round message action: send, or voice start while the input is empty. */
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--dt-primary); color: var(--dt-primary-foreground);
  box-shadow: inset 0 1px rgb(255 255 255 / 16%); transition: opacity .15s, transform .15s;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] :is(button[type="submit"], button[data-variant="default"][data-size="icon"]):not(:disabled):hover { transform: scale(1.05); }
/* T3's disabled:opacity-30 on send. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] button[type="submit"]:disabled { opacity: .3; box-shadow: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_assistant-message-content"] {
  /* Inset like the composer text. */
  --dt-line-height: 1.625;
  font-size: var(--conversation-text-font-size); line-height: 1.625;
  color: rgb(245 245 245 / 80%); padding-inline-start: 20px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_assistant-message-content"] :is(.aui-md, .aui-md p, .aui-md li) {
  color: inherit;
}
/* Slots verified in Duckwork: the portal hangs off body, not the composer.
   Radix width, positioning, z-index and behavior are preserved. */
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="dropdown-menu-content"], [data-slot="dropdown-menu-sub-content"], [data-slot="popover-content"]) {
  border-radius: 10px; padding: 4px;
  border: 1px solid rgb(245 245 245 / 10%);
  background: color-mix(in srgb, var(--dt-popover) 18%, color-mix(in srgb, var(--dt-popover) 80%, transparent));
  backdrop-filter: blur(16px) saturate(1.08);
  -webkit-backdrop-filter: blur(16px) saturate(1.08);
  box-shadow: 0 18px 44px -18px rgb(0 0 0 / 80%);
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="dropdown-menu-item"], [data-slot="dropdown-menu-sub-trigger"]) {
  border-radius: 8px; padding: 8px;
  font-size: 12px; font-weight: 500; line-height: 1.375;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dropdown-menu-radio-item"] {
  border-radius: 6px; padding: 4px 8px; min-height: 28px;
  font-size: 14px; line-height: 20px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dropdown-menu-label"] {
  padding: 6px 8px 4px; font-size: 12px; font-weight: 500;
  text-transform: none; letter-spacing: normal; color: var(--ui-text-tertiary);
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="dropdown-menu-radio-item"], [data-slot="dropdown-menu-checkbox-item"])[data-state="checked"] {
  background: rgb(245 245 245 / 8%); color: var(--t3-fg);
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="dropdown-menu-item"], [data-slot="dropdown-menu-sub-trigger"], [data-slot="dropdown-menu-radio-item"], [data-slot="dropdown-menu-checkbox-item"]):not([data-disabled]):not([data-variant="destructive"])[data-highlighted] {
  background: color-mix(in srgb, var(--dt-popover) 90%, var(--t3-fg)); color: var(--t3-fg);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-surface"] > [aria-hidden="true"] {
  backdrop-filter: blur(16px) saturate(1.08);
  -webkit-backdrop-filter: blur(16px) saturate(1.08);
}
/* ── Polish v2 (measured against the real DOM) ─────────────────────────── */
/* Attachments are a flow sibling of the user root (no slot of their own).
   Right-align them with the bubble and drop the -mt-3 that tucks them under it. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-message-root"] + div:has(> [data-slot="aui_directive-text"]) {
  justify-content: flex-end; margin-top: 2px; margin-bottom: 10px;
  max-width: 80%; margin-inline-start: auto;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_user-message-root"] + div:has(> [data-slot="aui_directive-text"]) [data-slot="aui_embedded-images"] {
  justify-content: flex-end; margin-top: 0;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_directive-image"] img { border-radius: 12px; }
/* Duckwork draws a 48px placeholder and loads the image later at its own size,
   which grows or rewraps the row and makes the transcript jump under the
   composer when a chat with screenshots opens. Fixed tiles keep every row stable. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="aui_embedded-images"] > span[aria-hidden],
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="aui_directive-image"], [data-slot="aui_embedded-image"]) img {
  width: 300px; height: 192px; max-width: 100%;
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-slot="aui_directive-image"], [data-slot="aui_embedded-image"]) img { object-fit: cover; }
/* Chat-area titlebar uses the canvas (#0a0a0a), not the sidebar black. Duckwork
   paints the tab strip inside it too, which would leave a black band that stops
   short of the titlebar controls. */
:root[data-duckwork-theme="t3-code-theme"] [data-tree-group]:not(:has([data-tour="sessions-sidebar"])) [data-panel-header],
:root[data-duckwork-theme="t3-code-theme"] [data-tree-group]:not(:has([data-tour="sessions-sidebar"])) [data-panel-header] [data-zone-tabstrip] {
  background: var(--ui-editor-surface-background);
}
/* Attachment chips carry their own px-1. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-attachments"] { padding-inline: 0; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"])) { margin-inline-start: -8px; }
/* Empty session (tiles, and any stored session with no messages yet): Duckwork
   shows no intro there, so the "chat.empty" contribution supplies the headline,
   with the composer in the middle of the pane as in T3's new thread. It stands
   down when another plugin (e.g. a bot) owns that empty state. */
:root[data-duckwork-theme="t3-code-theme"] [data-t3-empty-hero]:not(:only-child) { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-t3-empty-hero] {
  margin: 0 auto; max-width: 64rem; padding-bottom: calc(var(--composer-measured-height) + 132px);
  font-size: 30px; line-height: 36px; font-weight: 400; letter-spacing: -0.025em; color: var(--t3-fg); text-wrap: balance;
}
:root[data-duckwork-theme="t3-code-theme"] [data-chat-surface]:not([data-hud-shell] *) div:has(> [data-t3-empty-hero]:only-child) { padding-top: 0; }
:root[data-duckwork-theme="t3-code-theme"] [data-chat-surface]:not([data-composer-target="main"]):has([data-t3-empty-hero]:only-child):not([data-hud-shell] *) [data-slot="composer-dock"]:not([data-popped-out]),
:root[data-duckwork-theme="t3-code-theme"] [data-chat-surface][data-composer-target="main"]:has([data-t3-empty-hero]:only-child):not([data-hud-shell] *) [data-slot="composer-dock"]:not([data-popped-out]) {
  top: 50%; bottom: auto; --tw-translate-y: -50%;
}
/* Sidebar chat rows, T3's thread list: the title leads (13px medium, dim
   until hover or selection), metadata recedes, rounded row surface. */
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover:has(.hover-marquee) { border-radius: 8px; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"] .hover-marquee {
  font-weight: 500; color: rgb(245 245 245 / 72%); transition: color .15s;
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover:is(:hover, :focus-within, [class~="bg-(--ui-row-active-background)"], [data-working="true"]) [data-slot="row-button"] .hover-marquee { color: #f5f5f5; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"] .hover-marquee + span {
  margin-top: 3px; font-size: 11px; color: rgb(129 129 129 / 85%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover .session-row-tail { font-size: 11px; color: rgb(129 129 129 / 85%); }
/* Card rows (Duckwork' card style, row-button is flex-col), T3's thread card:
   badge + project + age, title, then this plugin's footer over the space the
   hidden native footer leaves. No running arc, no idle dot. */
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover > .arc-row { display: none; }
/* Duckwork' min-h replaces min-height: auto, so in an overflowing list the flex
   column shrinks each card below its content and clips it. */
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover:has(> [data-slot="row-button"][class~="flex-col"]) { flex-shrink: 0; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] {
  --card-gap: 4px; padding-block: 8px 28px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] > span:last-child { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] > div:first-child { min-height: 20px; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] > div:first-child > span:not([data-reorder-handle]):has(> span > [class~="size-1"][aria-hidden="true"]) { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] > div:first-child > [class~="flex-1"] {
  font-size: 12px; line-height: 16px; font-weight: 500; color: var(--t3-sidebar-muted-fg);
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] .hover-marquee {
  font-size: 14px; line-height: 20px; color: rgb(245 245 245 / 90%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover:is(:hover, :focus-within, [class~="bg-(--ui-row-active-background)"], [data-working="true"]) [data-slot="row-button"][class~="flex-col"] .hover-marquee { color: #f5f5f5; }
:root[data-duckwork-theme="t3-code-theme"] [data-tour="sessions-sidebar"] .row-hover [data-slot="row-button"][class~="flex-col"] .session-row-tail { font-size: 12px; color: var(--t3-sidebar-muted-fg); }
/* Confirm dialogs (a body with header + footer): T3's AlertDialog. dialog-glass popup
   with a 2xl radius, 24px header, 20px title, and the footer as a muted bar with
   an outline Cancel and a primary Confirm. Other dialogs keep Duckwork' layout. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-overlay"]:has(~ [data-slot="dialog-content"] > div > [data-slot="dialog-footer"]) {
  background: color-mix(in srgb, #0a0a0a 64%, transparent); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"]:has(> div > [data-slot="dialog-footer"]) {
  border-radius: 18px; border: 1px solid rgb(255 255 255 / 8%);
  background: color-mix(in srgb, #0a0a0a 80%, transparent);
  backdrop-filter: blur(16px) saturate(1.08); -webkit-backdrop-filter: blur(16px) saturate(1.08);
  box-shadow: inset 0 1px rgb(255 255 255 / 4%), 0 24px 72px -20px rgb(0 0 0 / 90%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"] > div:has(> [data-slot="dialog-footer"]) { gap: 16px; padding: 24px 24px 0; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"]:has(> div > [data-slot="dialog-footer"]) [data-slot="dialog-close-button"] { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"]:has(> div > [data-slot="dialog-footer"]) [data-slot="dialog-header"] { gap: 8px; text-align: left; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"]:has(> div > [data-slot="dialog-footer"]) [data-slot="dialog-title"] {
  font-size: 20px; line-height: 1; font-weight: 600; letter-spacing: normal; color: var(--t3-fg); overflow-wrap: anywhere;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"]:has(> div > [data-slot="dialog-footer"]) [data-slot="dialog-description"] {
  font-size: 14px; line-height: 20px; color: var(--t3-muted-fg);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-content"] > div > [data-slot="dialog-footer"] {
  margin: 8px -24px 0; padding: 16px 24px; gap: 8px;
  border-top: 1px solid #191919; border-radius: 0 0 17px 17px; background: rgb(17 17 17 / 72%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button {
  height: 32px; padding: 0 11px; gap: 8px; border: 1px solid transparent; border-radius: 8px;
  font-size: 14px; font-weight: 500; line-height: 20px; box-shadow: none; transition: box-shadow .15s, scale .15s;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button:active:not(:disabled) { scale: .97; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="ghost"] {
  border-color: #1e1e1e; background: rgb(255 255 255 / 2.5%); color: var(--t3-fg); box-shadow: inset 0 1px rgb(255 255 255 / 6%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="ghost"]:hover { background: rgb(255 255 255 / 5%); }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="secondary"] { background: var(--t3-surface); color: var(--t3-fg); }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button:is([data-variant="default"], [data-variant="destructive"]) {
  color: #ffffff; box-shadow: inset 0 1px rgb(255 255 255 / 16%), 0 1px 2px rgb(0 0 0 / 5%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="default"] { border-color: var(--t3-primary); background: var(--t3-primary); }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="default"]:hover { background: color-mix(in srgb, var(--t3-primary) 90%, transparent); }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="destructive"] { border-color: #fb414a; background: #fb414a; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="dialog-footer"] > button[data-variant="destructive"]:hover { background: color-mix(in srgb, #fb414a 90%, transparent); }
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  :root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-root"] { --composer-fill: var(--dt-card); }
  :root[data-duckwork-theme="t3-code-theme"] :is([data-slot="dropdown-menu-content"], [data-slot="dropdown-menu-sub-content"], [data-slot="popover-content"]) { background: var(--dt-popover); }
}
`

const composerCss = `
/* Composer controls: T3 ComposerControl "sm" (h-7, px-2.5, gap-1.5, text-sm
   font-medium, secondary label color measured in the T3 app). */
:root[data-duckwork-theme="t3-code-theme"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"]), [data-testid="reasoning-pill"]) {
  height: 28px; padding-inline: 10px; gap: 6px; border-radius: 8px;
  font-size: 14px; font-weight: 500; color: #767676;
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"]), [data-testid="reasoning-pill"]):is(:hover, [data-state="open"]) {
  color: var(--t3-fg); background: rgb(255 255 255 / 6%);
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"]), [data-testid="reasoning-pill"]) > svg {
  width: 14px; height: 14px; opacity: .6;
}
:root[data-duckwork-theme="t3-code-theme"] [data-testid="reasoning-pill"] { position: relative; margin-inline-start: var(--t3-separator-space, 9px); }
/* The separator sits in the middle of the row gap plus that margin, so the
   space to the model and to the effort is equal. */
:root[data-duckwork-theme="t3-code-theme"] [data-testid="reasoning-pill"]::before {
  content: ''; position: absolute; width: 1px; height: 16px; top: calc(50% - 8px);
  inset-inline-start: calc((var(--t3-control-gap, 6px) + var(--t3-separator-space, 9px) + 1px) / -2);
  background: rgb(255 255 255 / 8%);
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"]), [data-testid="reasoning-pill"]) > span:has(.glyph-spinner) {
  width: 56px; height: 10px; border-radius: 9999px; background: rgb(255 255 255 / 8%);
  animation: t3-skeleton 1.2s ease-in-out infinite;
}
:root[data-duckwork-theme="t3-code-theme"] :is([data-tour="model-pill"], button:has(+ [data-testid="reasoning-pill"]), [class*="grid-area:controls"] > div > button[aria-haspopup="menu"]:first-child:not([data-testid="reasoning-pill"]), [data-testid="reasoning-pill"]) > span:has(.glyph-spinner) > * { visibility: hidden; }
@keyframes t3-skeleton { 50% { opacity: .45; } }
/* The native "+" context menu reads as T3's paperclip on the right. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:menu"] button { color: rgb(245 245 245 / 60%); width: 32px; height: 32px; border-radius: 8px; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:menu"] button:hover { color: var(--t3-fg); background: rgb(255 255 255 / 6%); }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:menu"] .codicon-add::before { content: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [class*="grid-area:menu"] .codicon-add {
  width: 16px; height: 16px; background: currentColor; mask: ${paperclipIcon} center / contain no-repeat;
}
/* T3's resting placeholder, minus "$use skills" (Duckwork has no $ trigger).
   Duckwork picks a random starter or follow-up line; its connection states
   ("Starting Duckwork...", "Reconnecting to Duckwork...") stay visible. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-fade"] [data-slot="composer-rich-input"][data-placeholder]:not([data-placeholder^="Starting"], [data-placeholder^="Reconnecting"]):is(:empty, [data-empty])::before {
  content: "Ask anything, @tag files/folders, or / for commands"; color: rgb(129 129 129 / 80%);
}
/* Voice fan: T3 has no read-aloud or wake-word toggles, so their discs are
   hidden while off. Once on they reappear so they can be turned off again;
   a lone visible disc takes the first slot (hub size + the fan's 4px gap). */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="fan-menu"] > button:is([aria-label="Read replies aloud"], [aria-label^="Wake word"][aria-pressed="false"]) { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="fan-menu"][data-state="open"][data-direction="vertical"]:has(> button[aria-label="Read replies aloud"]) > button[aria-label^="Wake word"] {
  translate: 0 calc(-100% - 4px) !important;
}
/* Nothing left to fan out: drop the "more" caret on the mic. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="fan-menu-anchor"] > .codicon-chevron-up { display: none; }
/* The native pin dot after the model name (T3 has none; the title keeps the pin). */
:root[data-duckwork-theme="t3-code-theme"] [data-testid="model-pinned-dot"] { display: none; }
/* Status tray: T3 draws branch/checkout as a strip BELOW the composer, inset
   22px. The surface loses its frame, the input area (composer-fade) takes it,
   and the status drawer moves to the second grid row. Kept in flow so the
   host's measured composer height stays true. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-dock"]:not([data-popped-out]) [data-slot="status-drawer-toggle"] { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-dock"]:not([data-popped-out]) [data-slot="composer-surface"] {
  grid-template-rows: auto auto; overflow: visible; border-width: 0; box-shadow: none;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-dock"]:not([data-popped-out]) [data-slot="composer-surface"] > [aria-hidden="true"] { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-dock"]:not([data-popped-out]) [data-slot="composer-fade"] {
  grid-row: 1; border-radius: 22px; background: var(--composer-fill);
  border: 1px solid rgb(255 255 255 / 5%); box-shadow: inset 0 1px rgb(255 255 255 / 3%);
  backdrop-filter: blur(16px) saturate(1.08); -webkit-backdrop-filter: blur(16px) saturate(1.08);
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-dock"]:not([data-popped-out]) [data-slot="composer-surface"] > .status-drawer {
  /* min-height: the tray's rows remount when a chat opens; reserving its
     height keeps the composer from hopping 29px for a frame. */
  grid-row: 2; min-height: 29px; margin: 0 22px; border: 1px solid #252525; border-top: 0;
  border-radius: 0 0 14px 14px; background: #151515; color: #767676;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-surface"] > .status-drawer .coding-status-bar {
  min-height: 28px; padding: 4px 12px; border: 0; border-radius: 0 0 14px 14px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-surface"] > .status-drawer .coding-status-bar :is(span, .codicon) { font-size: 12px; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="composer-surface"] > .status-drawer .coding-status-bar :is(span, .codicon) { color: #767676; }
`

const rowCardCss = `
/* Sidebar row contributions (the "sessionRow" areas): project badge and footer. */
:root[data-duckwork-theme="t3-code-theme"] [data-slot="row-button"]:not([class~="flex-col"]) [data-t3-row-badge] { display: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-badge] {
  display: grid; place-items: center; flex: none; width: 16px; height: 16px; border-radius: 4px;
  font-size: 8px; font-weight: 700; line-height: 1; letter-spacing: .02em; color: #fb923c; background: rgb(234 88 12 / 22%);
}
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-badge="home"] { background: rgb(129 129 129 / 18%); }
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-badge="home"]::before {
  content: ""; width: 10px; height: 10px; background: var(--t3-sidebar-muted-fg); mask: ${homeIcon} center / contain no-repeat;
}
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-foot] { display: flex; flex: none; align-items: center; gap: 4px; pointer-events: none; }
:root[data-duckwork-theme="t3-code-theme"] [data-slot="row-button"]:not([class~="flex-col"]) [data-t3-row-foot] > :not([data-t3-row-machine]) { display: none; }
:root[data-duckwork-theme="t3-code-theme"] .row-hover:has(> [data-slot="row-button"][class~="flex-col"]) [data-t3-row-foot] {
  position: absolute; left: 8px; right: 8px; bottom: 8px; height: 16px;
}
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-branch] {
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 12px; line-height: 16px; color: rgb(129 129 129 / 60%);
}
:root[data-duckwork-theme="t3-code-theme"] .row-hover:has(> [data-slot="row-button"][class~="flex-col"]) [data-t3-row-branch]:empty { visibility: hidden; }
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-machine] {
  flex: none; width: 12px; height: 12px;
  background: rgb(163 163 163 / 70%); mask: ${serverIcon} center / contain no-repeat;
}
:root[data-duckwork-theme="t3-code-theme"] .row-hover:has(> [data-slot="row-button"][class~="flex-col"]) [data-t3-row-machine] { width: 14px; height: 14px; }
:root[data-duckwork-theme="t3-code-theme"] [data-t3-row-provider] {
  flex: none; width: 14px; height: 14px; opacity: .6; background: center / contain no-repeat;
}
`

// Display adapter from Duckwork model-status-label.ts (MIT, Fordex).
// Matching is deliberately collision-intolerant: no row is guessed from its
// position, a fuzzy name, React internals, or a model from another provider.
function nativeModelParts(model) {
  let base = model.trim().split('/').pop(), variant = '', quant = ''
  // Variant and GGUF quant suffixes can come in either order.
  for (let progress = true; progress;) {
    progress = false
    if (!variant) {
      for (const [suffix, label] of [['fast','Fast'],['flash','Flash'],['thinking','Thinking'],['preview','Preview'],['latest','Latest']]) {
        if (base.toLowerCase().endsWith('-' + suffix)) { base = base.slice(0, -suffix.length - 1); variant = label; progress = true; break }
      }
    }
    const q = !quant && base.match(/-(?:UD-)?(Q\d(?:_[A-Z0-9]+)*|IQ\d(?:_[A-Z0-9]+)*|F16|BF16)$/i)
    if (q) {
      quant = q[1].split('_')[0].toUpperCase()
      base = base.slice(0, -q[0].length).replace(/-(?:Instruct|Chat)(?:-\d{4})?$/i, '')
      progress = true
    }
  }
  const tags = [variant, quant].filter(Boolean)
  const context = base.match(/\[(\d+[mk])\]$/i)
  if (context) { tags.push(context[1].toUpperCase()); base = base.slice(0, -context[0].length) }
  base = base.replace(/-\d{8}$/, '')
  const title = s => s.replace(/\b\w/g, c => c.toUpperCase()).trim()
  const vendor = s => VENDOR_CASING.reduce((text, [pattern, cased]) => text.replace(pattern, cased),
    s.replace(/\b(a?)(\d+(?:\.\d+)?)b\b/gi, (m, prefix, size) => `${prefix.toUpperCase()}${size}B`))
  const name = /^claude-/i.test(base) ? vendor(title(base.replace(/^claude-/i,'').replace(/(\d)-(?=\d)/g,'$1.').replace(/-/g,' ')))
    : /^gpt-/i.test(base) ? base.replace(/^gpt-/i,'GPT-')
    : /^gemini-/i.test(base) ? vendor(title(base.replace(/^gemini-/i,'Gemini ').replace(/-/g,' ')))
    : vendor(title(base.replace(/-/g,' ')))
  return { name: name || model.trim() || 'No model', tag: tags.join(' ') }
}
const VENDOR_CASING = [['Deepseek','DeepSeek'],['Glm','GLM'],['Minimax','MiniMax'],['Openai','OpenAI'],['Ernie','ERNIE'],['Mimo','MiMo'],['Bge','BGE'],['Vl','VL'],['It','IT'],['Fp8','FP8'],['Ai','AI']]
  .map(([word, cased]) => [new RegExp(`\\b${word}\\b`, 'g'), cased])

// These neutral monograms are original fallback icons, not vendor logos.
// The OpenAI/Claude SVG paths below are attributed separately in README.
const providerIconPaths = {"openai": {"viewBox": "0 0 256 260", "path": "M239.184 106.203a64.716 64.716 0 0 0-5.576-53.103C219.452 28.459 191 15.784 163.213 21.74A65.586 65.586 0 0 0 52.096 45.22a64.716 64.716 0 0 0-43.23 31.36c-14.31 24.602-11.061 55.634 8.033 76.74a64.665 64.665 0 0 0 5.525 53.102c14.174 24.65 42.644 37.324 70.446 31.36a64.72 64.72 0 0 0 48.754 21.744c28.481.025 53.714-18.361 62.414-45.481a64.767 64.767 0 0 0 43.229-31.36c14.137-24.558 10.875-55.423-8.083-76.483Zm-97.56 136.338a48.397 48.397 0 0 1-31.105-11.255l1.535-.87 51.67-29.825a8.595 8.595 0 0 0 4.247-7.367v-72.85l21.845 12.636c.218.111.37.32.409.563v60.367c-.056 26.818-21.783 48.545-48.601 48.601Zm-104.466-44.61a48.345 48.345 0 0 1-5.781-32.589l1.534.921 51.722 29.826a8.339 8.339 0 0 0 8.441 0l63.181-36.425v25.221a.87.87 0 0 1-.358.665l-52.335 30.184c-23.257 13.398-52.97 5.431-66.404-17.803ZM23.549 85.38a48.499 48.499 0 0 1 25.58-21.333v61.39a8.288 8.288 0 0 0 4.195 7.316l62.874 36.272-21.845 12.636a.819.819 0 0 1-.767 0L41.353 151.53c-23.211-13.454-31.171-43.144-17.804-66.405v.256Zm179.466 41.695-63.08-36.63L161.73 77.86a.819.819 0 0 1 .768 0l52.233 30.184a48.6 48.6 0 0 1-7.316 87.635v-61.391a8.544 8.544 0 0 0-4.4-7.213Zm21.742-32.69-1.535-.922-51.619-30.081a8.39 8.39 0 0 0-8.492 0L99.98 99.808V74.587a.716.716 0 0 1 .307-.665l52.233-30.133a48.652 48.652 0 0 1 72.236 50.391v.205ZM88.061 139.097l-21.845-12.585a.87.87 0 0 1-.41-.614V65.685a48.652 48.652 0 0 1 79.757-37.346l-1.535.87-51.67 29.825a8.595 8.595 0 0 0-4.246 7.367l-.051 72.697Zm11.868-25.58 28.138-16.217 28.188 16.218v32.434l-28.086 16.218-28.188-16.218-.052-32.434Z"}, "anthropic": {"viewBox": "0 0 256 257", "path": "m50.228 170.321 50.357-28.257.843-2.463-.843-1.361h-2.462l-8.426-.518-28.775-.778-24.952-1.037-24.175-1.296-6.092-1.297L0 125.796l.583-3.759 5.12-3.434 7.324.648 16.202 1.101 24.304 1.685 17.629 1.037 26.118 2.722h4.148l.583-1.685-1.426-1.037-1.101-1.037-25.147-17.045-27.22-18.017-14.258-10.37-7.713-5.25-3.888-4.925-1.685-10.758 7-7.713 9.397.649 2.398.648 9.527 7.323 20.35 15.75L94.817 91.9l3.889 3.24 1.555-1.102.195-.777-1.75-2.917-14.453-26.118-15.425-26.572-6.87-11.018-1.814-6.61c-.648-2.723-1.102-4.991-1.102-7.778l7.972-10.823L71.42 0 82.05 1.426l4.472 3.888 6.61 15.101 10.694 23.786 16.591 32.34 4.861 9.592 2.592 8.879.973 2.722h1.685v-1.556l1.36-18.211 2.528-22.36 2.463-28.776.843-8.1 4.018-9.722 7.971-5.25 6.222 2.981 5.12 7.324-.713 4.73-3.046 19.768-5.962 30.98-3.889 20.739h2.268l2.593-2.593 10.499-13.934 17.628-22.036 7.778-8.749 9.073-9.657 5.833-4.601h11.018l8.1 12.055-3.628 12.443-11.342 14.388-9.398 12.184-13.48 18.147-8.426 14.518.778 1.166 2.01-.194 30.46-6.481 16.462-2.982 19.637-3.37 8.88 4.148.971 4.213-3.5 8.62-20.998 5.184-24.628 4.926-36.682 8.685-.454.324.519.648 16.526 1.555 7.065.389h17.304l32.21 2.398 8.426 5.574 5.055 6.805-.843 5.184-12.962 6.611-17.498-4.148-40.83-9.721-14-3.5h-1.944v1.167l11.666 11.406 21.387 19.314 26.767 24.887 1.36 6.157-3.434 4.86-3.63-.518-23.526-17.693-9.073-7.972-20.545-17.304h-1.36v1.814l4.73 6.935 25.017 37.59 1.296 11.536-1.814 3.76-6.481 2.268-7.13-1.297-14.647-20.544-15.1-23.138-12.185-20.739-1.49.843-7.194 77.448-3.37 3.953-7.778 2.981-6.48-4.925-3.436-7.972 3.435-15.749 4.148-20.544 3.37-16.333 3.046-20.285 1.815-6.74-.13-.454-1.49.194-15.295 20.999-23.267 31.433-18.406 19.702-4.407 1.75-7.648-3.954.713-7.064 4.277-6.286 25.47-32.405 15.36-20.092 9.917-11.6-.065-1.686h-.583L44.07 198.125l-12.055 1.555-5.185-4.86.648-7.972 2.463-2.593 20.35-13.999-.064.065Z"}}
// Gemini SVG from T3 Code (MIT); OpenRouter mark from Simple Icons (CC0).
const geminiProviderSvg = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 296 298\" fill=\"none\">\n    <mask\n      id=\"gemini__a\"\n      width=\"296\"\n      height=\"298\"\n      x=\"0\"\n      y=\"0\"\n      maskUnits=\"userSpaceOnUse\"\n      style=\"mask-type:alpha\"\n    >\n      <path\n        fill=\"#3186FF\"\n        d=\"M141.201 4.886c2.282-6.17 11.042-6.071 13.184.148l5.985 17.37a184.004 184.004 0 0 0 111.257 113.049l19.304 6.997c6.143 2.227 6.156 10.91.02 13.155l-19.35 7.082a184.001 184.001 0 0 0-109.495 109.385l-7.573 20.629c-2.241 6.105-10.869 6.121-13.133.025l-7.908-21.296a184 184 0 0 0-109.02-108.658l-19.698-7.239c-6.102-2.243-6.118-10.867-.025-13.132l20.083-7.467A183.998 183.998 0 0 0 133.291 26.28l7.91-21.394Z\"\n      />\n    </mask>\n    <g mask=\"url(#gemini__a)\">\n      <g filter=\"url(#gemini__b)\">\n        <ellipse cx=\"163\" cy=\"149\" fill=\"#3689FF\" rx=\"196\" ry=\"159\" />\n      </g>\n      <g filter=\"url(#gemini__c)\">\n        <ellipse cx=\"33.5\" cy=\"142.5\" fill=\"#F6C013\" rx=\"68.5\" ry=\"72.5\" />\n      </g>\n      <g filter=\"url(#gemini__d)\">\n        <ellipse cx=\"19.5\" cy=\"148.5\" fill=\"#F6C013\" rx=\"68.5\" ry=\"72.5\" />\n      </g>\n      <g filter=\"url(#gemini__e)\">\n        <path fill=\"#FA4340\" d=\"M194 10.5C172 82.5 65.5 134.333 22.5 135L144-66l50 76.5Z\" />\n      </g>\n      <g filter=\"url(#gemini__f)\">\n        <path fill=\"#FA4340\" d=\"M190.5-12.5C168.5 59.5 62 111.333 19 112L140.5-89l50 76.5Z\" />\n      </g>\n      <g filter=\"url(#gemini__g)\">\n        <path fill=\"#14BB69\" d=\"M194.5 279.5C172.5 207.5 66 155.667 23 155l121.5 201 50-76.5Z\" />\n      </g>\n      <g filter=\"url(#gemini__h)\">\n        <path fill=\"#14BB69\" d=\"M196.5 320.5C174.5 248.5 68 196.667 25 196l121.5 201 50-76.5Z\" />\n      </g>\n    </g>\n    <defs>\n      <filter\n        id=\"gemini__b\"\n        width=\"464\"\n        height=\"390\"\n        x=\"-69\"\n        y=\"-46\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"18\" />\n      </filter>\n      <filter\n        id=\"gemini__c\"\n        width=\"265\"\n        height=\"273\"\n        x=\"-99\"\n        y=\"6\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n      <filter\n        id=\"gemini__d\"\n        width=\"265\"\n        height=\"273\"\n        x=\"-113\"\n        y=\"12\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n      <filter\n        id=\"gemini__e\"\n        width=\"299.5\"\n        height=\"329\"\n        x=\"-41.5\"\n        y=\"-130\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n      <filter\n        id=\"gemini__f\"\n        width=\"299.5\"\n        height=\"329\"\n        x=\"-45\"\n        y=\"-153\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n      <filter\n        id=\"gemini__g\"\n        width=\"299.5\"\n        height=\"329\"\n        x=\"-41\"\n        y=\"91\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n      <filter\n        id=\"gemini__h\"\n        width=\"299.5\"\n        height=\"329\"\n        x=\"-39\"\n        y=\"132\"\n        color-interpolation-filters=\"sRGB\"\n        filterUnits=\"userSpaceOnUse\"\n      >\n        <feFlood flood-opacity=\"0\" result=\"BackgroundImageFix\" />\n        <feBlend in=\"SourceGraphic\" in2=\"BackgroundImageFix\" result=\"shape\" />\n        <feGaussianBlur result=\"effect1_foregroundBlur_69_17998\" stdDeviation=\"32\" />\n      </filter>\n    </defs>\n  </svg>"
const openrouterProviderSvg = "<svg role=\"img\" viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><title>OpenRouter</title><path d=\"M16.778 1.844v1.919q-.569-.026-1.138-.032-.708-.008-1.415.037c-1.93.126-4.023.728-6.149 2.237-2.911 2.066-2.731 1.95-4.14 2.75-.396.223-1.342.574-2.185.798-.841.225-1.753.333-1.751.333v4.229s.768.108 1.61.333c.842.224 1.789.575 2.185.799 1.41.798 1.228.683 4.14 2.75 2.126 1.509 4.22 2.11 6.148 2.236.88.058 1.716.041 2.555.005v1.918l7.222-4.168-7.222-4.17v2.176c-.86.038-1.611.065-2.278.021-1.364-.09-2.417-.357-3.979-1.465-2.244-1.593-2.866-2.027-3.68-2.508.889-.518 1.449-.906 3.822-2.59 1.56-1.109 2.614-1.377 3.978-1.466.667-.044 1.418-.017 2.278.02v2.176L24 6.014Z\"/></svg>"
// OpenCode dark variant from the same T3 Icons.tsx (MIT).
const opencodeProviderSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 40" fill="none"><path d="M24 32H8V16H24V32Z" fill="#4B4646"/><path d="M24 8H8V32H24V8ZM32 40H0V0H32V40Z" fill="#F1ECEC"/></svg>'
// More provider marks, matched by the whole slug. Grok and GitHub Copilot: T3 Code
// Icons.tsx at commit de251fc2971a (MIT). The rest: @lobehub/icons-static-svg 1.95.1
// (MIT, Copyright (c) 2023 LobeHub). Entries with "svg" keep their own colors.
const extraProviderIcons = [
  ["xai(?:-oauth)?", { viewBox: "0 0 24 24", attrs: "", body: "<path d=\"M9.26905 15.284L17.2479 9.36086C17.6391 9.07047 18.1981 9.18374 18.3845 9.63478C19.3655 12.0135 18.9272 14.8721 16.9755 16.8349C15.0238 18.7976 12.3082 19.228 9.8261 18.2477L7.1146 19.5102C11.0037 22.1834 15.7263 21.5223 18.6774 18.5525C21.0182 16.1985 21.7432 12.9897 21.0653 10.0961L21.0714 10.1023C20.0884 5.85143 21.3131 4.15233 23.8218 0.677913C23.8812 0.595532 23.9406 0.513151 24 0.428711L20.6987 3.74866V3.73836L9.267 15.2861\"/><path d=\"M7.62249 16.7237C4.83113 14.0422 5.3124 9.89222 7.69417 7.49905C9.45541 5.72786 12.341 5.00497 14.86 6.06768L17.5653 4.81138C17.0779 4.45714 16.4533 4.07613 15.7365 3.80839C12.4966 2.46764 8.6178 3.13492 5.98413 5.78141C3.45081 8.32904 2.65415 12.2463 4.02219 15.5889C5.04412 18.0871 3.36889 19.8541 1.68137 21.6377C1.08337 22.2699 0.483318 22.9022 0 23.5716L7.62045 16.7257\"/>" }],
  ["copilot(?:-acp)?", { viewBox: "0 0 256 208", attrs: "", body: "<path d=\"M205.3 31.4c14 14.8 20 35.2 22.5 63.6 6.6 0 12.8 1.5 17 7.2l7.8 10.6c2.2 3 3.4 6.6 3.4 10.4v28.7a12 12 0 0 1-4.8 9.5C215.9 187.2 172.3 208 128 208c-49 0-98.2-28.3-123.2-46.6a12 12 0 0 1-4.8-9.5v-28.7c0-3.8 1.2-7.4 3.4-10.5l7.8-10.5c4.2-5.7 10.4-7.2 17-7.2 2.5-28.4 8.4-48.8 22.5-63.6C77.3 3.2 112.6 0 127.6 0h.4c14.7 0 50.4 2.9 77.3 31.4ZM128 78.7c-3 0-6.5.2-10.3.6a27.1 27.1 0 0 1-6 12.1 45 45 0 0 1-32 13c-6.8 0-13.9-1.5-19.7-5.2-5.5 1.9-10.8 4.5-11.2 11-.5 12.2-.6 24.5-.6 36.8 0 6.1 0 12.3-.2 18.5 0 3.6 2.2 6.9 5.5 8.4C79.9 185.9 105 192 128 192s48-6 74.5-18.1a9.4 9.4 0 0 0 5.5-8.4c.3-18.4 0-37-.8-55.3-.4-6.6-5.7-9.1-11.2-11-5.8 3.7-13 5.1-19.7 5.1a45 45 0 0 1-32-12.9 27.1 27.1 0 0 1-6-12.1c-3.4-.4-6.9-.5-10.3-.6Zm-27 44c5.8 0 10.5 4.6 10.5 10.4v19.2a10.4 10.4 0 0 1-20.8 0V133c0-5.8 4.6-10.4 10.4-10.4Zm53.4 0c5.8 0 10.4 4.6 10.4 10.4v19.2a10.4 10.4 0 0 1-20.8 0V133c0-5.8 4.7-10.4 10.4-10.4Zm-73-94.4c-11.2 1.1-20.6 4.8-25.4 10-10.4 11.3-8.2 40.1-2.2 46.2A31.2 31.2 0 0 0 75 91.7c6.8 0 19.6-1.5 30.1-12.2 4.7-4.5 7.5-15.7 7.2-27-.3-9.1-2.9-16.7-6.7-19.9-4.2-3.6-13.6-5.2-24.2-4.3Zm69 4.3c-3.8 3.2-6.4 10.8-6.7 19.9-.3 11.3 2.5 22.5 7.2 27a41.7 41.7 0 0 0 30 12.2c8.9 0 17-2.9 21.3-7.2 6-6.1 8.2-34.9-2.2-46.3-4.8-5-14.2-8.8-25.4-9.9-10.6-1-20 .7-24.2 4.3ZM128 56c-2.6 0-5.6.2-9 .5.4 1.7.5 3.7.7 5.7 0 1.5 0 3-.2 4.5 3.2-.3 6-.3 8.5-.3 2.6 0 5.3 0 8.5.3-.2-1.6-.2-3-.2-4.5.2-2 .3-4 .7-5.7-3.4-.3-6.4-.5-9-.5Z\"/>" }],
  ["groq", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M12.036 2c-3.853-.035-7 3-7.036 6.781-.035 3.782 3.055 6.872 6.908 6.907h2.42v-2.566h-2.292c-2.407.028-4.38-1.866-4.408-4.23-.029-2.362 1.901-4.298 4.308-4.326h.1c2.407 0 4.358 1.915 4.365 4.278v6.305c0 2.342-1.944 4.25-4.323 4.279a4.375 4.375 0 01-3.033-1.252l-1.851 1.818A7 7 0 0012.029 22h.092c3.803-.056 6.858-3.083 6.879-6.816v-6.5C18.907 4.963 15.817 2 12.036 2z\"></path>" }],
  ["fordex", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M5.938 12.835c.127-.039.285.02.373.143.028.038.036.092.046.14.003.014-.02.033-.04.05-.124-.098-.24-.194-.354-.291-.011-.01-.016-.027-.025-.042zM8.396 9.412c.195-.032.39-.06.588-.05a.54.54 0 01.148.026c.202.071.402.147.601.224.028.01.05.036.075.055l-.013.027a9.203 9.203 0 01-.26-.089c-.115-.038-.213-.077-.315-.098-.25-.05-.25-.046-.292-.014l.574.144c.275.139.55.276.823.417.042.022.09.057.107.098.026.06.063.076.117.072.066-.006.132-.017.213-.027l-.04.086c.051.08.142.02.216.064-.074.13-.247.09-.334.199l.061.074-.12.087c0 .106-.038.168-.306.243l.026.085-.196.042.07.124h-.25l-.007.137c-.081-.01-.161-.018-.244-.027l-.053.123c-.027-.008-.052-.011-.073-.023-.067-.038-.128-.056-.195.006-.019.017-.063.014-.093.008-.026-.006-.05-.029-.07-.042-.11.095-.11.095-.208.003-.057.046-.12.074-.186.011-.063.027-.123-.02-.178-.014-.07.007-.097-.035-.133-.07l-.13.033c-.013-.236-.194-.19-.34-.203.005-.072.05-.092.095-.094a.474.474 0 01.159.022c.164.05.32.12.496.138.203.021.405.029.601-.015.265-.059.52-.149.707-.365.049-.056.083-.127.117-.195.019-.038.02-.084-.02-.116a1.397 1.397 0 00-.382-.217c.024.12-.031.182-.115.221 0 .014-.004.025 0 .03.08.115.084.16-.007.267a1.39 1.39 0 01-.218.211.477.477 0 01-.641-.05 1.36 1.36 0 01-.133-.152c-.078-.107-.076-.108-.033-.236-.165-.08-.128-.226-.104-.364.008-.05.028-.096.049-.163-.04.014-.067.017-.087.032a.897.897 0 00-.316.357c-.007.016-.01.034-.02.047-.012.015-.034.038-.045.035-.02-.006-.037-.027-.05-.045-.008-.012-.007-.032-.012-.057h-.126l.053-.172a14.82 14.82 0 00-.039-.049l.11-.284c-.06.026-.091.044-.124.051-.03.007-.064 0-.095 0 0-.031-.01-.07.004-.092.149-.22.305-.428.593-.476z\"></path><path d=\"M8.06 10.788c-.003-.038-.004-.075.037-.062.016.006.034.048.028.067-.01.04-.038.032-.064-.005z\"></path><path clip-rule=\"evenodd\" d=\"M11.981.009c.226-.012.453-.011.679 0 .247.01.495.024.74.062.401.064.798.157 1.19.273.463.138.92.299 1.356.511a7.31 7.31 0 012.948 2.642c.292.469.536.963.739 1.479.219.556.446 1.11.623 1.683.204.654.329 1.326.458 1.997.097.504.182 1.01.29 1.511.156.722.329 1.44.494 2.16.186.812.4 1.615.63 2.415.102.355.193.713.282 1.072.11.436.202.876.254 1.323.031.278.066.557.073.837a7.56 7.56 0 01-.017.88c-.037.413-.1.818-.226 1.212a5.017 5.017 0 01-.915 1.649l-.13.156.018.023c.043-.023.088-.041.127-.068.2-.138.373-.307.531-.49.4-.46.721-.973.975-1.529a3.59 3.59 0 00.325-1.72c-.024-.424-.097-.834-.3-1.213-.013-.027-.015-.06-.03-.121.05.035.082.048.101.072.107.13.22.258.315.398.33.494.46 1.052.486 1.64a3.75 3.75 0 01-.47 1.97c-.36.655-.887 1.14-1.526 1.506-.193.111-.394.21-.595.308-.157.078-.248.211-.318.365a.522.522 0 00-.033.406.359.359 0 01.013.139c-.005.077-.077.155-.14.162-.054.006-.125-.043-.15-.116a1.206 1.206 0 01-.06-.233c-.04-.314-.155-.6-.308-.87a3.906 3.906 0 00-.73-.91 2.129 2.129 0 00-.897-.524 4.093 4.093 0 00-.692-.131c-.075-.008-.15-.04-.22.01.18.06.363.11.538.18.434.173.82.43 1.18.728.308.255.58.543.794.884.098.155.186.315.227.496.027.123.042.25.067.375.013.062-.002.109-.053.144-.047.033-.122.034-.163-.01a.455.455 0 01-.08-.14c-.03-.073-.038-.159-.078-.225a7.314 7.314 0 00-1.423-1.664c-.16-.137-.329-.26-.537-.323-.376-.114-.753-.203-1.15-.154-.213.025-.427.032-.64.053a1.6 1.6 0 00-.736.278 5.14 5.14 0 00-.834.72c-.329.342-.642.699-.955 1.055-.136.155-.264.319-.314.531a5.227 5.227 0 00-.012.051.096.096 0 01-.09.076h-.31c-.046 0-.082-.048-.072-.094.023-.108.045-.216.07-.324.075-.325.19-.635.368-.917.024-.039.04-.088.104-.08l.01.049.027.077c.28-.435.571-.834.996-1.135.283-.204.584-.378.89-.55a.196.196 0 00-.098-.002c-.162.043-.325.084-.485.134-.402.124-.764.33-1.11.566-.147.1-.298.193-.414.333a7.314 7.314 0 00-1.07 1.767.845.845 0 00-.04.12.075.075 0 01-.072.056h-.494c-.04 0-.062-.051-.036-.082.123-.14.246-.282.377-.415.275-.281.58-.532.777-.884.027-.048.063-.09.095-.135.238-.333.54-.607.818-.902.082-.086.175-.16.26-.24.029-.027.053-.057.079-.085l-.018-.025-.135.041c-.034.017-.07.031-.102.05-.248.144-.494.292-.743.433-.408.23-.825.439-1.209.711-.281.2-.591.358-.889.533-.02.012-.044.015-.08.028-.015-.135.143-.201.108-.336-.033.014-.064.02-.085.038-.111.096-.227.19-.328.296-.148.157-.284.325-.425.488-.125.143-.25.286-.373.431A.153.153 0 019.89 24H8.762a.316.316 0 00.016-.042c.028-.09.085-.172.083-.28-.091-.018-.162.001-.212.077a4.45 4.45 0 00-.136.215c-.01.016-.024.03-.042.03h-.093c-.019 0-.029-.022-.017-.037.071-.088.14-.178.209-.268.001-.002-.006-.012-.012-.024-.014.004-.03.006-.045.013-.176.09-.352.181-.527.274a.363.363 0 01-.168.042H5.202c-.026 0-.039-.036-.019-.053.21-.178.402-.374.558-.605.335-.496.538-1.047.667-1.629.004-.02-.003-.043-.006-.091-.037.048-.059.072-.076.1a1.943 1.943 0 01-.334.415c-.28.258-.59.448-.983.464-.297.012-.588 0-.865-.127-.46-.21-.722-.57-.794-1.072-.025-.17-.017-.171-.182-.219A3.513 3.513 0 011.97 20.6a2.286 2.286 0 01-.808-1.13 3.569 3.569 0 01-.16-1.245c.002-.034.016-.067.024-.1.032.023.046.043.05.066.033.153.059.308.096.46.086.355.257.664.516.92.258.256.571.419.91.532.358.118.717.138 1.07-.016a1.89 1.89 0 00.621-.452c.328-.348.533-.76.648-1.223.009-.034.005-.071.007-.11-.015.006-.026.006-.03.011-.031.05-.064.1-.093.152-.284.502-.679.887-1.196 1.135-.351.17-.718.255-1.11.159a1.607 1.607 0 01-.971-.64 2.006 2.006 0 01-.368-.924 2.903 2.903 0 01.02-.886c.05-.439.466-1.17.742-1.271-.02.063-.035.112-.053.16-.043.116-.097.227-.13.345a1.901 1.901 0 00-.05.82c.033.212.09.416.204.6.147.236.346.407.62.465.11.023.225.014.338.018a.576.576 0 00.386-.131c.164-.128.282-.292.366-.481.168-.375.24-.777.309-1.179.05-.296.093-.594.133-.893.039-.281.071-.563.104-.845.026-.232.048-.464.074-.696.024-.228.052-.455.076-.683.024-.227.047-.455.069-.683.013-.14.022-.28.034-.42l.037-.417c.022-.25.041-.5.065-.748.008-.082-.02-.132-.09-.177a2.46 2.46 0 01-.492-.418c-.1-.109-.188-.228-.282-.342-.035-.042-.056-.097-.116-.118a2.084 2.084 0 00.275.597c.06.092.131.176.196.265.063.086.182.115.234.226-.028.003-.046.01-.06.006a4.74 4.74 0 01-.22-.057 2.71 2.71 0 01-1.287-.819c-.435-.487-.656-1.076-.71-1.723a5.206 5.206 0 01.014-1.06c.072-.602.22-1.186.45-1.745.155-.376.338-.741.526-1.102.205-.393.466-.75.765-1.076.512-.559 1.104-1.024 1.726-1.448.717-.49 1.478-.898 2.277-1.233C8.244.828 8.767.632 9.31.494c.655-.166 1.31-.33 1.982-.415.229-.03.458-.058.688-.07zm-1.847 22.82c-.07.06-.147.111-.207.18-.238.27-.464.549-.668.869l-.044.108a.177.177 0 00.093-.057c.174-.19.351-.378.519-.574.104-.122.195-.255.288-.386.024-.034.03-.08.046-.12l-.027-.02zm1.65-3.695a5.51 5.51 0 00-.653.593l-.37.386a.963.963 0 01-.377.25 1.372 1.372 0 01-.467.09c-.044 0-.087.006-.151.012.028.058.043.097.064.131.15.242.301.482.45.724.136.22.276.438.399.666.068.125.105.267.156.404.077.027.14-.018.202-.048.29-.135.579-.274.867-.412.213-.101.437-.186.636-.31.347-.215.68-.455 1.018-.685.015-.01.026-.028.042-.046-.023-.019-.038-.037-.056-.044-.287-.111-.527-.3-.77-.482a5.319 5.319 0 01-.506-.42 1.757 1.757 0 01-.41-.653c-.019-.049-.045-.095-.075-.156zm-5.847.264c-.06.096-.097.194-.132.293a3.38 3.38 0 01-.555 1.01c-.2.25-.455.412-.762.493-.23.06-.464.076-.7.07-.048-.002-.097.002-.158.005.016.04.021.066.035.085.1.145.23.246.4.295.157.046.316.034.498.023.181-.037.343-.115.485-.234.238-.199.402-.454.536-.732.175-.363.264-.751.342-1.144.01-.053.008-.11.011-.164zm14.945-4.586c.008.029.016.057.027.107.024.155.051.31.072.464.03.219.067.437.078.657.017.344.027.689-.014 1.033-.037.315-.063.633-.116.946a6.153 6.153 0 01-.46 1.518c-.008.018-.01.039-.02.082.047-.03.077-.042.098-.064.085-.083.17-.167.248-.255.271-.305.458-.66.596-1.043.18-.498.228-1.011.145-1.531-.103-.65-.33-1.263-.597-1.881a9.055 9.055 0 00-.024-.055l-.033.022zM5.797 8.29a.26.26 0 00.018.153c.124.251.25.501.379.75.025.049.066.09.03.163-.284.06-.578.119-.88.255.059.038.097.06.132.087.042.032.112.058.09.12-.01.033-.075.048-.117.072.017.01.043.021.067.036.166.102.33.207.447.368.138.192.229.404.188.644-.079.469-.306.85-.69 1.132-.054.04-.106.083-.161.122a.243.243 0 00-.103.245.77.77 0 00.055.195c.083.196.22.35.375.492.083.076.159.164.222.257a.37.37 0 01.025.377c-.023.05-.05.099-.076.148-.03.06-.028.111.022.162.041.042.08.089.112.138.038.058.078.079.147.05a.486.486 0 01.333-.006c.16.046.302.126.444.21.13.077.264.149.4.219.067.035.14.05.219.026.071-.022.124.01.145.076.02.064-.003.108-.074.139-.07.03-.137.063-.209.088-.1.035-.201.073-.314.077-.013-.107.11-.088.127-.159-.206-.126-.643-.145-.801-.034.063.112.035.21-.096.313-.13-.1-.025-.202.002-.3a.209.209 0 00-.249.17c-.015.101.067.216.178.224.108.007.218-.005.326-.012.06-.005.12-.027.199 0-.103.123-.248.127-.357.19.002.05.07.086.019.131-.053.048-.095-.001-.132-.03-.08-.063-.16-.126-.231-.197a.474.474 0 01-.157-.311.52.52 0 00-.043-.172c-.032-.074-.032-.137.033-.19-.018-.03-.028-.053-.045-.072a1.222 1.222 0 01-.196-.369c-.053-.137-.046-.264.048-.381.024-.03.05-.06.064-.095a.664.664 0 00.047-.168c.017-.165-.064-.287-.182-.387-.186-.156-.36-.322-.46-.551-.005-.011-.024-.017-.037-.026-.011.017-.024.027-.025.038-.019.185-.045.37-.052.557-.014.377.058.743.162 1.104.118.41.289.798.488 1.173.267.502.537 1.002.812 1.5.055.098.13.189.208.27.198.202.452.272.724.273.202 0 .404-.006.605-.026.295-.03.59-.073.884-.113.183-.025.365-.057.548-.08.21-.026.38.073.522.21.16.156.305.327.447.5.22.265.397.56.554.867.05.098.07.1.147.03.13-.121.26-.242.394-.36.067-.059.088-.12.067-.213a3.535 3.535 0 01-.085-.796c.002-.157.006-.314.018-.471.015-.224.03-.45.06-.672a59.114 59.114 0 01.362-2.298c.087-.493.182-.984.268-1.477.06-.347.118-.694.162-1.043.034-.273.055-.55.063-.825.011-.332.003-.665.002-.998 0-.077.004-.155-.01-.23-.028-.142-.01-.155-.162-.19a5.826 5.826 0 00-.607-.107c-.146-.018-.207-.053-.221-.19-.006-.049-.025-.098-.041-.146-.009-.025-.024-.048-.046-.09l-.025.264c-.009.096-.029.116-.127.115-.055 0-.11-.008-.164-.008-.476 0-.952-.008-1.426.032-.095.008-.173-.015-.226-.103-.04-.066-.088-.126-.134-.186-.063-.084-.086-.093-.182-.06-.195.068-.388.138-.582.21a2.71 2.71 0 00-.675.394.986.986 0 01-.323.168c-.033.01-.07.008-.127.013.02-.066.024-.114.047-.15.064-.105.135-.205.205-.306.023-.033.049-.063.073-.095l-.015-.023-.201.037c-.146.04-.296.07-.437.122-.148.053-.266.023-.386-.072a3.623 3.623 0 01-.733-.786l-.093-.132zm8.592 8.963l-.147.09c-.22.134-.44.266-.659.402-.093.058-.184.12-.27.188-.085.07-.124.161-.072.272.047.1.093.2.147.294.047.08.124.138.213.147.11.01.228.012.336-.012.217-.05.372-.205.528-.357a.291.291 0 00.087-.308c-.046-.18-.079-.365-.118-.547-.011-.052-.027-.103-.045-.169zm-.257-2.409c-.12.291-.205.597-.325.91-.151.433-.294.87-.435 1.323.036-.01.054-.01.067-.018.261-.16.522-.324.785-.484.054-.033.071-.078.065-.138-.012-.13-.024-.262-.034-.393l-.068-.886c-.008-.103-.02-.206-.029-.31-.009 0-.017-.002-.026-.004zm3.081-8.13l.099.285c.08.231.159.463.24.714l.58 1.952c.187.63.372 1.262.558 1.893.114.382.235.762.343 1.146.072.257.126.519.186.799.044.206.087.413.127.64.034.106.023.226.077.325l.025-.006-.068-.362c-.038-.206-.077-.412-.113-.638-.015-.07-.029-.141-.046-.211-.095-.396-.177-.796-.29-1.187-.196-.685-.413-1.364-.618-2.046-.165-.549-.322-1.1-.488-1.648-.069-.227-.15-.45-.226-.695l-.117-.336c-.037-.107-.075-.216-.115-.322-.04-.106-.084-.21-.127-.314a7.558 7.558 0 01-.027.01zM6.225 14.304c-.063-.001-.115.014-.134.083a.35.35 0 00.41.012 4.533 4.533 0 00-.276-.095zM5.23 11.98c-.026-.027-.057-.048-.075.002-.012.032-.007.07-.01.113.082-.037.082-.037.085-.115zm.062-1.189a.135.135 0 00-.088.056.197.197 0 00-.025.11c.005.152.01.306.026.457a.751.751 0 00.066.218c.061.136.157.167.288.101.055-.027.06-.054.025-.11a4.52 4.52 0 01-.129-.211c-.015-.068-.066-.131-.033-.207.04-.09-.076-.116-.074-.19V10.874c-.003-.038-.006-.087-.056-.083zm-.017-.968a.867.867 0 00-.467.127c-.076.045-.084.07-.05.158.034.087.07.173.115.254.064.117.09.125.21.077a.657.657 0 01.336-.053c.202.022.357.136.504.264l.092.077c.007-.006.014-.013.022-.018-.019-.105-.035-.226-.149-.264-.157-.053-.324-.075-.508-.117l-.24-.005c.24-.169.452-.044.687.009-.063-.115-.153-.147-.23-.193-.082-.05-.17-.092-.25-.144-.06-.037-.12-.08-.072-.172zm10.233.325c-.23-.01-.427.08-.608.211-.034.026-.06.065-.105.117.087.026.15.046.232.065.044-.015.088-.03.13-.046.306-.114.61-.115.904.031.126.063.237.04.366-.005-.02-.031-.03-.054-.045-.071a.986.986 0 00-.448-.273c-.14-.044-.284-.024-.426-.03zM7.99 6.483a.308.308 0 00.002.133c.08.321.156.643.242.962.104.387.27.75.456 1.103.02.037.061.08.098.087a.404.404 0 00.253-.051l-.472-.84c-.23-.448-.405-.92-.579-1.394zM10.397.497c-.2-.008-.405.004-.603.034-.236.035-.47.087-.7.152-.287.08-.569.18-.852.273-.04.013-.074.038-.11.058.028.014.05.018.07.014.287-.068.58-.085.873-.09.134-.002.269.009.402.025.19.024.382.048.57.09.456.104.874.3 1.265.556.464.306.888.66 1.257 1.078.205.232.395.475.56.739.17.274.315.561.449.856.273.601.456 1.232.6 1.876.04.173.07.348.1.524.017.104.065.167.17.19.122.028.2.105.22.251-.003.102-.06.174-.129.24a1.065 1.065 0 00-.268.358.164.164 0 00.083-.039c.08-.086.162-.172.235-.265a.56.56 0 00.13-.333c.009-.05.022-.1.024-.15.007-.124-.017-.15-.143-.168-.025-.004-.049-.014-.073-.015-.082-.007-.125-.063-.137-.131-.033-.198-.004-.355.247-.408.086-.018.174-.03.26-.042.158-.023.315-.053.473-.067.14-.012.19.033.226.167.008.029.018.057.021.087.019.179-.008.225-.141.288-.027.013-.055.024-.078.042a.148.148 0 00-.051.067c-.039.144.073.382.206.445l.673.32c.023.011.05.015.075.023l.018-.026c-.015-.008-.032-.013-.044-.024a2.27 2.27 0 00-.544-.32 4.898 4.898 0 00-.173-.075.203.203 0 01-.126-.191c-.003-.085.045-.154.128-.187l.059-.025c.099-.044.118-.076.112-.187a.384.384 0 00-.008-.063c-.067-.294-.123-.59-.205-.88a9.478 9.478 0 00-.826-2.036 7.465 7.465 0 00-1.39-1.805 4.536 4.536 0 00-1.177-.824 3.656 3.656 0 00-1.016-.328 6.155 6.155 0 00-.712-.074zm6.719 5.955c.01.014.018.028.038.034l-.022-.044-.016.01zM4.103 3.917a.062.062 0 01-.03.012.455.455 0 01-.04.039c-.01.01-.02.02-.045.04l-.363.354c-.088.085-.17.178-.266.253-.284.22-.425.53-.544.855a.132.132 0 00-.007.071c.013.055.033.108.052.168l.074.026c-.017.056-.03.105-.047.152-.058.164-.118.327-.175.491-.005.015.008.036.019.077.08-.175.158-.33.225-.489.228-.544.484-1.074.819-1.561.09-.133.182-.266.283-.401.004-.006.007-.013.022-.03.001-.016.003-.032.015-.04l.008-.017zm12.976 2.408a.023.023 0 01.009.019.073.073 0 00-.006.01.188.188 0 00.007.02l.018.022c.002-.007.007-.016.005-.021-.003-.01-.012-.018-.02-.038a1.331 1.331 0 01-.013-.012zM4.199 4.48c-.003.004-.008.008-.027.014-.005.013-.011.025-.031.047a2.085 2.085 0 01-.124.167c-.048.07-.116.055-.181.041-.134-.028-.228.016-.287.143-.089.187-.187.37-.273.56-.049.108-.11.216-.118.36.081.003.154.007.228.008h.228a2.563 2.563 0 01-.079.264c-.01.052-.022.103-.033.155l.02.004c.018-.046.037-.092.067-.153.066-.142.13-.285.2-.426.02-.04.034-.1.116-.092 0 .043.004.084 0 .124-.005.045-.017.09-.028.143.141.043.086.174.115.269.102-.022.104-.195.248-.144v.205l.017.002.439-1.059c-.13 0-.246-.02-.358.033-.024.011-.058-.001-.108-.004.075-.15.139-.278.211-.417a.128.128 0 01.025-.036c0-.015-.001-.03.008-.038l.006-.02c-.005.006-.01.011-.028.017-.004.012-.009.024-.026.045a.085.085 0 01-.032.033c-.123.157-.09.164-.258.106-.079-.027-.078-.028-.047-.144.028-.046.056-.093.098-.15 0-.016-.001-.032.007-.042L4.2 4.48zm2.073-.67c-.003.006-.007.011-.027.016-.094.125-.194.246-.28.377-.155.238-.301.481-.451.723-.14.224-.345.368-.575.481-.017.008-.04.006-.079.011.012-.059.016-.109.033-.153a6.076 6.076 0 01.229-.518l-.007-.02a.138.138 0 01-.035.025c-.028.05-.055.1-.093.164-.26.424-.443.817-.442.95.024.004.048.011.073.013.177.013.188.007.26-.165.03-.07.077-.12.147-.15l.175-.07c.044-.018.085-.057.146-.032.003.05-.01.11.014.145.042.062.044.125.047.193.002.049.017.098.026.147.029-.034.039-.065.05-.097.142-.39.277-.782.428-1.17.1-.256.22-.504.33-.756.013-.03.013-.067.03-.092V3.81zm3.987-.34c0 .045.01.084.021.123.042.16.094.318.124.48.024.133.023.27.028.406 0 .033-.019.067-.032.11-.094-.058-.047-.158-.106-.215h-.125c-.015.072-.01.152-.046.2-.066.085-.155.154-.236.227-.043.038-.078.018-.103-.025l-.046-.087c-.065.035-.117.069-.172.093-.116.051-.235.095-.35.147-.085.038-.09.053-.07.147.014.075.034.148.047.223.013.072.05.109.123.124.233.05.462.115.657.265.058-.102.058-.102.168-.151.03-.014.06-.03.092-.042.08-.03.115-.017.15.06.023.048.041.098.066.158.06-.14-.042-.267.017-.416.157.18.24.39.375.567a.235.235 0 00.022-.098c.002-.124 0-.247.002-.371 0-.034.013-.067.02-.1l.032-.003c.11.155.13.354.226.52a3.036 3.036 0 00-.01-.392c-.004-.045 0-.074.05-.088.08.036.116.14.215.158-.03-.275-.423-1.137-.798-1.635-.114-.127-.2-.28-.34-.386zm-2.667.696c-.019.034-.03.05-.037.067-.061.185-.125.37-.18.556-.031.105-.087.169-.195.19-.09.019-.178.052-.268.073-.038.009-.089.015-.118-.003-.024-.016-.025-.069-.036-.106-.064.076-.082.087-.17.047-.133-.062-.262-.135-.393-.201-.048-.025-.093-.063-.17-.03-.043.12-.091.25-.137.382-.099.28-.087.242.095.453.046.048.102.03.154.023.054-.009.106-.03.16-.036.13-.013.26-.08.367-.015.204-.064.387-.122.571-.178.05-.015.089.005.114.054.022.042.034.093.082.121.038-.056-.013-.128.063-.178l.14.241-.042-1.46zm.278.358c-.096-.01-.107.01-.11.108-.002.038-.003.078.002.115.03.2.099.386.174.57.002.006.012.01.022.015l.078-.05c.052.036.081.088.153.088.205-.002.41.014.616.012.099-.001.158.042.205.12.018.03.024.077.088.066l-.08-.394c-.05-.195-.085-.395-.172-.589-.057.057-.114.068-.18.046a.72.72 0 00-.135-.028c-.22-.028-.44-.059-.66-.08zm10.254-1.727c.089.163.155.316.139.491-.016.168.026.342-.044.516-.047-.033-.088-.082-.112-.075-.117.035-.164-.057-.227-.115a4.772 4.772 0 01-.286-.29l-.104-.113a4.856 4.856 0 01-.023.019c.035.046.07.093.11.156.04.064.084.127.122.193.034.058.065.118.031.205-.082-.01-.164-.019-.246-.032-.06-.01-.101 0-.124.07-.031.098-.037.096-.15.09.02.042.036.08.057.116.041.074.03.138-.03.196-.06.06-.118.122-.178.181a.175.175 0 01-.185.046c-.222-.061-.447-.113-.67-.174-.032-.009-.063-.04-.086-.068-.03-.04-.052-.087-.08-.13-.044-.07-.09-.138-.136-.207a.18.18 0 00-.014.105c.012.127.03.253.035.38.005.1-.024.12-.121.104-.104-.017-.206-.04-.31-.058-.064-.012-.131-.028-.202.03l.081.208c.09 0 .166-.01.237.002a.819.819 0 01.458.251c.078.083.154.168.241.26l.018-.005c-.004-.006-.008-.013-.01-.04.014-.056-.062-.118.018-.178.031.03.064.057.088.09.058.078.111.159.169.257l.089.141.024-.013a2093.819 2093.819 0 01-.427-.934c.055.007.083.007.108.016.193.07.385.142.577.216.074.028.147.06.219.094.062.028.112.018.157-.033.05-.056.102-.112.154-.167.05-.051.095-.046.132.014.016.025.026.053.04.08.071.138.143.277.217.433l.159.308.025-.011c-.044-.106-.07-.218-.138-.334-.057-.182-.168-.346-.206-.545.136.034.362.326.567.732l.057.074.018-.011a1.563 1.563 0 01-.052-.127c-.046-.145-.097-.29-.136-.436-.022-.083-.036-.173.022-.26l.109.058-.026-.207.027-.016c.022.02.05.036.065.06.073.108.143.22.215.33.01.016.029.029.043.043-.036-.217-.2-.38-.229-.626l.155.112c.014-.166.012-.319.042-.465.032-.158-.023-.297-.063-.445.024.004.036.006.055.025.092.124.183.249.277.371.02.027.05.047.069.087l.04.063.019-.015a.293.293 0 01-.053-.082 27.922 27.922 0 01-.332-.49c-.221-.311-.363-.467-.485-.521zm-6.57.327c-.003.161.092.275.069.415l-.368.087c.09.139.032.237-.052.331-.05.057-.092.122-.143.178-.037.04-.046.078-.018.126l.16.275c.029.048.072.066.128.064.076-.003.152 0 .228-.001.116-.003.216.022.275.137.006.014.02.024.044.052.004-.059-.003-.098.01-.13.016-.04.04-.099.072-.108.084-.023.173-.024.26-.03.013-.001.027.018.04.029l.071.065c.019-.11-.082-.198-.024-.31l.126.04c-.026-.123-.07-.245-.071-.366 0-.123.051-.243.115-.36.107.062.16.156.234.253.183.265.36.533.494.834.165-.078.27.068.407.088-.003-.106-.133-.441-.197-.492a.142.142 0 00-.102-.028c-.06.011-.119.039-.191.063-.025-.039-.056-.078-.077-.122a3.936 3.936 0 00-.473-.783c-.076-.094-.16-.182-.228-.26l-.391.285c-.049.035-.094.03-.132-.017l-.169-.207c-.025-.03-.053-.059-.097-.108z\"></path>" }],
  ["deepseek", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M23.748 4.482c-.254-.124-.364.113-.512.234-.051.039-.094.09-.137.136-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.156-.708-.311-.955-.65-.172-.241-.219-.51-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.093.172.187.129.323-.082.28-.18.552-.266.833-.055.179-.137.217-.329.14a5.526 5.526 0 01-1.736-1.18c-.857-.828-1.631-1.742-2.597-2.458a11.365 11.365 0 00-.689-.471c-.985-.957.13-1.743.388-1.836.27-.098.093-.432-.779-.428-.872.004-1.67.295-2.687.684a3.055 3.055 0 01-.465.137 9.597 9.597 0 00-2.883-.102c-1.885.21-3.39 1.102-4.497 2.623C.082 8.606-.231 10.684.152 12.85c.403 2.284 1.569 4.175 3.36 5.653 1.858 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.133-.284 4.994-1.86.47.234.962.327 1.78.397.63.059 1.236-.03 1.705-.128.735-.156.684-.837.419-.961-2.155-1.004-1.682-.595-2.113-.926 1.096-1.296 2.746-2.642 3.392-7.003.05-.347.007-.565 0-.845-.004-.17.035-.237.23-.256a4.173 4.173 0 001.545-.475c1.396-.763 1.96-2.015 2.093-3.517.02-.23-.004-.467-.247-.588zM11.581 18c-2.089-1.642-3.102-2.183-3.52-2.16-.392.024-.321.471-.235.763.09.288.207.486.371.739.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.167-1.361-.802-2.5-1.86-3.301-3.307-.774-1.393-1.224-2.887-1.298-4.482-.02-.386.093-.522.477-.592a4.696 4.696 0 011.529-.039c2.132.312 3.946 1.265 5.468 2.774.868.86 1.525 1.887 2.202 2.891.72 1.066 1.494 2.082 2.48 2.914.348.292.625.514.891.677-.802.09-2.14.11-3.054-.614zm1-6.44a.306.306 0 01.415-.287.302.302 0 01.2.288.306.306 0 01-.31.307.303.303 0 01-.304-.308zm3.11 1.596c-.2.081-.399.151-.59.16a1.245 1.245 0 01-.798-.254c-.274-.23-.47-.358-.552-.758a1.73 1.73 0 01.016-.588c.07-.327-.008-.537-.239-.727-.187-.156-.426-.199-.688-.199a.559.559 0 01-.254-.078c-.11-.054-.2-.19-.114-.358.028-.054.16-.186.192-.21.356-.202.767-.136 1.146.016.352.144.618.408 1.001.782.391.451.462.576.685.914.176.265.336.537.445.848.067.195-.019.354-.25.452z\" fill=\"#4D6BFE\"></path></svg>" }],
  ["qwen-oauth|alibaba(?:-.+)?|dashscope-.+", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M12.604 1.34c.393.69.784 1.382 1.174 2.075a.18.18 0 00.157.091h5.552c.174 0 .322.11.446.327l1.454 2.57c.19.337.24.478.024.837-.26.43-.513.864-.76 1.3l-.367.658c-.106.196-.223.28-.04.512l2.652 4.637c.172.301.111.494-.043.77-.437.785-.882 1.564-1.335 2.34-.159.272-.352.375-.68.37-.777-.016-1.552-.01-2.327.016a.099.099 0 00-.081.05 575.097 575.097 0 01-2.705 4.74c-.169.293-.38.363-.725.364-.997.003-2.002.004-3.017.002a.537.537 0 01-.465-.271l-1.335-2.323a.09.09 0 00-.083-.049H4.982c-.285.03-.553-.001-.805-.092l-1.603-2.77a.543.543 0 01-.002-.54l1.207-2.12a.198.198 0 000-.197 550.951 550.951 0 01-1.875-3.272l-.79-1.395c-.16-.31-.173-.496.095-.965.465-.813.927-1.625 1.387-2.436.132-.234.304-.334.584-.335a338.3 338.3 0 012.589-.001.124.124 0 00.107-.063l2.806-4.895a.488.488 0 01.422-.246c.524-.001 1.053 0 1.583-.006L11.704 1c.341-.003.724.032.9.34zm-3.432.403a.06.06 0 00-.052.03L6.254 6.788a.157.157 0 01-.135.078H3.253c-.056 0-.07.025-.041.074l5.81 10.156c.025.042.013.062-.034.063l-2.795.015a.218.218 0 00-.2.116l-1.32 2.31c-.044.078-.021.118.068.118l5.716.008c.046 0 .08.02.104.061l1.403 2.454c.046.081.092.082.139 0l5.006-8.76.783-1.382a.055.055 0 01.096 0l1.424 2.53a.122.122 0 00.107.062l2.763-.02a.04.04 0 00.035-.02.041.041 0 000-.04l-2.9-5.086a.108.108 0 010-.113l.293-.507 1.12-1.977c.024-.041.012-.062-.035-.062H9.2c-.059 0-.073-.026-.043-.077l1.434-2.505a.107.107 0 000-.114L9.225 1.774a.06.06 0 00-.053-.031zm6.29 8.02c.046 0 .058.02.034.06l-.832 1.465-2.613 4.585a.056.056 0 01-.05.029.058.058 0 01-.05-.029L8.498 9.841c-.02-.034-.01-.052.028-.054l.216-.012 6.722-.012z\" fill=\"url(#lobe-icons-qwen-_R_0_)\" fill-rule=\"nonzero\"></path><defs><linearGradient id=\"lobe-icons-qwen-_R_0_\" x1=\"0%\" x2=\"100%\" y1=\"0%\" y2=\"0%\"><stop offset=\"0%\" stop-color=\"#6336E7\" stop-opacity=\".84\"></stop><stop offset=\"100%\" stop-color=\"#6F69F7\" stop-opacity=\".84\"></stop></linearGradient></defs></svg>" }],
  ["kimi-coding(?:-cn)?", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M21.846 0a1.923 1.923 0 110 3.846H20.15a.226.226 0 01-.227-.226V1.923C19.923.861 20.784 0 21.846 0z\" fill=\"#1783FF\"></path><path d=\"M11.065 11.199l7.257-7.2c.137-.136.06-.41-.116-.41H14.3a.164.164 0 00-.117.051l-7.82 7.756c-.122.12-.302.013-.302-.179V3.82c0-.127-.083-.23-.185-.23H3.186c-.103 0-.186.103-.186.23V19.77c0 .128.083.23.186.23h2.69c.103 0 .186-.102.186-.23v-3.25c0-.069.025-.135.069-.178l2.424-2.406a.158.158 0 01.205-.023l6.484 4.772a7.677 7.677 0 003.453 1.283c.108.012.2-.095.2-.23v-3.06c0-.117-.07-.212-.164-.227a5.028 5.028 0 01-2.027-.807l-5.613-4.064c-.117-.078-.132-.279-.028-.381z\" fill=\"#fff\"></path></svg>" }],
  ["minimax(?:-cn|-oauth)?", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><defs><linearGradient id=\"lobe-icons-minimax-_R_0_\" x1=\"0%\" x2=\"100.182%\" y1=\"50.057%\" y2=\"50.057%\"><stop offset=\"0%\" stop-color=\"#E2167E\"></stop><stop offset=\"100%\" stop-color=\"#FE603C\"></stop></linearGradient></defs><path d=\"M16.278 2c1.156 0 2.093.927 2.093 2.07v12.501a.74.74 0 00.744.709.74.74 0 00.743-.709V9.099a2.06 2.06 0 012.071-2.049A2.06 2.06 0 0124 9.1v6.561a.649.649 0 01-.652.645.649.649 0 01-.653-.645V9.1a.762.762 0 00-.766-.758.762.762 0 00-.766.758v7.472a2.037 2.037 0 01-2.048 2.026 2.037 2.037 0 01-2.048-2.026v-12.5a.785.785 0 00-.788-.753.785.785 0 00-.789.752l-.001 15.904A2.037 2.037 0 0113.441 22a2.037 2.037 0 01-2.048-2.026V18.04c0-.356.292-.645.652-.645.36 0 .652.289.652.645v1.934c0 .263.142.506.372.638.23.131.514.131.744 0a.734.734 0 00.372-.638V4.07c0-1.143.937-2.07 2.093-2.07zm-5.674 0c1.156 0 2.093.927 2.093 2.07v11.523a.648.648 0 01-.652.645.648.648 0 01-.652-.645V4.07a.785.785 0 00-.789-.78.785.785 0 00-.789.78v14.013a2.06 2.06 0 01-2.07 2.048 2.06 2.06 0 01-2.071-2.048V9.1a.762.762 0 00-.766-.758.762.762 0 00-.766.758v3.8a2.06 2.06 0 01-2.071 2.049A2.06 2.06 0 010 12.9v-1.378c0-.357.292-.646.652-.646.36 0 .653.29.653.646V12.9c0 .418.343.757.766.757s.766-.339.766-.757V9.099a2.06 2.06 0 012.07-2.048 2.06 2.06 0 012.071 2.048v8.984c0 .419.343.758.767.758.423 0 .766-.339.766-.758V4.07c0-1.143.937-2.07 2.093-2.07z\" fill=\"url(#lobe-icons-minimax-_R_0_)\" fill-rule=\"nonzero\"></path></svg>" }],
  ["zai", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M12.105 2L9.927 4.953H.653L2.83 2h9.276zM23.254 19.048L21.078 22h-9.242l2.174-2.952h9.244zM24 2L9.264 22H0L14.736 2H24z\"></path>" }],
  ["huggingface", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M2.25 11.535c0-3.407 1.847-6.554 4.844-8.258a9.822 9.822 0 019.687 0c2.997 1.704 4.844 4.851 4.844 8.258 0 5.266-4.337 9.535-9.687 9.535S2.25 16.8 2.25 11.535z\" fill=\"#FF9D0B\"></path><path d=\"M11.938 20.086c4.797 0 8.687-3.829 8.687-8.551 0-4.722-3.89-8.55-8.687-8.55-4.798 0-8.688 3.828-8.688 8.55 0 4.722 3.89 8.55 8.688 8.55z\" fill=\"#FFD21E\"></path><path d=\"M11.875 15.113c2.457 0 3.25-2.156 3.25-3.263 0-.576-.393-.394-1.023-.089-.582.283-1.365.675-2.224.675-1.798 0-3.25-1.693-3.25-.586 0 1.107.79 3.263 3.25 3.263h-.003z\" fill=\"#FF323D\"></path><path d=\"M14.76 9.21c.32.108.445.753.767.585.447-.233.707-.708.659-1.204a1.235 1.235 0 00-.879-1.059 1.262 1.262 0 00-1.33.394c-.322.384-.377.92-.14 1.36.153.283.638-.177.925-.079l-.002.003zm-5.887 0c-.32.108-.448.753-.768.585a1.226 1.226 0 01-.658-1.204c.048-.495.395-.913.878-1.059a1.262 1.262 0 011.33.394c.322.384.377.92.14 1.36-.152.283-.64-.177-.925-.079l.003.003zm1.12 5.34a2.166 2.166 0 011.325-1.106c.07-.02.144.06.219.171l.192.306c.069.1.139.175.209.175.074 0 .15-.074.223-.172l.205-.302c.08-.11.157-.188.234-.165.537.168.986.536 1.25 1.026.932-.724 1.275-1.905 1.275-2.633 0-.508-.306-.426-.81-.19l-.616.296c-.52.24-1.148.48-1.824.48-.676 0-1.302-.24-1.823-.48l-.589-.283c-.52-.248-.838-.342-.838.177 0 .703.32 1.831 1.187 2.56l.18.14z\" fill=\"#3A3B45\"></path><path d=\"M17.812 10.366a.806.806 0 00.813-.8c0-.441-.364-.8-.813-.8a.806.806 0 00-.812.8c0 .442.364.8.812.8zm-11.624 0a.806.806 0 00.812-.8c0-.441-.364-.8-.812-.8a.806.806 0 00-.813.8c0 .442.364.8.813.8zM4.515 13.073c-.405 0-.765.162-1.017.46a1.455 1.455 0 00-.333.925 1.801 1.801 0 00-.485-.074c-.387 0-.737.146-.985.409a1.41 1.41 0 00-.2 1.722 1.302 1.302 0 00-.447.694c-.06.222-.12.69.2 1.166a1.267 1.267 0 00-.093 1.236c.238.533.81.958 1.89 1.405l.24.096c.768.3 1.473.492 1.478.494.89.243 1.808.375 2.732.394 1.465 0 2.513-.443 3.115-1.314.93-1.342.842-2.575-.274-3.763l-.151-.154c-.692-.684-1.155-1.69-1.25-1.912-.195-.655-.71-1.383-1.562-1.383-.46.007-.889.233-1.15.605-.25-.31-.495-.553-.715-.694a1.87 1.87 0 00-.993-.312zm14.97 0c.405 0 .767.162 1.017.46.216.262.333.588.333.925.158-.047.322-.071.487-.074.388 0 .738.146.985.409a1.41 1.41 0 01.2 1.722c.22.178.377.422.445.694.06.222.12.69-.2 1.166.244.37.279.836.093 1.236-.238.533-.81.958-1.889 1.405l-.239.096c-.77.3-1.475.492-1.48.494-.89.243-1.808.375-2.732.394-1.465 0-2.513-.443-3.115-1.314-.93-1.342-.842-2.575.274-3.763l.151-.154c.695-.684 1.157-1.69 1.252-1.912.195-.655.708-1.383 1.56-1.383.46.007.889.233 1.15.605.25-.31.495-.553.718-.694.244-.162.523-.265.814-.3l.176-.012z\" fill=\"#FF9D0B\"></path><path d=\"M9.785 20.132c.688-.994.638-1.74-.305-2.667-.945-.928-1.495-2.288-1.495-2.288s-.205-.788-.672-.714c-.468.074-.81 1.25.17 1.971.977.721-.195 1.21-.573.534-.375-.677-1.405-2.416-1.94-2.751-.532-.332-.907-.148-.782.541.125.687 2.357 2.35 2.14 2.707-.218.362-.983-.42-.983-.42S2.953 14.9 2.43 15.46c-.52.558.398 1.026 1.7 1.803 1.308.778 1.41.985 1.225 1.28-.187.295-3.07-2.1-3.34-1.083-.27 1.011 2.943 1.304 2.745 2.006-.2.7-2.265-1.324-2.685-.537-.425.79 2.913 1.718 2.94 1.725 1.075.276 3.813.859 4.77-.522zm4.432 0c-.687-.994-.64-1.74.305-2.667.943-.928 1.493-2.288 1.493-2.288s.205-.788.675-.714c.465.074.807 1.25-.17 1.971-.98.721.195 1.21.57.534.377-.677 1.407-2.416 1.94-2.751.532-.332.91-.148.782.541-.125.687-2.355 2.35-2.137 2.707.215.362.98-.42.98-.42S21.05 14.9 21.57 15.46c.52.558-.395 1.026-1.7 1.803-1.308.778-1.408.985-1.225 1.28.187.295 3.07-2.1 3.34-1.083.27 1.011-2.94 1.304-2.743 2.006.2.7 2.263-1.324 2.685-.537.423.79-2.912 1.718-2.94 1.725-1.077.276-3.815.859-4.77-.522z\" fill=\"#FFD21E\"></path></svg>" }],
  ["ollama-cloud", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M7.905 1.09c.216.085.411.225.588.41.295.306.544.744.734 1.263.191.522.315 1.1.362 1.68a5.054 5.054 0 012.049-.636l.051-.004c.87-.07 1.73.087 2.48.474.101.053.2.11.297.17.05-.569.172-1.134.36-1.644.19-.52.439-.957.733-1.264a1.67 1.67 0 01.589-.41c.257-.1.53-.118.796-.042.401.114.745.368 1.016.737.248.337.434.769.561 1.287.23.934.27 2.163.115 3.645l.053.04.026.019c.757.576 1.284 1.397 1.563 2.35.435 1.487.216 3.155-.534 4.088l-.018.021.002.003c.417.762.67 1.567.724 2.4l.002.03c.064 1.065-.2 2.137-.814 3.19l-.007.01.01.024c.472 1.157.62 2.322.438 3.486l-.006.039a.651.651 0 01-.747.536.648.648 0 01-.54-.742c.167-1.033.01-2.069-.48-3.123a.643.643 0 01.04-.617l.004-.006c.604-.924.854-1.83.8-2.72-.046-.779-.325-1.544-.8-2.273a.644.644 0 01.18-.886l.009-.006c.243-.159.467-.565.58-1.12a4.229 4.229 0 00-.095-1.974c-.205-.7-.58-1.284-1.105-1.683-.595-.454-1.383-.673-2.38-.61a.653.653 0 01-.632-.371c-.314-.665-.772-1.141-1.343-1.436a3.288 3.288 0 00-1.772-.332c-1.245.099-2.343.801-2.67 1.686a.652.652 0 01-.61.425c-1.067.002-1.893.252-2.497.703-.522.39-.878.935-1.066 1.588a4.07 4.07 0 00-.068 1.886c.112.558.331 1.02.582 1.269l.008.007c.212.207.257.53.109.785-.36.622-.629 1.549-.673 2.44-.05 1.018.186 1.902.719 2.536l.016.019a.643.643 0 01.095.69c-.576 1.236-.753 2.252-.562 3.052a.652.652 0 01-1.269.298c-.243-1.018-.078-2.184.473-3.498l.014-.035-.008-.012a4.339 4.339 0 01-.598-1.309l-.005-.019a5.764 5.764 0 01-.177-1.785c.044-.91.278-1.842.622-2.59l.012-.026-.002-.002c-.293-.418-.51-.953-.63-1.545l-.005-.024a5.352 5.352 0 01.093-2.49c.262-.915.777-1.701 1.536-2.269.06-.045.123-.09.186-.132-.159-1.493-.119-2.73.112-3.67.127-.518.314-.95.562-1.287.27-.368.614-.622 1.015-.737.266-.076.54-.059.797.042zm4.116 9.09c.936 0 1.8.313 2.446.855.63.527 1.005 1.235 1.005 1.94 0 .888-.406 1.58-1.133 2.022-.62.375-1.451.557-2.403.557-1.009 0-1.871-.259-2.493-.734-.617-.47-.963-1.13-.963-1.845 0-.707.398-1.417 1.056-1.946.668-.537 1.55-.849 2.485-.849zm0 .896a3.07 3.07 0 00-1.916.65c-.461.37-.722.835-.722 1.25 0 .428.21.829.61 1.134.455.347 1.124.548 1.943.548.799 0 1.473-.147 1.932-.426.463-.28.7-.686.7-1.257 0-.423-.246-.89-.683-1.256-.484-.405-1.14-.643-1.864-.643zm.662 1.21l.004.004c.12.151.095.37-.056.49l-.292.23v.446a.375.375 0 01-.376.373.375.375 0 01-.376-.373v-.46l-.271-.218a.347.347 0 01-.052-.49.353.353 0 01.494-.051l.215.172.22-.174a.353.353 0 01.49.051zm-5.04-1.919c.478 0 .867.39.867.871a.87.87 0 01-.868.871.87.87 0 01-.867-.87.87.87 0 01.867-.872zm8.706 0c.48 0 .868.39.868.871a.87.87 0 01-.868.871.87.87 0 01-.867-.87.87.87 0 01.867-.872zM7.44 2.3l-.003.002a.659.659 0 00-.285.238l-.005.006c-.138.189-.258.467-.348.832-.17.692-.216 1.631-.124 2.782.43-.128.899-.208 1.404-.237l.01-.001.019-.034c.046-.082.095-.161.148-.239.123-.771.022-1.692-.253-2.444-.134-.364-.297-.65-.453-.813a.628.628 0 00-.107-.09L7.44 2.3zm9.174.04l-.002.001a.628.628 0 00-.107.09c-.156.163-.32.45-.453.814-.29.794-.387 1.776-.23 2.572l.058.097.008.014h.03a5.184 5.184 0 011.466.212c.086-1.124.038-2.043-.128-2.722-.09-.365-.21-.643-.349-.832l-.004-.006a.659.659 0 00-.285-.239h-.004z\"></path>" }],
  ["nvidia", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M10.212 8.976V7.62c.127-.01.256-.017.388-.021 3.596-.117 5.957 3.184 5.957 3.184s-2.548 3.647-5.282 3.647a3.227 3.227 0 01-1.063-.175v-4.109c1.4.174 1.681.812 2.523 2.258l1.873-1.627a4.905 4.905 0 00-3.67-1.846 6.594 6.594 0 00-.729.044m0-4.476v2.025c.13-.01.259-.019.388-.024 5.002-.174 8.261 4.226 8.261 4.226s-3.743 4.69-7.643 4.69c-.338 0-.675-.031-1.007-.092v1.25c.278.038.558.057.838.057 3.629 0 6.253-1.91 8.794-4.169.421.347 2.146 1.193 2.501 1.564-2.416 2.083-8.048 3.763-11.24 3.763-.308 0-.603-.02-.894-.048V19.5H24v-15H10.21zm0 9.756v1.068c-3.356-.616-4.287-4.21-4.287-4.21a7.173 7.173 0 014.287-2.138v1.172h-.005a3.182 3.182 0 00-2.502 1.178s.615 2.276 2.507 2.931m-5.961-3.3c1.436-1.935 3.604-3.148 5.961-3.336V6.523C5.81 6.887 2 10.723 2 10.723s2.158 6.427 8.21 7.015v-1.166C5.77 16 4.25 10.958 4.25 10.958h-.002z\" fill=\"#74B71B\" fill-rule=\"nonzero\"></path></svg>" }],
  ["meta(?:-ai)?", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M6.897 4h-.024l-.031 2.615h.022c1.715 0 3.046 1.357 5.94 6.246l.175.297.012.02 1.62-2.438-.012-.019a48.763 48.763 0 00-1.098-1.716 28.01 28.01 0 00-1.175-1.629C10.413 4.932 8.812 4 6.896 4z\" fill=\"url(#lobe-icons-meta-0-_R_0_)\"></path><path d=\"M6.873 4C4.95 4.01 3.247 5.258 2.02 7.17a4.352 4.352 0 00-.01.017l2.254 1.231.011-.017c.718-1.083 1.61-1.774 2.568-1.785h.021L6.896 4h-.023z\" fill=\"url(#lobe-icons-meta-1-_R_0_)\"></path><path d=\"M2.019 7.17l-.011.017C1.2 8.447.598 9.995.274 11.664l-.005.022 2.534.6.004-.022c.27-1.467.786-2.828 1.456-3.845l.011-.017L2.02 7.17z\" fill=\"url(#lobe-icons-meta-2-_R_0_)\"></path><path d=\"M2.807 12.264l-2.533-.6-.005.022c-.177.918-.267 1.851-.269 2.786v.023l2.598.233v-.023a12.591 12.591 0 01.21-2.44z\" fill=\"url(#lobe-icons-meta-3-_R_0_)\"></path><path d=\"M2.677 15.537a5.462 5.462 0 01-.079-.813v-.022L0 14.468v.024a8.89 8.89 0 00.146 1.652l2.535-.585a4.106 4.106 0 01-.004-.022z\" fill=\"url(#lobe-icons-meta-4-_R_0_)\"></path><path d=\"M3.27 16.89c-.284-.31-.484-.756-.589-1.328l-.004-.021-2.535.585.004.021c.192 1.01.568 1.85 1.106 2.487l.014.017 2.018-1.745a2.106 2.106 0 01-.015-.016z\" fill=\"url(#lobe-icons-meta-5-_R_0_)\"></path><path d=\"M10.78 9.654c-1.528 2.35-2.454 3.825-2.454 3.825-2.035 3.2-2.739 3.917-3.871 3.917a1.545 1.545 0 01-1.186-.508l-2.017 1.744.014.017C2.01 19.518 3.058 20 4.356 20c1.963 0 3.374-.928 5.884-5.33l1.766-3.13a41.283 41.283 0 00-1.227-1.886z\" fill=\"#0082FB\"></path><path d=\"M13.502 5.946l-.016.016c-.4.43-.786.908-1.16 1.416.378.483.768 1.024 1.175 1.63.48-.743.928-1.345 1.367-1.807l.016-.016-1.382-1.24z\" fill=\"url(#lobe-icons-meta-6-_R_0_)\"></path><path d=\"M20.918 5.713C19.853 4.633 18.583 4 17.225 4c-1.432 0-2.637.787-3.723 1.944l-.016.016 1.382 1.24.016-.017c.715-.747 1.408-1.12 2.176-1.12.826 0 1.6.39 2.27 1.075l.015.016 1.589-1.425-.016-.016z\" fill=\"#0082FB\"></path><path d=\"M23.998 14.125c-.06-3.467-1.27-6.566-3.064-8.396l-.016-.016-1.588 1.424.015.016c1.35 1.392 2.277 3.98 2.361 6.971v.023h2.292v-.022z\" fill=\"url(#lobe-icons-meta-7-_R_0_)\"></path><path d=\"M23.998 14.15v-.023h-2.292v.022c.004.14.006.282.006.424 0 .815-.121 1.474-.368 1.95l-.011.022 1.708 1.782.013-.02c.62-.96.946-2.293.946-3.91 0-.083 0-.165-.002-.247z\" fill=\"url(#lobe-icons-meta-8-_R_0_)\"></path><path d=\"M21.344 16.52l-.011.02c-.214.402-.519.67-.917.787l.778 2.462a3.493 3.493 0 00.438-.182 3.558 3.558 0 001.366-1.218l.044-.065.012-.02-1.71-1.784z\" fill=\"url(#lobe-icons-meta-9-_R_0_)\"></path><path d=\"M19.92 17.393c-.262 0-.492-.039-.718-.14l-.798 2.522c.449.153.927.222 1.46.222.492 0 .943-.073 1.352-.215l-.78-2.462c-.167.05-.341.075-.517.073z\" fill=\"url(#lobe-icons-meta-10-_R_0_)\"></path><path d=\"M18.323 16.534l-.014-.017-1.836 1.914.016.017c.637.682 1.246 1.105 1.937 1.337l.797-2.52c-.291-.125-.573-.353-.9-.731z\" fill=\"url(#lobe-icons-meta-11-_R_0_)\"></path><path d=\"M18.309 16.515c-.55-.642-1.232-1.712-2.303-3.44l-1.396-2.336-.011-.02-1.62 2.438.012.02.989 1.668c.959 1.61 1.74 2.774 2.493 3.585l.016.016 1.834-1.914a2.353 2.353 0 01-.014-.017z\" fill=\"url(#lobe-icons-meta-12-_R_0_)\"></path><defs><linearGradient id=\"lobe-icons-meta-0-_R_0_\" x1=\"75.897%\" x2=\"26.312%\" y1=\"89.199%\" y2=\"12.194%\"><stop offset=\".06%\" stop-color=\"#0867DF\"></stop><stop offset=\"45.39%\" stop-color=\"#0668E1\"></stop><stop offset=\"85.91%\" stop-color=\"#0064E0\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-1-_R_0_\" x1=\"21.67%\" x2=\"97.068%\" y1=\"75.874%\" y2=\"23.985%\"><stop offset=\"13.23%\" stop-color=\"#0064DF\"></stop><stop offset=\"99.88%\" stop-color=\"#0064E0\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-2-_R_0_\" x1=\"38.263%\" x2=\"60.895%\" y1=\"89.127%\" y2=\"16.131%\"><stop offset=\"1.47%\" stop-color=\"#0072EC\"></stop><stop offset=\"68.81%\" stop-color=\"#0064DF\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-3-_R_0_\" x1=\"47.032%\" x2=\"52.15%\" y1=\"90.19%\" y2=\"15.745%\"><stop offset=\"7.31%\" stop-color=\"#007CF6\"></stop><stop offset=\"99.43%\" stop-color=\"#0072EC\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-4-_R_0_\" x1=\"52.155%\" x2=\"47.591%\" y1=\"58.301%\" y2=\"37.004%\"><stop offset=\"7.31%\" stop-color=\"#007FF9\"></stop><stop offset=\"100%\" stop-color=\"#007CF6\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-5-_R_0_\" x1=\"37.689%\" x2=\"61.961%\" y1=\"12.502%\" y2=\"63.624%\"><stop offset=\"7.31%\" stop-color=\"#007FF9\"></stop><stop offset=\"100%\" stop-color=\"#0082FB\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-6-_R_0_\" x1=\"34.808%\" x2=\"62.313%\" y1=\"68.859%\" y2=\"23.174%\"><stop offset=\"27.99%\" stop-color=\"#007FF8\"></stop><stop offset=\"91.41%\" stop-color=\"#0082FB\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-7-_R_0_\" x1=\"43.762%\" x2=\"57.602%\" y1=\"6.235%\" y2=\"98.514%\"><stop offset=\"0%\" stop-color=\"#0082FB\"></stop><stop offset=\"99.95%\" stop-color=\"#0081FA\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-8-_R_0_\" x1=\"60.055%\" x2=\"39.88%\" y1=\"4.661%\" y2=\"69.077%\"><stop offset=\"6.19%\" stop-color=\"#0081FA\"></stop><stop offset=\"100%\" stop-color=\"#0080F9\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-9-_R_0_\" x1=\"30.282%\" x2=\"61.081%\" y1=\"59.32%\" y2=\"33.244%\"><stop offset=\"0%\" stop-color=\"#027AF3\"></stop><stop offset=\"100%\" stop-color=\"#0080F9\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-10-_R_0_\" x1=\"20.433%\" x2=\"82.112%\" y1=\"50.001%\" y2=\"50.001%\"><stop offset=\"0%\" stop-color=\"#0377EF\"></stop><stop offset=\"99.94%\" stop-color=\"#0279F1\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-11-_R_0_\" x1=\"40.303%\" x2=\"72.394%\" y1=\"35.298%\" y2=\"57.811%\"><stop offset=\".19%\" stop-color=\"#0471E9\"></stop><stop offset=\"100%\" stop-color=\"#0377EF\"></stop></linearGradient><linearGradient id=\"lobe-icons-meta-12-_R_0_\" x1=\"32.254%\" x2=\"68.003%\" y1=\"19.719%\" y2=\"84.908%\"><stop offset=\"27.65%\" stop-color=\"#0867DF\"></stop><stop offset=\"100%\" stop-color=\"#0471E9\"></stop></linearGradient></defs></svg>" }],
  ["bedrock", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><defs><linearGradient id=\"lobe-icons-bedrock-_R_0_\" x1=\"80%\" x2=\"20%\" y1=\"20%\" y2=\"80%\"><stop offset=\"0%\" stop-color=\"#6350FB\"></stop><stop offset=\"50%\" stop-color=\"#3D8FFF\"></stop><stop offset=\"100%\" stop-color=\"#9AD8F8\"></stop></linearGradient></defs><path d=\"M13.05 15.513h3.08c.214 0 .389.177.389.394v1.82a1.704 1.704 0 011.296 1.661c0 .943-.755 1.708-1.685 1.708-.931 0-1.686-.765-1.686-1.708 0-.807.554-1.484 1.297-1.662v-1.425h-2.69v4.663a.395.395 0 01-.188.338l-2.69 1.641a.385.385 0 01-.405-.002l-4.926-3.086a.395.395 0 01-.185-.336V16.3L2.196 14.87A.395.395 0 012 14.555L2 14.528V9.406c0-.14.073-.27.192-.34l2.465-1.462V4.448c0-.129.062-.249.165-.322l.021-.014L9.77 1.058a.385.385 0 01.407 0l2.69 1.675a.395.395 0 01.185.336V7.6h3.856V5.683a1.704 1.704 0 01-1.296-1.662c0-.943.755-1.708 1.685-1.708.931 0 1.685.765 1.685 1.708 0 .807-.553 1.484-1.296 1.662v2.311a.391.391 0 01-.389.394h-4.245v1.806h6.624a1.69 1.69 0 011.64-1.313c.93 0 1.685.764 1.685 1.707 0 .943-.754 1.708-1.685 1.708a1.69 1.69 0 01-1.64-1.314H13.05v1.937h4.953l.915 1.18a1.66 1.66 0 01.84-.227c.931 0 1.685.764 1.685 1.707 0 .943-.754 1.708-1.685 1.708-.93 0-1.685-.765-1.685-1.708 0-.346.102-.668.276-.937l-.724-.935H13.05v1.806zM9.973 1.856L7.93 3.122V6.09h-.778V3.604L5.435 4.669v2.945l2.11 1.36L9.712 7.61V5.334h.778V7.83c0 .136-.07.263-.184.335L7.963 9.638v2.081l1.422 1.009-.446.646-1.406-.998-1.53 1.005-.423-.66 1.605-1.055v-1.99L5.038 8.29l-2.26 1.34v1.676l1.972-1.189.398.677-2.37 1.429V14.3l2.166 1.258 2.27-1.368.397.677-2.176 1.311V19.3l1.876 1.175 2.365-1.426.398.678-2.017 1.216 1.918 1.201 2.298-1.403v-5.78l-4.758 2.893-.4-.675 5.158-3.136V3.289L9.972 1.856zM16.13 18.47a.913.913 0 00-.908.92c0 .507.406.918.908.918a.913.913 0 00.907-.919.913.913 0 00-.907-.92zm3.63-3.81a.913.913 0 00-.908.92c0 .508.406.92.907.92a.913.913 0 00.908-.92.913.913 0 00-.908-.92zm1.555-4.99a.913.913 0 00-.908.92c0 .507.407.918.908.918a.913.913 0 00.907-.919.913.913 0 00-.907-.92zM17.296 3.1a.913.913 0 00-.907.92c0 .508.406.92.907.92a.913.913 0 00.908-.92.913.913 0 00-.908-.92z\" fill=\"url(#lobe-icons-bedrock-_R_0_)\" fill-rule=\"nonzero\"></path></svg>" }],
  ["vertex", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M11.995 20.216a1.892 1.892 0 100 3.785 1.892 1.892 0 000-3.785zm0 2.806a.927.927 0 11.927-.914.914.914 0 01-.927.914z\" fill=\"#4285F4\"></path><path clip-rule=\"evenodd\" d=\"M21.687 14.144c.237.038.452.16.605.344a.978.978 0 01-.18 1.3l-8.24 6.082a1.892 1.892 0 00-1.147-1.508l8.28-6.08a.991.991 0 01.682-.138z\" fill=\"#669DF6\" fill-rule=\"evenodd\"></path><path clip-rule=\"evenodd\" d=\"M10.122 21.842l-8.217-6.066a.952.952 0 01-.206-1.287.978.978 0 011.287-.206l8.28 6.08a1.893 1.893 0 00-1.144 1.479z\" fill=\"#AECBFA\" fill-rule=\"evenodd\"></path><path d=\"M4.273 4.475a.978.978 0 01-.965-.965V1.09a.978.978 0 111.943 0v2.42a.978.978 0 01-.978.965zM4.247 13.034a.978.978 0 100-1.956.978.978 0 000 1.956zM4.247 10.19a.978.978 0 100-1.956.978.978 0 000 1.956zM4.247 7.332a.978.978 0 100-1.956.978.978 0 000 1.956z\" fill=\"#AECBFA\"></path><path d=\"M19.718 7.307a.978.978 0 01-.965-.979v-2.42a.965.965 0 011.93 0v2.42a.964.964 0 01-.965.979zM19.743 13.047a.978.978 0 100-1.956.978.978 0 000 1.956zM19.743 10.151a.978.978 0 100-1.956.978.978 0 000 1.956zM19.743 2.068a.978.978 0 100-1.956.978.978 0 000 1.956z\" fill=\"#4285F4\"></path><path d=\"M11.995 15.917a.978.978 0 01-.965-.965v-2.459a.978.978 0 011.943 0v2.433a.976.976 0 01-.978.991zM11.995 18.762a.978.978 0 100-1.956.978.978 0 000 1.956zM11.995 10.64a.978.978 0 100-1.956.978.978 0 000 1.956zM11.995 7.783a.978.978 0 100-1.956.978.978 0 000 1.956z\" fill=\"#669DF6\"></path><path d=\"M15.856 10.177a.978.978 0 01-.965-.965v-2.42a.977.977 0 011.702-.763.979.979 0 01.241.763v2.42a.978.978 0 01-.978.965zM15.869 4.913a.978.978 0 100-1.956.978.978 0 000 1.956zM15.869 15.853a.978.978 0 100-1.956.978.978 0 000 1.956zM15.869 12.996a.978.978 0 100-1.956.978.978 0 000 1.956z\" fill=\"#4285F4\"></path><path d=\"M8.121 15.853a.978.978 0 100-1.956.978.978 0 000 1.956zM8.121 7.783a.978.978 0 100-1.956.978.978 0 000 1.956zM8.121 4.913a.978.978 0 100-1.957.978.978 0 000 1.957zM8.134 12.996a.978.978 0 01-.978-.94V9.611a.965.965 0 011.93 0v2.445a.966.966 0 01-.952.94z\" fill=\"#AECBFA\"></path></svg>" }],
  ["fireworks(?:-ai)?|fw", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path clip-rule=\"evenodd\" d=\"M14.8 5l-2.801 6.795L9.195 5H7.397l3.072 7.428a1.64 1.64 0 003.038.002L16.598 5H14.8zm1.196 10.352l5.124-5.244-.699-1.669-5.596 5.739a1.664 1.664 0 00-.343 1.807 1.642 1.642 0 001.516 1.012L16 17l8-.02-.699-1.669-7.303.041h-.002zM2.88 10.104l.699-1.669 5.596 5.739c.468.479.603 1.189.343 1.807a1.643 1.643 0 01-1.516 1.012l-8-.018-.002.002.699-1.669 7.303.042-5.122-5.246z\" fill=\"#5019C5\" fill-rule=\"evenodd\"></path></svg>" }],
  ["deep-?infra(?:-ai)?", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M3.294 7.821A2.297 2.297 0 011 5.527a2.297 2.297 0 012.294-2.295A2.297 2.297 0 015.59 5.527 2.297 2.297 0 013.294 7.82zm0-3.688a1.396 1.396 0 000 2.79 1.396 1.396 0 000-2.79zM3.294 14.293A2.297 2.297 0 011 11.998a2.297 2.297 0 012.294-2.294 2.297 2.297 0 012.295 2.294 2.297 2.297 0 01-2.295 2.295zm0-3.688a1.395 1.395 0 000 2.788 1.395 1.395 0 100-2.788zM3.294 20.761A2.297 2.297 0 011 18.467a2.297 2.297 0 012.294-2.295 2.297 2.297 0 012.295 2.295 2.297 2.297 0 01-2.295 2.294zm0-3.688a1.396 1.396 0 000 2.79 1.396 1.396 0 000-2.79zM20.738 7.821a2.297 2.297 0 01-2.295-2.294 2.297 2.297 0 012.294-2.295 2.297 2.297 0 012.295 2.295 2.297 2.297 0 01-2.294 2.294zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.626-1.395-1.395-1.395zM20.738 14.293a2.297 2.297 0 01-2.295-2.295 2.297 2.297 0 012.294-2.294 2.297 2.297 0 012.295 2.294 2.297 2.297 0 01-2.294 2.295zm0-3.688c-.769 0-1.395.625-1.395 1.393a1.396 1.396 0 002.79 0c0-.77-.626-1.393-1.395-1.393zM20.738 20.761a2.297 2.297 0 01-2.295-2.294 2.297 2.297 0 012.294-2.295 2.297 2.297 0 012.295 2.295 2.297 2.297 0 01-2.294 2.294zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.626-1.395-1.395-1.395zM12.016 11.057a2.297 2.297 0 01-2.294-2.294 2.297 2.297 0 012.294-2.295 2.297 2.297 0 012.295 2.295 2.297 2.297 0 01-2.295 2.294zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.625-1.395-1.395-1.395zM12.017 4.589a2.297 2.297 0 01-2.295-2.295A2.297 2.297 0 0112.017 0a2.297 2.297 0 012.294 2.294 2.297 2.297 0 01-2.294 2.295zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.626-1.395-1.395-1.395zM12.017 17.529a2.297 2.297 0 01-2.295-2.295 2.297 2.297 0 012.295-2.294 2.297 2.297 0 012.294 2.294 2.297 2.297 0 01-2.294 2.295zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.626-1.395-1.395-1.395zM12.016 24a2.297 2.297 0 01-2.294-2.295 2.297 2.297 0 012.294-2.294 2.297 2.297 0 012.295 2.294A2.297 2.297 0 0112.016 24zm0-3.688a1.396 1.396 0 101.395 1.395c0-.77-.625-1.395-1.395-1.395z\" fill=\"#2A3275\"></path><path d=\"M8.363 8.222a.742.742 0 01-.277-.053l-1.494-.596a.75.75 0 11.557-1.392l1.493.595a.75.75 0 01-.278 1.446h-.001zM8.363 14.566a.743.743 0 01-.277-.053l-1.494-.595a.75.75 0 11.557-1.393l1.493.596a.75.75 0 01-.278 1.445h-.001zM17.124 11.397a.741.741 0 01-.277-.054l-1.493-.595a.75.75 0 11.555-1.392l1.493.595a.75.75 0 01-.278 1.446zM17.124 5.05a.744.744 0 01-.277-.054L15.354 4.4a.75.75 0 01.555-1.392l1.493.596a.75.75 0 01-.278 1.445zM17.124 17.739a.743.743 0 01-.277-.053l-1.494-.596a.75.75 0 11.556-1.392l1.493.596a.75.75 0 01-.278 1.445zM6.91 17.966a.75.75 0 01-.279-1.445l1.494-.595a.749.749 0 11.556 1.392l-1.493.595a.743.743 0 01-.277.053H6.91zM6.91 11.66a.75.75 0 01-.279-1.446l1.494-.595a.75.75 0 01.556 1.392l-1.493.595a.743.743 0 01-.277.053H6.91zM6.91 5.033a.75.75 0 01-.279-1.446l1.494-.595a.75.75 0 01.556 1.392l-1.493.596a.744.744 0 01-.277.053H6.91zM8.363 21.364a.743.743 0 01-.277-.053l-1.494-.596a.75.75 0 01.555-1.392l1.494.595a.75.75 0 01-.278 1.446zM15.63 8.223a.75.75 0 01-.278-1.447l1.494-.595a.75.75 0 01.556 1.393l-1.494.595a.744.744 0 01-.276.054h-.002zM15.63 14.567a.75.75 0 01-.278-1.446l1.494-.596a.75.75 0 01.556 1.394l-1.494.595a.743.743 0 01-.276.053h-.002zM15.63 21.363a.749.749 0 01-.278-1.445l1.494-.595a.75.75 0 11.555 1.392l-1.494.595a.741.741 0 01-.277.053z\" fill=\"#5699DB\"></path></svg>" }],
  ["novita(?:-?ai)?", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path clip-rule=\"evenodd\" d=\"M9.167 4.17v5.665L0 19.003h9.167v-5.666l5.666 5.666H24L9.167 4.17z\" fill=\"#23D57C\" fill-rule=\"evenodd\"></path></svg>" }],
  ["azure-foundry", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path clip-rule=\"evenodd\" d=\"M16.233 0c.713 0 1.345.551 1.572 1.329.227.778 1.555 5.59 1.555 5.59v9.562h-4.813L14.645 0h1.588z\" fill=\"url(#lobe-icons-azure-ai-0-_R_0_)\" fill-rule=\"evenodd\"></path><path d=\"M23.298 7.47c0-.34-.275-.6-.6-.6h-2.835a3.617 3.617 0 00-3.614 3.615v5.996h3.436a3.617 3.617 0 003.613-3.614V7.47z\" fill=\"url(#lobe-icons-azure-ai-1-_R_0_)\"></path><path clip-rule=\"evenodd\" d=\"M16.233 0a.982.982 0 00-.989.989l-.097 18.198A4.814 4.814 0 0110.334 24H1.6a.597.597 0 01-.567-.794l7-19.981A4.819 4.819 0 0112.57 0h3.679-.016z\" fill=\"url(#lobe-icons-azure-ai-2-_R_0_)\" fill-rule=\"evenodd\"></path><defs><linearGradient gradientUnits=\"userSpaceOnUse\" id=\"lobe-icons-azure-ai-0-_R_0_\" x1=\"18.242\" x2=\"14.191\" y1=\"16.837\" y2=\".616\"><stop stop-color=\"#712575\"></stop><stop offset=\".09\" stop-color=\"#9A2884\"></stop><stop offset=\".18\" stop-color=\"#BF2C92\"></stop><stop offset=\".27\" stop-color=\"#DA2E9C\"></stop><stop offset=\".34\" stop-color=\"#EB30A2\"></stop><stop offset=\".4\" stop-color=\"#F131A5\"></stop><stop offset=\".5\" stop-color=\"#EC30A3\"></stop><stop offset=\".61\" stop-color=\"#DF2F9E\"></stop><stop offset=\".72\" stop-color=\"#C92D96\"></stop><stop offset=\".83\" stop-color=\"#AA2A8A\"></stop><stop offset=\".95\" stop-color=\"#83267C\"></stop><stop offset=\"1\" stop-color=\"#712575\"></stop></linearGradient><linearGradient gradientUnits=\"userSpaceOnUse\" id=\"lobe-icons-azure-ai-1-_R_0_\" x1=\"19.782\" x2=\"19.782\" y1=\".34\" y2=\"23.222\"><stop stop-color=\"#DA7ED0\"></stop><stop offset=\".08\" stop-color=\"#B17BD5\"></stop><stop offset=\".19\" stop-color=\"#8778DB\"></stop><stop offset=\".3\" stop-color=\"#6276E1\"></stop><stop offset=\".41\" stop-color=\"#4574E5\"></stop><stop offset=\".54\" stop-color=\"#2E72E8\"></stop><stop offset=\".67\" stop-color=\"#1D71EB\"></stop><stop offset=\".81\" stop-color=\"#1471EC\"></stop><stop offset=\"1\" stop-color=\"#1171ED\"></stop></linearGradient><linearGradient gradientUnits=\"userSpaceOnUse\" id=\"lobe-icons-azure-ai-2-_R_0_\" x1=\"18.404\" x2=\"3.236\" y1=\".859\" y2=\"25.183\"><stop stop-color=\"#DA7ED0\"></stop><stop offset=\".05\" stop-color=\"#B77BD4\"></stop><stop offset=\".11\" stop-color=\"#9079DA\"></stop><stop offset=\".18\" stop-color=\"#6E77DF\"></stop><stop offset=\".25\" stop-color=\"#5175E3\"></stop><stop offset=\".33\" stop-color=\"#3973E7\"></stop><stop offset=\".42\" stop-color=\"#2772E9\"></stop><stop offset=\".54\" stop-color=\"#1A71EB\"></stop><stop offset=\".68\" stop-color=\"#1371EC\"></stop><stop offset=\"1\" stop-color=\"#1171ED\"></stop></linearGradient></defs></svg>" }],
  ["nebius(?:-.+)?", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M20 2.306v16.797s4-.242 4-4.815V2.306h-4zM4 22.001V5.204s-4 .242-4 4.816V22h4z\"></path><path d=\"M16.318 16.51L11.286 4.94c-.824-1.872-2.168-2.926-4.077-2.926-1.908 0-3.211 1.54-3.211 3.19 0 0 2.405-.333 3.68 2.593l5.036 11.57c.821 1.87 2.168 2.926 4.075 2.926 1.905 0 3.211-1.541 3.211-3.19 0 0-2.406.333-3.682-2.594z\"></path>" }],
  ["upstage|solar", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M19.763 0l-.373 1.297h2.594L22.354 0h-2.591zM16.192 2.27l-.376 1.298h5.52l.37-1.298h-5.514zM12.897 4.54l-.376 1.298h8.166l.37-1.298h-8.16zM2.85 6.81l-.377 1.298h17.565l.37-1.297H2.848zM3.884 9.081l-.376 1.297H19.39l.37-1.297H3.882zM4.088 24l.376-1.297H1.866L1.5 24h2.588zM7.662 21.73l.376-1.297H2.515L2.15 21.73h5.513zM10.957 19.459l.376-1.297h-8.17l-.366 1.297h8.16zM21.005 17.189l.376-1.297H3.812l-.366 1.297h17.559zM19.967 14.919l.376-1.297H4.461l-.366 1.297h15.872zM18.786 12.649l.376-1.297H4.26l-.366 1.297h14.893z\" fill=\"url(#lobe-icons-upsate-_R_0_)\"></path><defs><linearGradient gradientUnits=\"userSpaceOnUse\" id=\"lobe-icons-upsate-_R_0_\" x1=\"11.927\" x2=\"11.927\" y2=\"24\"><stop offset=\"0\" stop-color=\"#AEBCFE\"></stop><stop offset=\"1\" stop-color=\"#805DFA\"></stop></linearGradient></defs></svg>" }],
  ["stepfun", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M22.012 0h1.032v.927H24v.968h-.956V3.78h-1.032V1.896h-1.878v-.97h1.878V0zM2.6 12.371V1.87h.969v10.502h-.97zm10.423.66h10.95v.918h-6.208v9.579h-4.742V13.03zM5.629 3.333v12.356H0v4.51h10.386V8L20.859 8l-.003-4.668-15.227.001z\" fill=\"url(#lobe-icons-stepfun-_R_0_)\" fill-rule=\"evenodd\"></path><defs><linearGradient gradientUnits=\"userSpaceOnUse\" id=\"lobe-icons-stepfun-_R_0_\" x1=\"1.646\" x2=\"18.342\" y1=\"1.916\" y2=\"22.091\"><stop stop-color=\"#01A9FF\"></stop><stop offset=\"1\" stop-color=\"#0160FF\"></stop></linearGradient></defs></svg>" }],
  ["xiaomi", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M.958 15.936a.459.459 0 01.459.44v2.729a.46.46 0 01-.918 0v-2.729a.459.459 0 01.459-.44zm4.814-2.035a.46.46 0 01.553.45v4.754a.458.458 0 11-.918 0V15.48L3.74 17.202a.462.462 0 01-.655.016.462.462 0 01-.065-.082L.628 14.67a.459.459 0 01.658-.637l2.124 2.187 2.127-2.188a.46.46 0 01.235-.13zm2.068.004a.46.46 0 01.458.445v4.755a.46.46 0 01-.458.458.459.459 0 01-.458-.458V14.35a.459.459 0 01.458-.445zm1.973 2.014a.46.46 0 01.46.457v2.729a.46.46 0 01-.784.324.46.46 0 01-.134-.324v-2.729a.46.46 0 01.458-.458zm.002-2.045a.458.458 0 01.328.157l2.127 2.19 2.125-2.19a.459.459 0 01.784.318v4.756a.46.46 0 01-.455.458.46.46 0 01-.458-.458V15.48l-1.667 1.723a.46.46 0 01-.65.008l-.005-.005c0-.002-.002-.002-.004-.003l-2.455-2.534a.46.46 0 01-.008-.667.461.461 0 01.338-.128zm6.797 1.206a.46.46 0 01.53.651A1.966 1.966 0 0019.81 18.4a.462.462 0 01.623.18.46.46 0 01-.181.624 2.863 2.863 0 01-1.38.353l-.142-.004a2.88 2.88 0 01-2.393-4.263.461.461 0 01.274-.21zm.864-.931a2.884 2.884 0 013.915 3.914.46.46 0 01-.402.24l-.057-.004a.458.458 0 01-.164-.055.46.46 0 01-.182-.622 1.967 1.967 0 00-2.669-2.67.459.459 0 11-.441-.803zM9.59 6.368c1.481 0 1.696 1.202 1.696 1.654v2.648h-.917v-.432c-.26.346-.792.535-1.36.535-.133 0-1.289-.03-1.384-1.136-.082-.932.675-1.61 2.053-1.61h.691c0-.563-.367-.886-.983-.886-.44.013-.864.174-1.2.458l-.36-.664c.484-.379 1.012-.567 1.764-.567zm4.427.1c1.263 0 2.082.97 2.083 2.15 0 1.181-.824 2.154-2.083 2.154-1.26 0-2.084-.972-2.084-2.152 0-1.18.82-2.153 2.084-2.153zm6.801.015c.68 0 1.202.465 1.197 1.548v2.642H21.1V8.29c0-.312-.002-.98-.63-.98s-.628.667-.628.838v2.524h-.89V8.148c0-.17-.001-.838-.63-.838-.628 0-.628.668-.628.98v2.383h-.917v-4.03h.917V7a1.22 1.22 0 01.947-.516c.398 0 .76.193.982.686a1.321 1.321 0 011.195-.686zm-18.093.872l1.457-1.772H5.32L3.311 8.07l2.14 2.602H4.24L2.725 8.796 1.21 10.672H0L2.138 8.07.13 5.583h1.138l1.458 1.772zm4.149 3.317h-.916V6.644h.916v4.028zm16.99 0h-.916V6.644h.916v4.028zM9.925 8.71c-1.055 0-1.359.412-1.326.742.032.329.324.537.757.537a1.013 1.013 0 001.014-.968l.002-.31h-.447zM14.018 7.3c-.663 0-1.184.487-1.184 1.32 0 .832.52 1.32 1.184 1.32.662 0 1.182-.49 1.182-1.32 0-.832-.52-1.32-1.182-1.32zM6.417 5.001a.568.568 0 01.587.582.588.588 0 01-1.175 0A.57.57 0 016.417 5zm16.991 0a.57.57 0 01.592.582.588.588 0 01-1.174 0 .57.57 0 01.357-.542.572.572 0 01.225-.04z\"></path>" }],
  ["lmstudio", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M2.84 2a1.273 1.273 0 100 2.547h14.107a1.273 1.273 0 100-2.547H2.84zM7.935 5.33a1.273 1.273 0 000 2.548H22.04a1.274 1.274 0 000-2.547H7.935zM3.624 9.935c0-.704.57-1.274 1.274-1.274h14.106a1.274 1.274 0 010 2.547H4.898c-.703 0-1.274-.57-1.274-1.273zM1.273 12.188a1.273 1.273 0 100 2.547H15.38a1.274 1.274 0 000-2.547H1.273zM3.624 16.792c0-.704.57-1.274 1.274-1.274h14.106a1.273 1.273 0 110 2.547H4.898c-.703 0-1.274-.57-1.274-1.273zM13.029 18.849a1.273 1.273 0 100 2.547h9.698a1.273 1.273 0 100-2.547h-9.698z\" fill-opacity=\".3\"></path><path d=\"M2.84 2a1.273 1.273 0 100 2.547h10.287a1.274 1.274 0 000-2.547H2.84zM7.935 5.33a1.273 1.273 0 000 2.548H18.22a1.274 1.274 0 000-2.547H7.935zM3.624 9.935c0-.704.57-1.274 1.274-1.274h10.286a1.273 1.273 0 010 2.547H4.898c-.703 0-1.274-.57-1.274-1.273zM1.273 12.188a1.273 1.273 0 100 2.547H11.56a1.274 1.274 0 000-2.547H1.273zM3.624 16.792c0-.704.57-1.274 1.274-1.274h10.286a1.273 1.273 0 110 2.547H4.898c-.703 0-1.274-.57-1.274-1.273zM13.029 18.849a1.273 1.273 0 100 2.547h5.78a1.273 1.273 0 100-2.547h-5.78z\"></path>" }],
  ["kilocode", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M0 0v24h24V0H0zm22.222 22.222H1.778V1.778h20.444v20.444zm-7.555-4.964h2.222v1.778h-2.794L12.89 17.83v-2.794h1.778v2.222zm4 0h-1.778v-2.222h-2.222v-1.778h2.793l1.207 1.207v2.793zm-7.556-2.591H9.333v-1.778h1.778v1.778zm-5.778-1.778h1.778v4h4v1.778H6.54L5.333 17.46V12.89zm13.334-3.556v1.778h-5.778V9.333h1.987V7.111h-1.987V5.333h2.558l1.206 1.207v2.793h2.014zm-11.556-2h2.222l1.778 1.778v2H9.333v-2H7.111v2H5.333V5.333h1.778v2zm4 0H9.333v-2h1.778v2z\"></path>" }],
  ["ai-gateway", { viewBox: "0 0 24 24", attrs: " fill-rule=\"evenodd\"", body: "<path d=\"M12 0l12 20.785H0L12 0z\"></path>" }],
  ["arcee", { svg: "<svg viewBox=\"0 0 24 24\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M13.236 2.377L2.751 20.493H0L11.863 0l1.373 2.377zm3.554 6.156l-9.606 11.96H4.13L15.511 6.32l1.279 2.212zm6.908 11.96H14.05l8.406-2.151 1.242 2.15zm-3.42-5.922l-7.843 5.92H8.482l10.597-7.997 1.2 2.077z\" fill=\"#008C8C\"></path></svg>" }],
].map(([pattern, icon]) => [new RegExp("^(?:" + pattern + ")$"), icon])
function providerBrand(slug) {
  return /^(openai|openai-codex|openai-api)$/.test(slug) ? 'openai' : /^(anthropic|claude)(?:-|$)/.test(slug) ? 'anthropic' : null
}
// { svg, colored }: colored marks paint as images, the rest as masks on currentColor.
function providerSvg(slug, fill = 'black') {
  if (/^(gemini|google|google-ai-studio)$/.test(slug)) return { svg: geminiProviderSvg, colored: true }
  if (/^opencode(?:-|$)/.test(slug)) return { svg: opencodeProviderSvg, colored: true }
  if (slug === 'openrouter') return { svg: openrouterProviderSvg.replace('<svg ', `<svg fill="${fill}" `), colored: false }
  const icon = providerIconPaths[providerBrand(slug)]
  if (icon) return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${icon.viewBox}" fill="${fill}"><path d="${icon.path}"/></svg>`, colored: false }
  const extra = extraProviderIcons.find(([pattern]) => pattern.test(slug))?.[1]
  if (extra?.svg) return { svg: extra.svg, colored: true }
  if (extra) return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${extra.viewBox}" fill="${fill}"${extra.attrs}>${extra.body}</svg>`, colored: false }
  const safeLetter = (slug.match(/[a-z0-9]/i)?.[0] || '?').toUpperCase()
  return { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="1" y="1" width="22" height="22" rx="6" fill="none" stroke="${fill}" stroke-width="1.5"/><text x="12" y="17" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" font-weight="600" fill="${fill}">${safeLetter}</text></svg>`, colored: false }
}
const svgUrl = svg => `url("data:image/svg+xml,${encodeURIComponent(svg)}")`

// Pre-colored because a pseudo-element background cannot be masked separately.
function rowIconUrl(slug) {
  return svgUrl(providerSvg(slug, providerBrand(slug) === 'anthropic' ? '#d97757' : '#9a9a9a').svg)
}

// T3's getDisplayModelName: vendor-prefixed, title-cased, no effort/context tags.
function t3ModelLabel(model) {
  const { name, tag } = nativeModelParts(model)
  const base = model.trim().split('/').pop()
  const title = s => s.replace(/(^|[\s-])([a-z])/g, (m, sep, c) => sep + c.toUpperCase())
  const label = /^claude-/i.test(base) ? 'Claude ' + name : /^(gpt|gemini)-/i.test(base) ? title(name) : name
  const variant = tag.match(/\b(Fast|Flash)\b/)?.[1]
  return variant ? label + ' ' + variant : label
}

// The painted theme (it follows a preview too) is named "<skin>-<mode>".
const useT3 = sdk => /^t3-code-theme-(dark|light)$/.test(sdk.useTheme().theme?.name)

// T3 model names on the composer pill ("Claude Opus 5.5"), through the SDK's
// label provider. The host memoizes labels on registry changes, so the provider
// is registered only while this theme is painted. A contribution in the
// composer's top slot (mounted wherever a pill is) follows the theme through
// useTheme and renders nothing.
function installModelLabel(ctx, sdk) {
  const areas = sdk?.COMPOSER_AREAS
  if (!sdk?.useTheme || !areas?.top || !areas.modelPill) return
  let unregister = null, disposed = false
  const set = active => {
    if (disposed || active === !!unregister) return
    if (unregister) { unregister(); unregister = null; return }
    unregister = ctx.register({ id: 'model-pill-label', area: areas.modelPill, data: {
      label: ({ model }) => model?.trim() ? t3ModelLabel(model) : null
    } })
  }
  ctx.onDispose(() => { disposed = true })
  function ThemeWatch() {
    const active = useT3(sdk)
    useEffect(() => set(active), [active])
    return null
  }
  ctx.register({ id: 'theme-watch', area: areas.top, render: () => jsx(ThemeWatch, {}) })
}

// Sidebar rows, T3's thread card. One read of the persisted list feeds every
// row: a project badge in the header, and a footer with the branch, the
// machine glyph and the provider icon. Machine glyph follows T3's rule: this
// machine needs no marker, every other one gets its glyph. In the all-profiles
// list Duckwork tags rows served by another connected gateway with
// connection_id; untagged rows are local. Rows not in the last read (new
// chats) fall back to the active connection.
// The list is only read while this theme is painted and a row is on screen;
// under any other theme the rows render nothing and request nothing.
const ROW_CARD_REFRESH_MS = 30_000
const ROW_CARD_MISS_REFRESH_MS = 5_000
function installRowCard(ctx, sdk) {
  const host = sdk?.host
  if (!host?.listPersistedSessions || !host.state?.connectionId || !sdk.atom || !sdk.useValue || !sdk.useTheme || !sdk.SESSION_ROW_AREAS) return
  const $rows = sdk.atom(new Map()), $connections = sdk.atom([])
  // An unlisted row (a chat not saved yet, or one past the list limit) gets one
  // early re-read, then waits for the regular refresh like every other row.
  const missed = new Set()
  let loading = false, loadedAt = 0, loadedFor
  const load = (connection, maxAge) => {
    if (loading || (connection === loadedFor && Date.now() - loadedAt < maxAge)) return
    loading = true; loadedFor = connection
    Promise.all([host.listPersistedSessions(null, { profile: 'all', limit: 500 }), host.connections?.() ?? []])
      .then(([page, connections]) => {
        const rows = new Map()
        for (const row of page?.sessions || []) {
          const root = (row.git_repo_root || '').replace(/\/+$/, '')
          const info = {
            owner: row.connection_id || 'local',
            project: root ? root.split('/').pop() : '',
            branch: (row.git_branch || '').trim(),
            provider: row.billing_provider || ''
          }
          for (const id of [row.id, row._lineage_root_id]) if (id) rows.set(id, info)
        }
        $rows.set(rows)
        $connections.set(Array.isArray(connections) ? connections : [])
      }, () => {})
      .finally(() => { loading = false; loadedAt = Date.now() })
  }
  const useRow = sessionId => {
    const active = useT3(sdk), info = sdk.useValue($rows).get(sessionId), connection = sdk.useValue(host.state.connectionId)
    useEffect(() => {
      if (!active) return
      const retry = !info && !missed.has(sessionId)
      if (retry) missed.add(sessionId)
      load(connection, retry ? ROW_CARD_MISS_REFRESH_MS : ROW_CARD_REFRESH_MS)
    })
    return { active, info, connection }
  }
  function RowBadge({ sessionId }) {
    const { active, info } = useRow(sessionId)
    if (!active || !info) return null
    if (!info.project) return jsx('span', { 'data-t3-row-badge': 'home', 'aria-hidden': 'true' })
    return jsx('span', { 'data-t3-row-badge': '', 'aria-hidden': 'true', children: info.project.replace(/[^a-z0-9]/gi, '').slice(0, 2).toUpperCase() })
  }
  function RowFoot({ sessionId }) {
    const { active, info, connection: current } = useRow(sessionId), connections = sdk.useValue($connections)
    if (!active) return null
    const owner = info?.owner || current || 'local'
    const connection = connections.find(c => c.id === owner)
    const remote = owner !== 'local' && connection?.kind !== 'local'
    const label = connection?.label || owner
    return jsx('span', { 'data-t3-row-foot': '', children: [
      jsx('span', { 'data-t3-row-branch': '', children: info?.branch || '' }, 'branch'),
      remote ? jsx('span', { 'data-t3-row-machine': '', title: `Running on ${label}`, 'aria-label': `Running on ${label}`, role: 'img' }, 'machine') : null,
      info?.provider ? jsx('span', { 'data-t3-row-provider': info.provider, 'aria-hidden': 'true', style: { backgroundImage: rowIconUrl(info.provider) } }, 'provider') : null
    ] })
  }
  ctx.register({ id: 'row-badge', area: sdk.SESSION_ROW_AREAS.leading, data: { render: ({ sessionId }) => jsx(RowBadge, { sessionId }) } })
  ctx.register({ id: 'row-foot', area: sdk.SESSION_ROW_AREAS.trailing, data: { render: ({ sessionId }) => jsx(RowFoot, { sessionId }) } })
}

// Empty chat headline. No project name: the SDK exposes only the primary chat's
// cwd, and a tile may belong to another project.
function EmptyHero() {
  return useT3(sdk) ? jsx('h1', { 'data-t3-empty-hero': '', children: 'What should we build?' }) : null
}

export default {
  id: 't3-code-theme',
  name: 'T3 Code dark theme',
  register(ctx) {
    ctx.register({ id: 'theme', area: THEMES_AREA, data: {
      name: 't3-code-theme', label: 'T3 Code',
      description: 'Unofficial port of the standard T3 Code dark theme, based on its MIT source.',
      colors, darkColors: colors, typography, customCSS: css + composerCss + rowCardCss
    } })
    installModelLabel(ctx, sdk)
    installRowCard(ctx, sdk)
    if (sdk.useTheme) ctx.register({ id: 'empty-hero', area: CHAT_EMPTY_AREA, data: { render: () => jsx(EmptyHero, {}) } })
    // One-time activation only; don't override later user theme choices.
    // No restore on dispose: it also runs on hot reload, and Duckwork already
    // falls back to its default skin when this theme is unregistered.
    if (!ctx.storage.get('installed', false)) {
      if (requestTheme('t3-code-theme')) ctx.storage.set('installed', true)
    }
  }
}
