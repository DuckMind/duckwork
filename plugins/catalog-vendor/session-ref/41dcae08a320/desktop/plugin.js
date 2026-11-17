/**
 * Session Reference — @session completions for the Duckwork Desktop composer.
 *
 * Lets you type `@session` (or start typing a session's title after `@`) and
 * pick from live session suggestions. Picking inserts a compact reference
 * like  `@session:"<title>"`  into the draft. That reference is deliberately
 * NOT expanded or injected server-side — the agent resolves it itself with
 * its session-search tool, so no context is ever copied into the message.
 *
 * Install: copy this file to  ~/.duckwork/desktop-plugins/session-ref/plugin.js
 * on the machine running the Desktop app, then ⌘K → "Reload desktop plugins".
 */

import { host, COMPOSER_AREAS } from '@duckwork/plugin-sdk'

const ID = 'session-ref'

// Cached session rows: { id, title, started_at, message_count, source }.
// `provide` must stay synchronous (the popover calls it per keystroke), so
// the gateway round-trip happens on a timer and on gateway reconnect, never
// inside the provide path.
let sessions = []

async function refreshSessions() {
  try {
    const res = await host.request('session.list', { limit: 500 })
    sessions = (res && Array.isArray(res.sessions) ? res.sessions : []).filter(
      (s) => s && s.id && s.title
    )
  } catch {
    /* gateway busy or unavailable — keep the last good cache */
  }
}

function cleanTitle(t) {
  return String(t || '').replace(/"/g, "'").trim()
}

/** 3 = title prefix, 2 = title substring, 1 = id prefix, 0 = no match. */
function matchScore(s, q) {
  if (!q) return 1 // empty query: every titled session is a candidate
  const title = (s.title || '').toLowerCase()
  const id = String(s.id || '').toLowerCase()
  if (title.startsWith(q)) return 3
  if (title.includes(q)) return 2
  if (id.startsWith(q)) return 1
  return 0
}

function provide(query) {
  if (!sessions.length) return []
  let q = String(query || '').trim().toLowerCase().replace(/^@/, '')
  // Accept `session<name>`, `session:<name>`, or a bare title/id prefix.
  q = q.replace(/^session:?\s*/, '')
  const matches = sessions
    .map((s) => ({ s, score: matchScore(s, q) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      // Empty query: most recent first. Otherwise: most active first.
      if (!q) return (b.s.started_at || 0) - (a.s.started_at || 0)
      return (b.s.message_count || 0) - (a.s.message_count || 0)
    })
    .slice(0, 15)
  return matches.map(({ s }) => ({
    insert: `@session:"${cleanTitle(s.title)}"`,
    display: s.title,
    meta: `${s.source || 'session'} · ${new Date((s.started_at || 0) * 1000).toLocaleDateString()}`
  }))
}

export default {
  id: ID,
  name: 'Session Reference',
  description:
    '@session completion — reference another session by name, no session-ID copy-paste. Reference only: nothing is injected.',
  register(ctx) {
    refreshSessions()
    // Refresh when the gateway connects/reconnects and whenever the session
    // list changes on the backend (new chat, resume, rename, compression).
    ctx.onEvent('gateway.ready', refreshSessions)
    ctx.onEvent('sessions.changed', refreshSessions)
    // Belt-and-braces timer: keeps the cache fresh even if an event is missed.
    const timer = setInterval(refreshSessions, 60_000)
    if (typeof timer.unref === 'function') timer.unref()

    ctx.register({
      id: 'at-completions',
      area: COMPOSER_AREAS.atCompletions,
      data: { provide }
    })
  }
}