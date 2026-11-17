/**
 * Preview Text Size — a Duckwork Desktop plugin.
 *
 * Scales the rendered Markdown in the file preview pane. Chat text size and
 * the window's UI scale are left alone.
 *
 * Controls:
 *   - Settings → Appearance → Preview Text Size (90%–175%)
 *   - ⌘K: "Preview text: larger / smaller / reset to 100%"
 *   - Shortcuts, rebindable in Settings → Keyboard Shortcuts: ⌘⌥= larger,
 *     ⌘⌥- smaller, ⌘⌥0 reset on macOS. They start unbound on Windows and
 *     Linux, where Ctrl+Alt doubles as AltGr: a Ctrl+Alt default would
 *     swallow characters such as "@" and "}" on French and German layouts.
 *
 * How it works: one stylesheet sets CSS `zoom` on the preview's
 * [data-preview-markdown] element, so headings, tables, code blocks and
 * spacing scale together. The Source and Diff views keep their size: their
 * rows are virtualized at a fixed line height. If a later Desktop release
 * renames that attribute, the plugin stops having an effect; it cannot break
 * the preview.
 */
import {
  APPEARANCE_AREAS,
  atom,
  haptic,
  KEYBINDS_AREA,
  ListRow,
  PALETTE_AREA,
  SegmentedControl,
  usePluginI18n,
  useValue
} from '@duckwork/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const ID = 'preview-text-size'
const PRESETS = [90, 100, 110, 125, 150, 175]
/** The preview's own size: at this scale the plugin adds no CSS at all. */
const NATIVE = 100
/** Size used until the user picks one. */
const DEFAULT_SCALE = 100
const STORAGE_KEY = 'scale'
// ctx.storage keeps keys in localStorage as `duckwork.plugin.<id>.<key>`.
const STORAGE_KEY_FULL = `duckwork.plugin.${ID}.${STORAGE_KEY}`

const ACTIONS = {
  larger: 'previewTextSize.larger',
  smaller: 'previewTextSize.smaller',
  reset: 'previewTextSize.reset'
}

const LOCALES = {
  en: {
    title: 'Preview Text Size',
    description:
      'Text size of the rendered Markdown in the file preview pane. Chat, sidebar and the interface scale stay as they are.',
    larger: 'Preview text: larger',
    smaller: 'Preview text: smaller',
    reset: 'Preview text: reset to 100%'
  },
  zh: {
    title: '预览文字大小',
    description: '右侧文件预览中 Markdown 渲染内容的字号。不影响聊天、侧边栏和界面缩放。',
    larger: '预览文字放大',
    smaller: '预览文字缩小',
    reset: '预览文字恢复 100%'
  }
}

const KEYWORDS = ['preview', 'markdown', 'text', 'font', 'size', 'zoom', '预览', '文字', '字体', '字号', '放大', '缩小']

/** Cmd is a separate modifier only on macOS. Elsewhere `mod` is Ctrl, and Ctrl+Alt is AltGr. */
function isMac() {
  return typeof navigator !== 'undefined' && /mac/i.test(navigator.platform || navigator.userAgent || '')
}

/** Snap any stored value to the nearest preset; garbage falls back to DEFAULT_SCALE. */
function normalize(value) {
  const n = Number(value)

  if (!Number.isFinite(n)) {
    return DEFAULT_SCALE
  }

  return PRESETS.reduce((best, preset) => (Math.abs(preset - n) < Math.abs(best - n) ? preset : best), PRESETS[0])
}

function cssFor(pct) {
  return pct === NATIVE ? '' : `[data-preview-markdown] { zoom: ${pct / 100}; }`
}

function PreviewTextSizeRow({ scale, setScale }) {
  const t = usePluginI18n(ID)
  const value = useValue(scale)

  return jsx(ListRow, {
    id: 'preview-text-size',
    title: t('title'),
    description: t('description'),
    action: jsx(SegmentedControl, {
      options: PRESETS.map(preset => ({ id: String(preset), label: `${preset}%` })),
      value: String(value),
      onChange: id => {
        haptic('selection')
        setScale(Number(id))
      }
    })
  })
}

export default {
  id: ID,
  name: 'Preview Text Size',
  description: 'Larger or smaller text in the Markdown file preview, independent of chat text size and UI scale.',
  register(ctx) {
    ctx.i18n.register(LOCALES)

    const scale = atom(normalize(ctx.storage.get(STORAGE_KEY, DEFAULT_SCALE)))

    const setScale = value => {
      const next = normalize(value)
      scale.set(next)
      ctx.storage.set(STORAGE_KEY, next)
    }

    const step = direction => {
      const index = PRESETS.indexOf(scale.get())
      setScale(PRESETS[Math.min(PRESETS.length - 1, Math.max(0, index + direction))])
    }

    const style = document.createElement('style')
    style.setAttribute('data-duckwork-plugin', ID)
    document.head.append(style)
    ctx.onDispose(() => style.remove())
    // nanostores calls the listener immediately, so the stored size applies on load.
    ctx.onDispose(
      scale.subscribe(pct => {
        style.textContent = cssFor(pct)
      })
    )

    // Another Duckwork window changed the size: follow it.
    ctx.addEventListener(window, 'storage', event => {
      if (event.key === STORAGE_KEY_FULL) {
        scale.set(normalize(ctx.storage.get(STORAGE_KEY, DEFAULT_SCALE)))
      }
    })

    ctx.register({
      id: 'appearance-row',
      area: APPEARANCE_AREAS.extra,
      render: () => jsx(PreviewTextSizeRow, { scale, setScale })
    })

    const chords = isMac()
      ? { larger: ['mod+alt+='], smaller: ['mod+alt+-'], reset: ['mod+alt+0'] }
      : { larger: [], smaller: [], reset: [] }

    // Palette and shortcut labels are read once at registration, so rebuild
    // them when the app language changes.
    const registerCommands = () => {
      const t = ctx.i18n.t
      const detail = () => `${scale.get()}%`

      return ctx.registerMany([
        {
          id: 'palette-larger',
          area: PALETTE_AREA,
          data: {
            id: `${ID}.larger`,
            label: t('larger'),
            action: ACTIONS.larger,
            keywords: KEYWORDS,
            detail,
            detailVariant: 'state',
            keepOpen: true,
            run: () => step(1)
          }
        },
        {
          id: 'palette-smaller',
          area: PALETTE_AREA,
          data: {
            id: `${ID}.smaller`,
            label: t('smaller'),
            action: ACTIONS.smaller,
            keywords: KEYWORDS,
            detail,
            detailVariant: 'state',
            keepOpen: true,
            run: () => step(-1)
          }
        },
        {
          id: 'palette-reset',
          area: PALETTE_AREA,
          data: {
            id: `${ID}.reset`,
            label: t('reset'),
            action: ACTIONS.reset,
            keywords: KEYWORDS,
            detail,
            detailVariant: 'state',
            run: () => setScale(NATIVE)
          }
        },
        {
          id: 'key-larger',
          area: KEYBINDS_AREA,
          data: { id: ACTIONS.larger, category: 'view', label: t('larger'), defaults: chords.larger, run: () => step(1) }
        },
        {
          id: 'key-smaller',
          area: KEYBINDS_AREA,
          data: { id: ACTIONS.smaller, category: 'view', label: t('smaller'), defaults: chords.smaller, run: () => step(-1) }
        },
        {
          id: 'key-reset',
          area: KEYBINDS_AREA,
          data: { id: ACTIONS.reset, category: 'view', label: t('reset'), defaults: chords.reset, run: () => setScale(NATIVE) }
        }
      ])
    }

    let disposeCommands = registerCommands()
    ctx.i18n.onLocaleChange?.(() => {
      disposeCommands()
      disposeCommands = registerCommands()
    })
  }
}
