// ⌃⌘] / ⌃⌘[: step through the LEFT SIDEBAR's session rows in on-screen order,
// one row per press, wrapping last → first (and first → last).
// Built-in session.next opens the recent-session switcher HUD on a repeated
// press while ⌃ is held, and walks recency order rather than the sidebar's.
//
// SDK-only: the plugin reads the sidebar order from markers it renders itself
// through the session-row slot, asks the host which session is focused, and
// opens the next one through host.openSession. It never queries or clicks the
// app's own markup, so a sidebar restyle cannot break it.
import { host, KEYBINDS_AREA, SESSION_ROW_AREAS } from '@duckwork/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const ID = 'sidebar-cycle'
const MARK = 'data-sidebar-cycle-id'
const SETTLE_FRAMES = 2
// Each wrap pass scrolls one viewport; this bounds the walk on a huge list.
const MAX_WRAP_PASSES = 40

// Zero-size, not `hidden`: a display:none node has no layout box, so it could
// neither be scrolled into view nor tell a filtered-out row from a shown one.
const MARKER_STYLE = { height: 0, overflow: 'hidden', pointerEvents: 'none', position: 'absolute', width: 0 }

function Marker({ sessionId }) {
  return jsx('span', { 'aria-hidden': true, [MARK]: sessionId, style: MARKER_STYLE })
}

const isShown = el => el.getClientRects().length > 0

// Markers in document order = the sidebar's render order (pins, date groups,
// manual drag order, filters). The virtualized Recents list renders only the
// rows near the viewport, so this is a window, not the whole list.
function markers() {
  return [...document.querySelectorAll(`[${MARK}]`)].filter(isShown)
}

const idOf = marker => marker.getAttribute(MARK)

const nextFrame = () => new Promise(resolve => requestAnimationFrame(() => resolve()))

async function settle() {
  for (let i = 0; i < SETTLE_FRAMES; i++) {
    await nextFrame()
  }
}

// Bring the rows beyond `edge` into the virtual window; true when new rows rendered.
async function revealBeyond(edge, direction) {
  const before = idOf(markers().at(direction === 1 ? -1 : 0) ?? edge)
  edge.scrollIntoView({ block: direction === 1 ? 'start' : 'end' })
  await settle()

  return idOf(markers().at(direction === 1 ? -1 : 0) ?? edge) !== before
}

// Scroll until the list edge opposite to `direction` is rendered, then return the window.
async function scrollToEdge(direction) {
  const towardStart = direction === 1
  let list = markers()

  for (let pass = 0; pass < MAX_WRAP_PASSES && list.length > 0; pass++) {
    const edge = towardStart ? list[0] : list[list.length - 1]

    if (!(await revealBeyond(edge, towardStart ? -1 : 1))) {
      break
    }

    list = markers()
  }

  return list
}

async function open(sessionId) {
  await host.openSession(sessionId)
  await settle()
  markers()
    .find(marker => idOf(marker) === sessionId)
    ?.scrollIntoView({ block: 'nearest' })
}

async function step(direction) {
  let list = markers()

  if (list.length === 0) {
    return
  }

  const focused = host.state.focusedStoredSessionId.get()
  const current = list.findIndex(marker => idOf(marker) === focused)

  if (current !== -1) {
    const target = current + direction

    if (target >= 0 && target < list.length) {
      return open(idOf(list[target]))
    }

    if (await revealBeyond(list[current], direction)) {
      list = markers()
      const moved = list.findIndex(marker => idOf(marker) === focused) + direction

      if (moved >= 0 && moved < list.length) {
        return open(idOf(list[moved]))
      }
    }
  }

  // Real edge, or the focused row is outside the rendered window: wrap.
  list = await scrollToEdge(direction)

  if (list.length > 0) {
    return open(idOf(direction === 1 ? list[0] : list[list.length - 1]))
  }
}

const run = direction => () => void step(direction).catch(error => host.notifyError?.(error))

export default {
  id: ID,
  name: 'Sidebar session cycle',
  description: '⌃⌘] / ⌃⌘[ steps through sidebar sessions in on-screen order and wraps around.',
  register(ctx) {
    ctx.registerMany([
      {
        id: 'marker',
        area: SESSION_ROW_AREAS.leading,
        data: { render: props => jsx(Marker, props) }
      },
      {
        id: 'next',
        area: KEYBINDS_AREA,
        data: {
          id: 'sidebarCycle.next',
          category: 'session',
          defaults: ['mod+ctrl+]'],
          label: 'Next sidebar session (wraps)',
          run: run(1)
        }
      },
      {
        id: 'prev',
        area: KEYBINDS_AREA,
        data: {
          id: 'sidebarCycle.prev',
          category: 'session',
          defaults: ['mod+ctrl+['],
          label: 'Previous sidebar session (wraps)',
          run: run(-1)
        }
      }
    ])
  }
}
