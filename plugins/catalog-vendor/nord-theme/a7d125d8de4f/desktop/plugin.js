/**
 * Nord for Duckwork Desktop.
 *
 * A full DesktopTheme (not a CLI skin): hand-tuned Polar Night (dark) and
 * Snow Storm (light) palettes, the Nord terminal ANSI set, and a scoped CSS
 * layer for the parts a palette alone cannot reach (semantic colors, text
 * selection, inline code, code-block syntax colors).
 *
 * Palette rules
 *   - Canonical Nord hexes (nordtheme.com) for every primary role.
 *   - A derived value is one of: a blend of two Nord colors, one extra step
 *     of the Polar Night / Snow Storm ladder (OKLab extrapolation), or a Nord
 *     hue with only its OKLCH lightness lowered until it clears WCAG AA on the
 *     light surfaces. Each one is named and explained below.
 *
 * Elevation ladder (dark):  well #22272F < base nord0 < raised nord1 < active nord2
 * Elevation ladder (light): well nord5 < base nord6 < floating #F3F5F8
 *
 * Install: `duckwork plugins install nord-theme`, then enable it under
 * Capabilities > Plugins.
 * Keep the theme name `nord` free of a CLI skin with the same name: an active
 * backend skin called `nord` would shadow this theme in the desktop registry.
 *
 * Nord palette: Copyright (c) 2016-present Sven Greb (Arctic Ice Studio), MIT.
 * This plugin is an unofficial port and is not affiliated with the Nord project.
 */

import { requestTheme, THEMES_AREA } from '@duckwork/plugin-sdk'

const ID = 'nord-theme'
const THEME_NAME = 'nord'

// -- Canonical Nord ----------------------------------------------------------
const nord = {
  // Polar Night
  nord0: '#2E3440',
  nord1: '#3B4252',
  nord2: '#434C5E',
  nord3: '#4C566A',
  nord3Bright: '#616E88', // Nord's own comment color (VS Code / vim ports)
  // Snow Storm
  nord4: '#D8DEE9',
  nord5: '#E5E9F0',
  nord6: '#ECEFF4',
  // Frost
  nord7: '#8FBCBB',
  nord8: '#88C0D0',
  nord9: '#81A1C1',
  nord10: '#5E81AC',
  // Aurora
  nord11: '#BF616A',
  nord12: '#D08770',
  nord13: '#EBCB8B',
  nord14: '#A3BE8C',
  nord15: '#B48EAD'
}

// -- Derived values ----------------------------------------------------------
const derived = {
  // One Polar Night step below nord0 (nord0 + (nord0 - nord1) in OKLab).
  // Recessed surfaces in dark mode: the sidebar and code wells.
  polarWell: '#22272F',
  // One Snow Storm step above nord6. Floating surfaces in light mode.
  snowFloat: '#F3F5F8',
  // The app paints primary text at 94% of the foreground. These inks make
  // that paint land exactly on nord4 (dark) and nord0 (light).
  inkDark: '#E3E9F4',
  inkLight: '#222835',
  // nord1 with 10% nord8: the user bubble, a raised surface with a frost hint.
  bubbleDark: '#434F5F',
  // nord5 with 8% nord10.
  bubbleLight: '#DAE1EB',
  // nord0 with 16% nord8 / nord6 with 12% nord10: soft accent surfaces.
  accentSoftDark: '#3C4A57',
  accentSoftLight: '#DBE2EB',
  // Comments: nord3Bright moved 21% toward nord4, so 11px code comments read
  // at 4:1 on the dark code well (canonical nord3Bright measures 2.9:1 there).
  commentDark: '#7A869C'
}

// Nord hues deepened for light surfaces: same OKLCH hue and chroma, lightness
// lowered until the color clears 4.5:1 on nord5 (the light sidebar / code well).
const deep = {
  nord7: '#457070',
  nord8: '#3A707F',
  nord9: '#4D6C89',
  nord10: '#496B95', // canonical nord10 measures 3.3:1 on nord5
  nord11: '#A74C56',
  nord14: '#587042',
  nord15: '#815E7B'
}

// Light semantic colors, measured against nord6 (4.5:1; 3.6:1 for the
// yellow/orange pair, which carry dots and bars rather than text).
const semanticLight = {
  red: '#AB4F59',
  orange: '#B06A54',
  yellow: '#967839',
  green: '#5C7446',
  cyan: '#3E7483',
  blue: '#4C6F99',
  purple: '#85617F'
}

// -- Palettes ----------------------------------------------------------------
const darkColors = {
  background: nord.nord0,
  foreground: derived.inkDark,
  card: nord.nord1,
  cardForeground: derived.inkDark,
  muted: nord.nord1,
  mutedForeground: nord.nord4,
  popover: nord.nord1,
  popoverForeground: derived.inkDark,
  primary: nord.nord8,
  primaryForeground: nord.nord0,
  secondary: nord.nord2,
  secondaryForeground: derived.inkDark,
  accent: derived.accentSoftDark,
  accentForeground: derived.inkDark,
  border: nord.nord2,
  input: nord.nord2,
  ring: nord.nord8,
  midground: nord.nord8,
  midgroundForeground: nord.nord0,
  composerRing: nord.nord8,
  destructive: nord.nord11,
  destructiveForeground: nord.nord6,
  sidebarBackground: derived.polarWell,
  sidebarBorder: nord.nord1,
  userBubble: derived.bubbleDark,
  userBubbleBorder: nord.nord2
}

const lightColors = {
  background: nord.nord6,
  foreground: derived.inkLight,
  card: nord.nord5,
  cardForeground: derived.inkLight,
  muted: nord.nord5,
  mutedForeground: nord.nord3,
  popover: derived.snowFloat,
  popoverForeground: derived.inkLight,
  primary: deep.nord10,
  primaryForeground: nord.nord6,
  secondary: nord.nord4,
  secondaryForeground: derived.inkLight,
  accent: derived.accentSoftLight,
  accentForeground: derived.inkLight,
  border: nord.nord4,
  input: nord.nord4,
  ring: deep.nord10,
  midground: deep.nord10,
  midgroundForeground: nord.nord6,
  composerRing: deep.nord10,
  destructive: semanticLight.red,
  destructiveForeground: nord.nord6,
  sidebarBackground: nord.nord5,
  sidebarBorder: nord.nord4,
  userBubble: derived.bubbleLight,
  userBubbleBorder: nord.nord4
}

// Official Nord terminal colors. Bright black uses nord3Bright instead of
// nord3 so dim CLI output (autosuggestions, test dots) stays visible.
const darkTerminal = {
  foreground: nord.nord4,
  cursor: nord.nord4,
  selectionBackground: '#434C5ECC',
  black: nord.nord1,
  red: nord.nord11,
  green: nord.nord14,
  yellow: nord.nord13,
  blue: nord.nord9,
  magenta: nord.nord15,
  cyan: nord.nord8,
  white: nord.nord5,
  brightBlack: nord.nord3Bright,
  brightRed: nord.nord11,
  brightGreen: nord.nord14,
  brightYellow: nord.nord13,
  brightBlue: nord.nord9,
  brightMagenta: nord.nord15,
  brightCyan: nord.nord7,
  brightWhite: nord.nord6
}

// Nord has no official light terminal set. Normal colors are the Nord hues
// deepened to 4.5:1 on nord6; bright colors stop at 3:1. White is a readable
// Nord grey, because programs that print "white" assume a dark background.
const lightTerminal = {
  foreground: nord.nord0,
  cursor: deep.nord10,
  selectionBackground: '#88C0D066',
  black: nord.nord1,
  red: '#AB4F59',
  green: '#5C7446',
  yellow: '#866828',
  blue: '#4C6F99',
  magenta: '#85617F',
  cyan: '#3E7483',
  white: '#7D8696',
  brightBlack: nord.nord3,
  brightRed: nord.nord11,
  brightGreen: '#779161',
  brightYellow: '#A48547',
  brightBlue: nord.nord10,
  brightMagenta: '#A47E9D',
  brightCyan: '#5B92A1',
  brightWhite: '#A0A8B6'
}

// -- Code-block syntax colors ------------------------------------------------
// The app highlights code with GitHub's Shiki themes. Those themes share one
// nine-role structure, so each role maps to one Nord color. The mapping was
// measured by highlighting a 17-language corpus with both themes and taking
// the Nord color each GitHub color lands on most often.
// Columns: github-dark-dimmed, github-dark-default, github-light-default,
//          [extra light hexes], Nord dark, Nord light.
const SYNTAX_ROLES = [
  { role: 'text', gh: ['#ADBAC7', '#E6EDF3', '#1F2328'], dark: nord.nord4, light: nord.nord0 },
  { role: 'keyword', gh: ['#F47067', '#FF7B72', '#CF222E'], dark: nord.nord9, light: deep.nord9 },
  { role: 'constant', gh: ['#6CB6FF', '#79C0FF', '#0550AE'], dark: nord.nord15, light: deep.nord15 },
  { role: 'type', gh: ['#F69D50', '#FFA657', '#953800'], dark: nord.nord7, light: deep.nord7 },
  { role: 'function', gh: ['#DCBDFB', '#D2A8FF', '#8250DF'], dark: nord.nord8, light: deep.nord8 },
  { role: 'tag', gh: ['#8DDB8C', '#7EE787', '#116329'], dark: nord.nord7, light: deep.nord7 },
  { role: 'string', gh: ['#96D0FF', '#A5D6FF', '#0A3069'], dark: nord.nord14, light: deep.nord14 },
  { role: 'comment', gh: ['#768390', '#8B949E', '#6E7781', '#57606A'], dark: derived.commentDark, light: nord.nord3Bright },
  { role: 'invalid', gh: ['#FF938A', '#FFA198', '#82071E'], dark: nord.nord11, light: deep.nord11 }
]

const rgbOf = hex => {
  const n = Number.parseInt(hex.slice(1), 16)

  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

// Two render paths carry token colors:
//   1. Dual-theme HTML (chat code blocks, file preview): every span carries
//      `--shiki-dark:#HEX`, so the dark hex identifies the role in both modes.
//   2. Token rows (inline diffs): React writes `color: rgb(r, g, b)`.
// `light-dark()` follows the color-scheme the app sets, like Shiki itself.
function syntaxCss(scope) {
  return SYNTAX_ROLES.map(({ gh, dark, light }) => {
    const darkHexes = gh.slice(0, 2)

    const selectors = [
      ...darkHexes.map(hex => `${scope} [style*="--shiki-dark:${hex}" i]`),
      ...gh.map(hex => `${scope} [style*="color: ${rgbOf(hex)}"]`)
    ]

    return `${selectors.join(',\n')} {\n  color: light-dark(${light}, ${dark}) !important;\n}`
  }).join('\n\n')
}

// Match the theme and its accent retints (`nord-accent-<hex>`).
const SCOPE = ':root:is([data-duckwork-theme="nord"], [data-duckwork-theme^="nord-accent-"])'
const DARK = `${SCOPE}.dark`
const LIGHT = `${SCOPE}:not(.dark)`

const customCSS = `
/* Nord for Duckwork Desktop: injected only while the Nord theme is painted. */

/* The app blends chrome, card, popover and bubble seeds toward a neutral
   grey. Nord brings its own ladder, so paint the seeds as authored. If these
   knobs ever change upstream, the theme degrades to the app's default blend. */
${SCOPE} {
  --theme-mix-chrome: 100% !important;
  --theme-mix-card: 100% !important;
  --theme-mix-elevated: 100% !important;
  --theme-mix-bubble: 100% !important;
}

${DARK} {
  --ui-red: ${nord.nord11};
  --ui-orange: ${nord.nord12};
  --ui-yellow: ${nord.nord13};
  --ui-green: ${nord.nord14};
  --ui-cyan: ${nord.nord8};
  --ui-blue: ${nord.nord9};
  --ui-purple: ${nord.nord15};
  --ui-success: ${nord.nord14} !important;
  --ui-selection-background: color-mix(in srgb, ${nord.nord8} 35%, transparent);
  --ui-inline-code-background: ${nord.nord1};
  --ui-inline-code-foreground: ${nord.nord7};
  --dt-scrollbar-thumb: ${nord.nord4};
}

${LIGHT} {
  --ui-red: ${semanticLight.red};
  --ui-orange: ${semanticLight.orange};
  --ui-yellow: ${semanticLight.yellow};
  --ui-green: ${semanticLight.green};
  --ui-cyan: ${semanticLight.cyan};
  --ui-blue: ${semanticLight.blue};
  --ui-purple: ${semanticLight.purple};
  --ui-success: ${semanticLight.green} !important;
  --ui-selection-background: color-mix(in srgb, ${nord.nord8} 40%, transparent);
  --ui-inline-code-background: color-mix(in srgb, ${nord.nord4} 60%, transparent);
  --ui-inline-code-foreground: ${deep.nord7};
  --dt-scrollbar-thumb: ${nord.nord3};
}

/* Code sits in a recessed Polar Night well in dark mode: canonical Nord
   syntax colors gain contrast there (keywords 5.6:1 vs 3.7:1 on nord1). */
${DARK} [data-slot='code-card'] {
  --ui-bg-editor: ${derived.polarWell};
}

/* The app dims GitHub's bright dark tokens with a filter. Nord's tokens are
   already soft, so render them at their real values. */
${DARK} .shiki {
  filter: none !important;
}

/* GitHub token roles -> Nord. Degrades to the app's GitHub colors if the app
   ever switches highlighter themes. */
${syntaxCss(SCOPE)}
`

const nordTheme = {
  name: THEME_NAME,
  label: 'Nord',
  description: 'Arctic, north-bluish: Polar Night and Snow Storm',
  colors: lightColors,
  darkColors,
  terminal: lightTerminal,
  darkTerminal,
  customCSS
}

const APPLIED_KEY = 'applied-once'

export default {
  id: ID,
  name: 'Nord Theme',
  description: 'Nord color theme: Polar Night (dark) and Snow Storm (light).',
  register(ctx) {
    ctx.register({ id: THEME_NAME, area: THEMES_AREA, data: nordTheme })

    // Select Nord once, on the first load after install. Later loads leave the
    // user's own pick alone; Settings > Appearance switches back any time.
    if (ctx.storage.get(APPLIED_KEY, false)) {
      return
    }

    let tries = 0

    const apply = () => {
      if (requestTheme(THEME_NAME)) {
        ctx.storage.set(APPLIED_KEY, true)
      } else if (++tries < 20) {
        setTimeout(apply, 100)
      }
    }

    setTimeout(apply, 0)
  }
}
