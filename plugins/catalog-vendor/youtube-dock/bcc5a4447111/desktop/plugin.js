import {
  Button, Codicon, MessageTextContent, PALETTE_AREA, Popover,
  PopoverContent, PopoverTrigger, TITLEBAR_AREAS, atom, usePluginI18n, useValue
} from '@duckwork/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

export const VERSION = '1.1.0'
const ID = 'youtube-dock'
const menuOpen = atom(false)

export const DESTINATIONS = Object.freeze([
  Object.freeze({ id: 'home', url: 'https://www.youtube.com/', icon: 'home' }),
  Object.freeze({ id: 'shorts', url: 'https://www.youtube.com/shorts/', icon: 'device-mobile' })
])

// The public message renderer owns #preview links. Unlike ordinary web links,
// these always use the native internal Browser, even with external links enabled.
// No guest injection, raw webview, cookie access, or private Electron bridge.
export function previewMarkdown(url) {
  if (!DESTINATIONS.some(destination => destination.url === url)) {
    throw new Error('Unsupported YouTube destination')
  }
  // "Preview:" labels are agent hand-off markers stripped from prose. An
  // ordinary label keeps the user-facing canonical preview control visible.
  return `[YouTube](#preview/${encodeURIComponent(url)})`
}

const bundles = {
  en: {
    title: 'YouTube',
    help: 'Help',
    menu: 'YouTube — recommendations and Shorts',
    subtitle: 'Your YouTube, inside Duckwork',
    home: 'Recommended videos',
    homeDescription: 'Browse your signed-in Home feed.',
    shorts: 'Shorts',
    shortsDescription: 'Open the vertical Shorts feed.',
    hint: 'Open preview opens YouTube in Duckwork. Pin to workspace is a manual tab-menu action. An already-open destination shows Hide.',
    layout: 'Resize or drag the Browser tab beside your conversation. Its tab menu can pin the page across chats or open a separate Duckwork window.',
    privacy: 'Playback uses the existing internal Browser and its saved login. This plugin does not read cookies, watch history, or recommendations.',
    pip: 'This version uses the docked Browser. A dedicated picture-in-picture button is not included.',
    palette: 'YouTube: recommendations and Shorts'
  },
  ko: {
    title: 'YouTube',
    help: '도움말',
    menu: 'YouTube — 추천 피드와 쇼츠',
    subtitle: '내 유튜브를 Duckwork 안에서',
    home: '추천 피드',
    homeDescription: '로그인한 내 계정의 홈 추천 영상을 봅니다.',
    shorts: '쇼츠',
    shortsDescription: '세로형 쇼츠 피드를 열고 넘겨봅니다.',
    hint: 'Open preview를 누르면 Duckwork 내부 브라우저로 바로 열립니다. 고정은 탭 메뉴의 Pin to workspace에서 직접 하세요. 이미 열린 대상은 Hide로 표시됩니다.',
    layout: 'Browser 탭을 대화 옆으로 드래그하거나 경계를 움직여 크기를 조절하세요. 탭 메뉴에서 다른 대화에도 고정하거나 별도 Duckwork 창으로 분리할 수 있습니다.',
    privacy: '기존 내부 브라우저의 로그인 상태를 사용합니다. 플러그인은 쿠키·시청 기록·추천 목록을 읽지 않습니다.',
    pip: '이 버전은 내부 브라우저 도킹 방식입니다. 별도의 PIP 버튼은 포함하지 않습니다.',
    palette: 'YouTube: 추천 피드와 쇼츠'
  }
}

export function Destination({ destination, t }) {
  return jsxs('section', {
    'aria-label': t(destination.id),
    style: { minWidth: 0 },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 },
        children: [jsx(Codicon, { name: destination.icon, size: '1rem' }),
          jsx('h3', { style: { fontSize: 13, fontWeight: 600, margin: 0 }, children: t(destination.id) })]
      }),
      jsx('p', {
        style: { margin: '0 0 6px', fontSize: 12, color: 'var(--ui-text-tertiary)' },
        children: t(`${destination.id}Description`)
      }),
      jsx('div', {
        // Hide the unrelated download control only inside our own preview cards.
        // Never select or modify other app surfaces.
        className: 'youtube-dock-destination',
        children: jsxs('div', { children: [
          jsx('style', { children: '.youtube-dock-destination button[aria-label]{display:none}' }),
          jsx(MessageTextContent, { media: false, text: previewMarkdown(destination.url) })
        ] })
      })
    ]
  })
}

export function YouTubeMenu() {
  const t = usePluginI18n(ID)
  const open = useValue(menuOpen)
  return jsxs(Popover, {
    open,
    onOpenChange: value => menuOpen.set(value),
    children: [
      jsx(PopoverTrigger, {
        asChild: true,
        children: jsxs(Button, {
          type: 'button', variant: 'ghost', size: 'sm',
          'aria-label': t('menu'), title: t('menu'),
          style: { WebkitAppRegion: 'no-drag', gap: 6 },
          children: [jsx(Codicon, { name: 'play', size: '1rem' }), 'YouTube']
        })
      }),
      jsxs(PopoverContent, {
        align: 'end', side: 'bottom', collisionPadding: 12,
        'aria-label': t('menu'),
        style: { width: 'min(360px, calc(100vw - 24px))', maxHeight: 'min(660px, calc(100vh - 100px))', overflowY: 'auto', padding: 16 },
        children: [
          jsx('p', { style: { margin: '0 0 14px', fontSize: 13, fontWeight: 600 }, children: t('subtitle') }),
          jsx('div', {
            style: { display: 'grid', gap: 16 },
            children: DESTINATIONS.map(destination => jsx(Destination, { destination, t }, destination.id))
          }),
          jsx('p', { style: { margin: '14px 0 0', fontSize: 11, lineHeight: 1.6, color: 'var(--ui-text-tertiary)' }, children: t('hint') }),
          jsxs('details', {
            style: { marginTop: 12, fontSize: 11, lineHeight: 1.6, color: 'var(--ui-text-tertiary)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer' }, children: t('title') + ' · ' + t('help') }),
              ...['layout', 'privacy', 'pip'].map(key => jsx('p', { style: { marginBottom: 0 }, children: t(key) }, key))
            ]
          })
        ]
      })
    ]
  })
}

export default {
  id: ID,
  name: 'YouTube Dock',
  description: 'Browse your YouTube recommendations and Shorts in the Duckwork internal Browser.',
  defaultEnabled: false,
  register(ctx) {
    // Retire only this plugin’s obsolete preference; failure never changes the launcher.
    try { ctx.storage.remove('manualPinGuide') } catch { /* Older/unavailable storage is harmless. */ }
    ctx.i18n.register(bundles)
    ctx.register({ id: 'menu', area: TITLEBAR_AREAS.right, order: 15, render: () => jsx(YouTubeMenu, {}) })
    ctx.register({
      id: 'open-menu', area: PALETTE_AREA,
      data: {
        id: 'youtube-dock.open', label: ctx.i18n.t('palette'),
        keywords: ['youtube', '유튜브', '쇼츠', 'shorts', '추천', 'video'],
        run: () => menuOpen.set(true)
      }
    })
    ctx.onDispose(() => menuOpen.set(false))
  }
}
