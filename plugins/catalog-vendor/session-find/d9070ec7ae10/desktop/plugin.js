/**
 * session-find: one window that finds any past session by what was said in it.
 *
 * What it does
 *   - "Find a session" in the command palette and mod+alt+f open a window: the
 *     search box on top, results on the left, a preview on the right.
 *   - An empty box lists pinned, then recent sessions (GET /recent), so Enter
 *     on the top row reopens yesterday's chat.
 *   - Typing searches message text, not only titles (GET /search). A row is the
 *     title, the source, the age, one line of the best matching message with
 *     the query words marked, and a quiet word for why it matched (title,
 *     keyword, meaning).
 *   - The footer carries the wait: the round trip for the list on screen, in
 *     whole milliseconds, coloured by how quick it was (under 50 ms is accent,
 *     under 200 ms is plain, past that is muted).
 *   - The preview is the matching message and its neighbours (GET /context),
 *     fetched for the highlighted row and prefetched for the next rows, so a
 *     move paints from cache.
 *   - Filters are typed in the box (in:, -in:, after:, before:, me:, repo:,
 *     "exact") and mirrored as chips. The box is the one source of truth: a
 *     source chip adds or removes its in: token, a filter chip removes its
 *     token, and the server parses the text.
 *   - Two retrieval toggles sit at the right of the box, drawn as icons: Meaning
 *     (the vector list, `vec=1`) on and Keywords (the full-text lists, `kw=1`)
 *     off by default, both kept in plugin storage. No word sits in the button,
 *     so the hover is where a mode is explained and where its state is stated.
 *     With one off the ranking is built from the other plus the titles, recency
 *     and pins; with both off the list area says so in one line and nothing is
 *     asked of the service. The toggles are for comparing the two halves on a
 *     real query, not for saving keystrokes.
 *   - The backend is asked what it can do (GET /status). A Duckwork with no search
 *     service answers from its own database and has no vector half, so on one of
 *     those the window keeps Keywords on, greys the Meaning glyph and says on its
 *     hover why, rather than failing the first search a new user runs.
 *   - Tab flips Best match and Newest; ctrl+r cycles the scope (all sessions,
 *     this profile, this repo).
 *
 * Keys (the same table the app's other lists use)
 *   - up/down move the highlight; ctrl+j/ctrl+k move it too on macOS. Off macOS
 *     Control is the app's mod key and the app's capture-phase dispatcher has
 *     already spent ctrl+j (right sidebar) and ctrl+k (palette) before this
 *     field sees the key, so the chord is honoured on macOS only.
 *   - Enter opens the highlighted session (mod+Enter in a tab, mod+shift+Enter
 *     in a window) and posts /opened. A move never opens anything.
 *   - Escape closes the window and nothing else.
 *   - Pointer: only genuine motion moves the highlight. A row sliding under a
 *     parked pointer (the scroll a key press makes) repeats the old
 *     coordinates and is ignored. A click opens.
 *
 * Why mod+alt+f and not mod+shift+f
 *   - mod+shift+f is the built-in session.focusSearch, and the plan's fallback
 *     mod+shift+k is the composer's send-queued chord. mod+alt+<letter> is the
 *     app's namespace for plugin commands (the Kanban plugin ships mod+alt+n),
 *     and f keeps the letter.
 *
 * Instant feel
 *   - No debounce. Every keystroke asks, and the answer it asks for is the
 *     keyword index alone (`fast=1`): no vector scan. The list on screen stays
 *     there while the next one loads, so nothing flashes and no spinner shows
 *     for a fast query. With Keywords off there is no paint stage to build, so
 *     the vector answer itself is asked for on every keystroke, from the model
 *     inside the service (a query embeds in single-digit milliseconds) rather
 *     than over a socket to another process. An
 *     Enter typed ahead of the answer opens the top row of that answer. A
 *     fetch still pending after 250 ms gets one quiet word in the
 *     footer. Rows, chips and panes have fixed sizes, so nothing moves while
 *     results change.
 *   - The window arrives in the frame of the key press (no entrance
 *     animation); only the way out keeps a short linger.
 *
 * Backend
 *   - /api/plugins/session-find/{search,recent,opened,context,status} through
 *     ctx.rest: a thin proxy over `duckwork-sync session-find serve`. The shapes
 *     read here are posted on bead gal-xzvz; normalizeRows accepts a bare array
 *     or {results}, and epoch seconds, ms or ISO for last_activity_at.
 *
 * Constraints
 *   - Plain ESM, loaded uncompiled: only @duckwork/plugin-sdk, react and
 *     react/jsx-runtime resolve, and UI is jsx()/jsxs() with children inside
 *     props, never the third argument (that slot is the element key; children
 *     put there are dropped without a word). tests/plugin.test.mjs guards it.
 *   - Layout in inline styles: the app ships a prebuilt Tailwind bundle, so a
 *     utility only this file used would never be generated.
 *   - Mounted from titleBar.center, a permanent mount point, so the window
 *     survives navigation and a hidden statusbar.
 *   - The two panes scroll in plain overflow boxes (the app's own
 *     dt-portal-scrollbar skin), not ScrollArea: Radix's viewport wraps its
 *     content in a display:table box, which grows to the widest nowrap row, so
 *     a 419px list laid its rows out 1364px wide and lost every ellipsis.
 *     The list box is also the one the key moves scroll, by scrollTop, so no
 *     ancestor moves with it.
 */

import {
  atom,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  host,
  icons,
  Kbd,
  KEYBINDS_AREA,
  MessageTextContent,
  PALETTE_AREA,
  queryClient,
  relativeTime,
  SearchField,
  STATUSBAR_AREAS,
  TITLEBAR_AREAS,
  useQuery,
  useValue
} from '@duckwork/plugin-sdk'
import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'session-find'
const OPEN_ACTION = 'sessionFind.open'
const OPEN_COMBO = 'mod+alt+f'

// Zero: a typed word is a sequence of questions, and each one is a few
// milliseconds of keyword index. Waiting 110 ms to ask the second one was the
// delay the owner felt, and it bought nothing the index does not already have.
const DEBOUNCE_MS = 0
// The pause that upgrades the painted keyword list to the fused answer, which
// adds the vector list (one embed round trip) and may reorder. Never on the
// typing path: only after the hand stops.
// The pause before the full answer is asked for when the keyword list has
// already painted: long enough that the vector list is not paid for on every
// keystroke of a fast typist, short enough that it lands before the hand stops.
const REFINE_PAUSE_MS = 180
const SLOW_MS = 250
const LIMIT = 30
const PREFETCH_AHEAD = 3
const AROUND = 2
const PAGE_STEP = 8
const AGE_TICK_MS = 30_000

const ROW_HEIGHT = 58
const LIST_WIDTH = '41%'
const WINDOW_WIDTH = 'min(64rem, calc(100vw - 2rem))'
const WINDOW_HEIGHT = 'min(38rem, 82vh)'

const SCOPES = ['all', 'profile', 'repo']
const SORTS = ['best', 'newest']
const SORT_LABEL = { best: 'Best match', newest: 'Newest' }

/** Sources a person chats on. They lead the chip row, so the chips a person
 *  reaches for are not pushed off the edge by worker sources. */
const INTERACTIVE_SOURCES = ['desktop', 'signal', 'tui', 'cli', 'matrix']

/** Shown when /status names no sources. */
const FALLBACK_SOURCES = [...INTERACTIVE_SOURCES, 'kanban', 'cron', 'subagent', 'a2a']

/** Text sent to the preview is capped so a very long report cannot stall the
 *  markdown renderer on every move. */
const MATCH_TEXT_CAP = 6000
const NEIGHBOUR_TEXT_CAP = 1600

const IS_MAC = /mac|iphone|ipad/i.test((typeof navigator !== 'undefined' && navigator.platform) || '')

// ---- pure helpers (exported for tests/plugin.test.mjs) -----------------------------

const TOKEN_RE = /"[^"]*"?|\S+/g
const FILTER_RE = /^(-in|in|after|before|repo|me):(.*)$/i

/** Split the box into free words, "exact" phrases and typed filters. The
 *  server is the authority on what a filter means; this only mirrors the text
 *  as chips and picks the words to mark. */
export function parseQuery(text) {
  const words = []
  const phrases = []
  const filters = []

  for (const match of String(text || '').matchAll(TOKEN_RE)) {
    const raw = match[0]

    if (raw.startsWith('"')) {
      const phrase = raw.replace(/^"/, '').replace(/"$/, '').trim()

      if (phrase) {
        phrases.push(phrase)
        filters.push({ kind: 'exact', raw, value: phrase })
      }

      continue
    }

    const filter = FILTER_RE.exec(raw)

    if (filter) {
      const kind = filter[1].toLowerCase()
      const value = filter[2].trim()

      if (value || kind === 'me') {
        filters.push({ kind, raw, value })

        continue
      }
    }

    words.push(raw)
  }

  return { filters, phrases, words }
}

/** The text with no filters left: what the server ranks on. Empty means the
 *  box holds filters only (or nothing). */
export function freeText(text) {
  const { phrases, words } = parseQuery(text)

  return [...words, ...phrases].join(' ').trim()
}

function tokensOf(text) {
  return [...String(text || '').matchAll(TOKEN_RE)].map(match => match[0])
}

function joinTokens(tokens, original) {
  const joined = tokens.join(' ')
  // Keep a trailing space the user typed so the caret carries on after a chip edit.
  const trailing = /\s$/.test(String(original || '')) || tokens.length > 0 ? ' ' : ''

  return joined ? joined + trailing : ''
}

/** Remove one token (a chip's own text) from the box. */
export function removeToken(text, raw) {
  const tokens = tokensOf(text)
  const at = tokens.findIndex(token => token.toLowerCase() === String(raw).toLowerCase())

  if (at < 0) {
    return text
  }

  tokens.splice(at, 1)

  return joinTokens(tokens, text)
}

/** One click on a source chip: add `in:<source>` when absent, remove it when
 *  present. A `-in:<source>` for the same source is removed too, since the two
 *  would ask for opposite things. */
export function toggleSource(text, source) {
  const name = String(source).toLowerCase()
  const tokens = tokensOf(text)
  const has = tokens.some(token => token.toLowerCase() === `in:${name}`)
  const kept = tokens.filter(token => !['in:', '-in:'].some(prefix => token.toLowerCase() === `${prefix}${name}`))

  if (!has) {
    kept.push(`in:${name}`)
  }

  return joinTokens(kept, text)
}

/** Sources the box asks for with in: (lowercase). */
export function activeSources(text) {
  return parseQuery(text)
    .filters.filter(filter => filter.kind === 'in')
    .map(filter => filter.value.toLowerCase())
}

/** Words to mark in a snippet or a preview: free words and phrases, longest
 *  first so a phrase wins over a word inside it. Negated words are skipped. */
export function highlightTerms(text) {
  const { phrases, words } = parseQuery(text)
  const terms = [...phrases, ...words.filter(word => !word.startsWith('-'))]
    .map(term => term.replace(/^["']+|["'*]+$/g, '').trim())
    .filter(term => term.length >= 2)
  const unique = [...new Set(terms.map(term => term.toLowerCase()))]

  return unique.sort((a, b) => b.length - a.length)
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Split text into runs, marking the runs that match a term (case-insensitive). */
export function splitHighlights(text, terms) {
  const source = String(text || '')

  if (!source || !terms || terms.length === 0) {
    return source ? [{ hit: false, text: source }] : []
  }

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi')
  const runs = []
  let last = 0

  for (const match of source.matchAll(pattern)) {
    if (match.index > last) {
      runs.push({ hit: false, text: source.slice(last, match.index) })
    }

    runs.push({ hit: true, text: match[0] })
    last = match.index + match[0].length
  }

  if (last < source.length) {
    runs.push({ hit: false, text: source.slice(last) })
  }

  return runs
}

/** Seconds, milliseconds or an ISO string to epoch milliseconds (0 when unknown). */
export function toMs(value) {
  if (value === null || value === undefined || value === '') {
    return 0
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? (value < 1e12 ? value * 1000 : value) : 0
  }

  const numeric = Number(value)

  if (Number.isFinite(numeric)) {
    return toMs(numeric)
  }

  const parsed = Date.parse(String(value))

  return Number.isFinite(parsed) ? parsed : 0
}

function oneLine(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** A message read as one line of prose: markdown markers that only make
 *  sense rendered (code ticks, bold, heading hashes, table rules) are dropped. */
export function plainSnippet(value) {
  return oneLine(
    String(value || '')
      .replace(/`+/g, '')
      .replace(/\*\*|__/g, '')
      .replace(/(^|\n)\s*#{1,6}\s+/g, '$1')
      .replace(/\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?/g, ' ')
      .replace(/(^|\s)#{1,6}\s+/g, '$1')
  )
}

/** Interactive sources first, then the rest in the server's order, deduped. */
export function orderSources(list) {
  const names = (list || []).map(source => String(source).toLowerCase()).filter(Boolean)

  return [...new Set([...INTERACTIVE_SOURCES.filter(source => names.includes(source)), ...names])]
}

/** The service's rows in one shape, deduped by session id, order kept. */
export function normalizeRows(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results)
      ? payload.results
      : Array.isArray(payload?.sessions)
        ? payload.sessions
        : Array.isArray(payload?.items)
          ? payload.items
          : []

  const seen = new Set()
  const rows = []

  for (const raw of list) {
    const id = String(raw?.session_id ?? raw?.id ?? '').trim()

    if (!id || seen.has(id)) {
      continue
    }

    seen.add(id)
    rows.push({
      archived: Boolean(raw.archived),
      at: toMs(raw.last_activity_at ?? raw.started_at),
      id,
      messageId: raw.snippet_message_id ?? null,
      pinned: Boolean(raw.pinned),
      profile: String(raw.profile ?? raw.profile_name ?? ''),
      snippet: plainSnippet(raw.snippet),
      source: String(raw.source || ''),
      title: oneLine(raw.title) || 'Untitled session',
      why: Array.isArray(raw.why) ? raw.why.map(reason => String(reason).toLowerCase()) : []
    })
  }

  return rows
}

/** The id of the last user message in a context list, or null. */
export function lastUserId(messages) {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'user') {
      return messages[i].id
    }
  }

  return null
}

/** Why a row matched, in the three words a row shows: title, keyword, meaning. */
// ---- how long an answer took ---------------------------------------------------------
// The footer says the number the person waited for: the round trip from this
// window, through the plugin's proxy, to the service. Two thresholds turn it
// into a glance: under FAST_TRIP_MS the answer is instant, over SLOW_TRIP_MS the list
// arrived late enough to notice, and the colour says which without a word.

export const FAST_TRIP_MS = 50
export const SLOW_TRIP_MS = 200

/** 'fast' | 'ok' | 'slow' for a round trip, or 'none' when there is no number. */
export function speedTone(ms) {
  if (ms === null || ms === undefined) {
    return 'none'
  }

  if (ms <= FAST_TRIP_MS) {
    return 'fast'
  }

  return ms <= SLOW_TRIP_MS ? 'ok' : 'slow'
}

/** The number as it is printed: whole milliseconds, never a decimal. */
export function tookText(ms) {
  if (ms === null || ms === undefined) {
    return ''
  }

  return `${Math.round(ms)} ms`
}

export function whyLabel(why) {
  const reasons = new Set(why || [])
  const words = []

  if (reasons.has('title')) {
    words.push('title')
  }

  if (reasons.has('keyword')) {
    words.push('keyword')
  }

  if (reasons.has('vector') || reasons.has('meaning')) {
    words.push('meaning')
  }

  return words.join(' + ')
}

/** Pinned first, then the rest, order kept inside each group. */
export function partitionPinned(rows) {
  const pinned = rows.filter(row => row.pinned)
  const recent = rows.filter(row => !row.pinned)

  return { flat: [...pinned, ...recent], pinned, recent }
}

/** One step through the scopes; `repo` is skipped while no workspace is open. */
export function nextScope(scope, hasRepo) {
  const order = hasRepo ? SCOPES : SCOPES.filter(name => name !== 'repo')
  const at = order.indexOf(scope)

  return order[(at + 1) % order.length] ?? 'all'
}

export function nextSort(sort) {
  return sort === 'best' ? 'newest' : 'best'
}

/** Clamped move; -1 when the list is empty. */
export function moveIndex(index, delta, length) {
  if (length <= 0) {
    return -1
  }

  const from = index < 0 ? 0 : index

  return Math.max(0, Math.min(length - 1, from + delta))
}

/** What a key press in the box means here, or null to leave it to the field. */
export function keyAction(event, isMac = IS_MAC) {
  if (event.isComposing) {
    return null
  }

  const key = event.key
  const bare = !event.ctrlKey && !event.metaKey && !event.altKey

  if (bare && !event.shiftKey) {
    if (key === 'ArrowDown') {
      return { delta: 1, type: 'move' }
    }

    if (key === 'ArrowUp') {
      return { delta: -1, type: 'move' }
    }

    if (key === 'PageDown') {
      return { delta: PAGE_STEP, type: 'move' }
    }

    if (key === 'PageUp') {
      return { delta: -PAGE_STEP, type: 'move' }
    }
  }

  if (isMac && event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey) {
    const letter = String(key).toLowerCase()

    if (letter === 'j') {
      return { delta: 1, type: 'move' }
    }

    if (letter === 'k') {
      return { delta: -1, type: 'move' }
    }
  }

  if (key === 'Enter' && !event.altKey) {
    const mod = isMac ? event.metaKey : event.ctrlKey

    return { intent: mod && event.shiftKey ? 'window' : mod ? 'tab' : 'in-place', type: 'open' }
  }

  if (key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    return { type: 'sort' }
  }

  if (event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey && String(key).toLowerCase() === 'r') {
    return { type: 'scope' }
  }

  return null
}

/** The search request's path, relative to the plugin namespace. */
export function searchPath({ cwd, fast, keywords, meaning, profile, q, scope, sort }) {
  const params = new URLSearchParams({ limit: String(LIMIT), q, scope, sort })

  // `fast=1` is the keyword-only answer: the paint stage. The full answer is
  // asked for once the typing pause has passed (or on every keystroke when
  // there is no paint stage), and it is the one that holds the recall (vectors)
  // the fast list does not have.
  if (fast) {
    params.set('fast', '1')
  }

  if (profile) {
    params.set('profile', profile)
  }

  if (scope === 'repo' && cwd) {
    params.set('cwd', cwd)
  }

  // The two retrieval toggles, always explicit: a service that changed its own
  // default must not change what the window shows without the window saying so.
  params.set('vec', meaning ? '1' : '0')
  params.set('kw', keywords ? '1' : '0')

  return `/search?${params.toString()}`
}

function basename(path) {
  const parts = String(path || '')
    .replace(/\/+$/, '')
    .split('/')

  return parts[parts.length - 1] || ''
}

export function scopeLabel(scope, profile, cwd) {
  if (scope === 'profile') {
    return `Profile ${profile || 'default'}`
  }

  if (scope === 'repo') {
    return cwd ? `Repo ${basename(cwd)}` : 'Repo'
  }

  return 'All sessions'
}

function capText(text, cap) {
  const value = String(text || '')

  return value.length > cap ? `${value.slice(0, cap).trimEnd()}\n\n...` : value
}

// ---- state shared by the palette row, the keybind and the window ------------------

// Said when neither half is on. A machine with no service cannot offer meaning,
// so the sentence names only what it can do.
const EMPTY_HINT = 'Turn on Meaning or Keywords to search.'
const EMPTY_HINT_WORDS = 'Turn on Keywords to search: this Duckwork has no search service for meaning.'

const $open = atom(false)
// The two retrieval toggles. Meaning on, Keywords off: the shipped list is the
// vector answer, and the exact-word half is one press away. Meaning is the
// vector half and Keywords the full-text half; both live in plugin storage.
const $meaning = atom(true)
const $keywords = atom(false)

// One shared empty list, so the hint state does not hand the effects a new
// array identity on every render.
const NO_ROWS = []
const $sort = atom('best')
const $scope = atom('all')

/** ctx.rest and ctx.storage, bound once in register(). */
let rest = null
let storage = null

function setPersisted(store, key, value) {
  store.set(value)
  storage?.set(key, value)
}

function openFinder() {
  $open.set(true)
}

// ---- data ---------------------------------------------------------------------------

const keys = {
  context: (sessionId, messageId) => [ID, 'context', sessionId, messageId ?? 'tail'],
  recent: profile => [ID, 'recent', profile],
  search: args => [
    ID,
    'search',
    args.q,
    args.sort,
    args.scope,
    args.profile,
    args.scope === 'repo' ? args.cwd : '',
    args.meaning ? 1 : 0,
    args.keywords ? 1 : 0,
    args.fast ? 1 : 0
  ],
  status: () => [ID, 'status']
}

// ---- diagnostics --------------------------------------------------------------------
// The window runs on a machine an agent cannot see, so every call to this
// plugin's backend records what it asked and what came back into plugin storage
// (localStorage, key duckwork.plugin.<id>.<key>). A report of "it did not answer"
// then names the connection, the path and the failure, instead of leaving the
// shape of the sentence on screen as the only evidence. The last few calls are
// kept, and a failure to record is ignored: diagnostics must never break the
// thing they measure.

const DIAG_KEY = 'lastCalls'
const DIAG_CAP = 8

function activeConnection() {
  try {
    return host.state.connectionId?.get() ?? null
  } catch {
    return null
  }
}

function noteCall(entry) {
  try {
    const kept = storage?.get(DIAG_KEY, [])
    const list = Array.isArray(kept) ? kept : []

    storage?.set(DIAG_KEY, [...list, { connection: activeConnection(), ...entry }].slice(-DIAG_CAP))
  } catch {
    // See above: a diagnostic that throws is worse than no diagnostic.
  }
}

async function callRest(path, options) {
  const started = Date.now()

  try {
    const payload = await rest(path, options)

    noteCall({ at: new Date().toISOString(), ms: Date.now() - started, ok: true, path })

    return payload
  } catch (error) {
    // A cancelled request is not a failed one: a keystroke aborts the answer to
    // the key before it, and recording that as an error would put a red row in
    // the diagnostics for every character typed.
    if (isAbort(error)) {
      throw error
    }

    noteCall({
      at: new Date().toISOString(),
      message: String((error && error.message) || error),
      ms: Date.now() - started,
      name: String((error && error.name) || ''),
      ok: false,
      path,
      status: Number((error && error.status) || 0) || null
    })

    throw error
  }
}

function isAbort(error) {
  return Boolean(error) && (error.name === 'AbortError' || error.code === 'ABORT_ERR' || error.code === 20)
}

async function fetchSearch(args, signal) {
  const started = Date.now()
  const payload = await callRest(searchPath(args), signal ? { signal } : undefined)

  return { q: args.q, rows: normalizeRows(payload), took: Date.now() - started }
}

async function fetchRecent(profile) {
  const params = new URLSearchParams({ limit: String(LIMIT) })

  if (profile) {
    params.set('profile', profile)
  }

  const started = Date.now()
  const rows = partitionPinned(normalizeRows(await callRest(`/recent?${params.toString()}`))).flat

  return { q: '', rows, took: Date.now() - started }
}

async function fetchContext(sessionId, messageId) {
  const params = new URLSearchParams({ around: String(AROUND), session_id: sessionId })

  if (messageId !== null && messageId !== undefined) {
    params.set('message_id', String(messageId))
  }

  const payload = await callRest(`/context?${params.toString()}`)
  const list = Array.isArray(payload) ? payload : Array.isArray(payload?.messages) ? payload.messages : []

  return list.map(message => ({
    at: toMs(message.timestamp),
    content: String(message.content ?? message.text ?? ''),
    id: message.id ?? null,
    role: String(message.role || '')
  }))
}

function contextQuery(row) {
  return {
    queryFn: () => fetchContext(row.id, row.messageId),
    queryKey: keys.context(row.id, row.messageId),
    retry: false,
    staleTime: 5 * 60_000
  }
}

function prefetchContext(rows) {
  for (const row of rows) {
    if (row && row.messageId) {
      void queryClient.prefetchQuery(contextQuery(row))
    }
  }
}

/** Which door opens a result: the message-level one when this desktop has it,
 *  the session door otherwise. An older desktop only knows `openSession`, so a
 *  feature check is the whole compatibility story. */
export function openTarget(hostApi, row, options) {
  return row.messageId && typeof hostApi.revealMessage === 'function'
    ? hostApi.revealMessage(row.id, row.messageId, options)
    : hostApi.openSession(row.id, options)
}

function openRow(row, intent = 'in-place') {
  if (!row) {
    return
  }

  $open.set(false)

  const options = { intent }

  if (row.profile) {
    options.profile = row.profile
  }

  openTarget(host, row, options).catch(error => host.notifyError(error, 'Could not open the session'))
  rest?.('/opened', { body: { session_id: row.id }, method: 'POST' }).catch(() => undefined)
}

function intentFromPointer(event) {
  const mod = IS_MAC ? event.metaKey : event.ctrlKey

  return mod && event.shiftKey ? 'window' : mod ? 'tab' : 'in-place'
}

// ---- styles (inline: the prebuilt Tailwind bundle has no plugin-only utilities) ----

const TEXT = 'var(--color-foreground)'
// The app's tertiary text token measured 3.5:1 on this window in the light
// theme, under the 4.5:1 floor, so secondary is the quietest tier used here.
const TEXT_2 = 'var(--ui-text-secondary)'
const RULE = '1px solid var(--ui-stroke-tertiary)'
const SCROLLER = 'dt-portal-scrollbar'
const ACCENT = 'var(--theme-primary)'
const HOT_WASH = 'var(--ui-control-hover-background)'

const TRUNCATE = { minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }

// Colour is one channel; weight is the second, so a mark reads in both themes.
const MARK_STYLE = {
  background: 'color-mix(in srgb, var(--theme-primary) 18%, transparent)',
  borderRadius: 2,
  color: 'inherit',
  fontWeight: 600,
  padding: '0 1px'
}

const LABEL_STYLE = {
  color: ACCENT,
  fontSize: '0.64rem',
  fontWeight: 600,
  letterSpacing: '0.16em',
  padding: '10px 14px 4px',
  textTransform: 'uppercase'
}

function chipStyle(active) {
  return {
    alignItems: 'center',
    background: active ? 'color-mix(in srgb, var(--theme-primary) 10%, transparent)' : 'transparent',
    border: `1px solid ${active ? 'color-mix(in srgb, var(--theme-primary) 55%, transparent)' : 'var(--ui-stroke-tertiary)'}`,
    borderRadius: 999,
    color: active ? TEXT : TEXT_2,
    cursor: 'pointer',
    display: 'inline-flex',
    flexShrink: 0,
    fontSize: 11,
    fontWeight: active ? 600 : 400,
    gap: 4,
    height: 22,
    lineHeight: '20px',
    padding: '0 9px',
    whiteSpace: 'nowrap'
  }
}

// ---- pieces -------------------------------------------------------------------------

function Marked({ terms, text }) {
  const runs = splitHighlights(text, terms)

  return jsx('span', {
    children: runs.map((run, index) =>
      run.hit ? jsx('mark', { children: run.text, key: index, style: MARK_STYLE }) : run.text
    )
  })
}

/** decorateText for MessageTextContent: marks the query words inside each
 *  paragraph's text nodes, leaving elements (code, links) as they are. */
function markerFor(terms) {
  if (!terms.length) {
    return undefined
  }

  const markNode = (node, index) =>
    typeof node === 'string'
      ? splitHighlights(node, terms).map((run, at) =>
          run.hit ? jsx('mark', { children: run.text, key: `m${index}-${at}`, style: MARK_STYLE }) : run.text
        )
      : node

  return children => (Array.isArray(children) ? children.flatMap(markNode) : markNode(children, 0))
}

function Row({ hot, now, onOpen, onPointer, row, terms }) {
  const pressAt = useRef(null)
  const why = whyLabel(row.why)
  const meta = [row.archived ? 'archived' : '', row.source].filter(Boolean).join(' \u00b7 ')
  const detail = row.snippet || (row.profile && row.profile !== 'default' ? row.profile : '')

  return jsxs('div', {
    'aria-selected': hot,
    'data-nav-hot': hot ? 'true' : undefined,
    'data-session-id': row.id,
    onClick: event => {
      const at = pressAt.current

      // A press that travelled is a text selection, not a click.
      if (at && Math.abs(event.clientX - at.x) + Math.abs(event.clientY - at.y) > 4) {
        return
      }

      onOpen(row, intentFromPointer(event))
    },
    onMouseDown: event => {
      pressAt.current = { x: event.clientX, y: event.clientY }
    },
    onMouseMove: event => onPointer(row, event),
    role: 'option',
    style: {
      background: hot ? HOT_WASH : 'transparent',
      borderRadius: 6,
      boxShadow: hot ? `inset 2px 0 0 ${ACCENT}` : 'none',
      display: 'flex',
      flexDirection: 'column',
      gap: 3,
      height: ROW_HEIGHT,
      justifyContent: 'center',
      margin: '0 6px',
      padding: '0 10px 0 12px'
    },
    children: [
      jsxs('div', {
        style: { alignItems: 'center', display: 'flex', gap: 6, minWidth: 0 },
        children: [
          row.pinned
            ? jsx(icons.Pin, { 'aria-label': 'Pinned', style: { color: TEXT_2, flexShrink: 0, height: 12, width: 12 } })
            : null,
          jsx('span', {
            style: { ...TRUNCATE, color: TEXT, flex: 1, fontSize: 13, fontWeight: hot ? 600 : 500 },
            children: jsx(Marked, { terms, text: row.title })
          }),
          jsx('span', {
            style: { ...TRUNCATE, color: hot ? TEXT : TEXT_2, flexShrink: 0, fontSize: 11, maxWidth: '45%' },
            children: [meta, row.at ? relativeTime(row.at, now) : ''].filter(Boolean).join(' \u00b7 ')
          })
        ]
      }),
      jsxs('div', {
        style: { alignItems: 'center', display: 'flex', gap: 8, minWidth: 0 },
        children: [
          jsx('span', {
            style: { ...TRUNCATE, color: hot ? TEXT : TEXT_2, flex: 1, fontSize: 12 },
            children: jsx(Marked, { terms, text: detail })
          }),
          why
            ? jsx('span', {
                style: { color: hot ? TEXT : TEXT_2, flexShrink: 0, fontSize: 10.5, letterSpacing: '0.02em' },
                children: why
              })
            : null
        ]
      })
    ]
  })
}

function SectionLabel({ text }) {
  return jsx('div', { 'aria-hidden': true, style: LABEL_STYLE, children: text })
}

function ResultList({ error, hint, hotIndex, listRef, mode, now, onOpen, onPointer, rows, terms }) {
  const pinnedCount = mode === 'recent' ? rows.filter(row => row.pinned).length : 0
  const children = []

  rows.forEach((row, index) => {
    if (mode === 'recent' && index === 0 && pinnedCount > 0) {
      children.push(jsx(SectionLabel, { key: 'label-pinned', text: 'Pinned' }))
    }

    if (mode === 'recent' && index === pinnedCount) {
      children.push(jsx(SectionLabel, { key: 'label-recent', text: 'Recent' }))
    }

    children.push(jsx(Row, { hot: index === hotIndex, key: row.id, now, onOpen, onPointer, row, terms }))
  })

  if (rows.length === 0) {
    children.push(
      jsx('div', {
          key: 'empty',
          style: { color: TEXT_2, fontSize: 12, lineHeight: 1.5, padding: '18px 16px' },
          children: hint || (error
            ? jsxs('div', {
                children: [
                  jsx('div', { style: { color: TEXT, fontWeight: 500 }, children: 'The search service did not answer.' }),
                  jsx('div', { style: { color: TEXT_2, marginTop: 4 }, children: String(error.message || error) })
                ]
              })
            : mode === 'recent'
              ? 'No recent sessions yet.'
              : 'No sessions match. Try fewer words, or drop a filter.')
      })
    )
  }

  return jsx('div', {
    className: SCROLLER,
    'data-scroll': 'list',
    ref: listRef,
    style: { height: '100%', minHeight: 0, overflowX: 'hidden', overflowY: 'auto', overscrollBehavior: 'contain' },
    children: jsx('div', {
      'aria-label': 'Sessions',
      'data-nav-list': '',
      role: 'listbox',
      style: { display: 'flex', flexDirection: 'column', gap: 1, padding: '6px 0' },
      children
    })
  })
}

class PreviewBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return jsx('div', { style: { color: TEXT_2, fontSize: 12, padding: 16 }, children: 'This preview could not be drawn.' })
    }

    return this.props.children
  }
}

function roleLabel(role) {
  if (role === 'user') {
    return 'You'
  }

  if (role === 'assistant') {
    return 'Duckwork'
  }

  return role || 'Message'
}

function PreviewMessage({ decorate, match, matchLabel, message, sessionId }) {
  return jsxs('div', {
    'data-match': match ? 'true' : undefined,
    style: {
      background: match ? 'color-mix(in srgb, var(--theme-primary) 5%, transparent)' : 'transparent',
      borderRadius: 6,
      boxShadow: match ? `inset 2px 0 0 ${ACCENT}` : 'none',
      padding: '8px 12px 8px 14px'
    },
    children: [
      jsx('div', {
        style: { color: match ? ACCENT : TEXT_2, fontSize: 10.5, fontWeight: 600, letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' },
        children: match ? `${roleLabel(message.role)} \u00b7 ${matchLabel}` : roleLabel(message.role)
      }),
      jsx('div', {
        style: { color: match ? TEXT : TEXT_2, fontSize: 12.5, lineHeight: 1.55, overflowWrap: 'anywhere' },
        // Keyed by the message: the markdown stack rewrites nodes it owns, so a
        // reader reused across messages throws on the swap.
        children: jsx(MessageTextContent, {
          decorateText: decorate,
          key: `${sessionId}:${message.id ?? 'snippet'}`,
          media: false,
          text: capText(message.content, match ? MATCH_TEXT_CAP : NEIGHBOUR_TEXT_CAP)
        })
      })
    ]
  })
}

function Preview({ mode, now, row, terms }) {
  // Every row has something to show: a row with no matching message asks
  // /context without a message_id, and the service answers with the last turn.
  const context = useQuery({ ...contextQuery(row || { id: '', messageId: null }), enabled: Boolean(row && row.id) })
  const latest = mode === 'recent' || Boolean(row && row.why && row.why.includes('latest'))

  if (!row) {
    return jsx('div', { style: { color: TEXT_2, fontSize: 12, padding: 18 }, children: 'Nothing highlighted.' })
  }

  const decorate = markerFor(terms)
  const messages = context.data && context.data.length > 0 ? context.data : null
  // Paint from the row at once; neighbours replace it when /context answers.
  const shown = messages || (row.snippet ? [{ content: row.snippet, id: row.messageId, role: '' }] : [])
  const meta = [row.source, row.profile, row.at ? relativeTime(row.at, now) : '', row.pinned ? 'pinned' : '', row.archived ? 'archived' : '']
    .filter(Boolean)
    .join(' \u00b7 ')

  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 },
    children: [
      jsxs('div', {
        style: { borderBottom: RULE, flexShrink: 0, padding: '12px 16px 10px' },
        children: [
          jsx('div', {
            style: { color: TEXT, fontSize: 14, fontWeight: 600, lineHeight: 1.35, textWrap: 'balance' },
            children: jsx(Marked, { terms, text: row.title })
          }),
          jsx('div', { style: { ...TRUNCATE, color: TEXT_2, fontSize: 11, marginTop: 3 }, children: meta })
        ]
      }),
      jsx('div', {
        className: SCROLLER,
        style: { flex: 1, minHeight: 0, overflowX: 'hidden', overflowY: 'auto', overscrollBehavior: 'contain' },
        children: jsx(PreviewBoundary, {
            children: jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 8px 14px' },
              children: [
                ...shown.map((message, index) =>
                  jsx(PreviewMessage, {
                    decorate,
                    key: `${row.id}:${message.id ?? index}`,
                    match: messages ? (row.messageId !== null ? message.id === row.messageId : latest && message.role === 'user' && message.id === lastUserId(messages)) : true,
                    // A row with no hit is anchored on its last turn, not on a match.
                    matchLabel: latest ? 'latest' : 'best match',
                    message,
                    sessionId: row.id
                  })
                ),
                shown.length === 0 && !context.isPending
                  ? jsx('div', {
                      key: 'hint',
                      style: { color: TEXT_2, fontSize: 12, padding: '6px 12px' },
                      // An error here means a service too old to answer /context
                      // without a message_id; it is not an empty session.
                      children: context.isError ? 'The last turn could not be loaded. Enter opens the session.' : 'This session has no messages yet.'
                    })
                  : null,
                context.isError && row.snippet
                  ? jsx('div', { key: 'gap', style: { color: TEXT_2, fontSize: 11, padding: '2px 14px' }, children: 'Neighbouring messages are not available.' })
                  : null
              ]
            })
        })
      })
    ]
  })
}

function Chips({ cwd, onEdit, profile, scope, sources, text, onScope }) {
  const active = new Set(activeSources(text))
  const typed = parseQuery(text).filters.filter(filter => filter.kind !== 'in')
  const known = new Set(sources)
  // A source typed by hand that the chip list does not carry still gets a chip.
  const extra = [...active].filter(source => !known.has(source))

  const filterLabel = filter =>
    filter.kind === 'exact'
      ? `"${filter.value}"`
      : filter.kind === '-in'
        ? `not ${filter.value}`
        : filter.kind === 'me'
          ? 'my messages'
          : `${filter.kind} ${filter.value}`

  return jsxs('div', {
    style: {
      alignItems: 'center',
      display: 'flex',
      flexShrink: 0,
      gap: 6,
      height: 34,
      overflowX: 'auto',
      overflowY: 'hidden',
      padding: '0 12px 8px',
      scrollbarWidth: 'none'
    },
    children: [
      jsx('button', {
        'aria-label': `Scope: ${scopeLabel(scope, profile, cwd)}. Control R cycles it.`,
        onClick: onScope,
        onMouseDown: event => event.preventDefault(),
        style: { ...chipStyle(scope !== 'all'), fontWeight: 600 },
        type: 'button',
        children: scopeLabel(scope, profile, cwd)
      }),
      // The filters the box holds come first: they are the state in force, and
      // the source chips after them may run past the edge.
      ...typed.map(filter =>
        jsxs('span', {
          key: `filter-${filter.raw}`,
          style: { ...chipStyle(true), cursor: 'default', paddingRight: 3 },
          children: [
            jsx('span', { children: filterLabel(filter) }),
            jsx('button', {
              'aria-label': `Remove ${filterLabel(filter)}`,
              onClick: () => onEdit(removeToken(text, filter.raw)),
              onMouseDown: event => event.preventDefault(),
              style: {
                alignItems: 'center',
                background: 'transparent',
                border: 0,
                borderRadius: 999,
                color: TEXT_2,
                cursor: 'pointer',
                display: 'inline-flex',
                height: 16,
                justifyContent: 'center',
                padding: 0,
                width: 16
              },
              type: 'button',
              children: jsx(icons.X, { style: { height: 11, width: 11 } })
            })
          ]
        })
      ),
      jsx('span', { 'aria-hidden': true, style: { background: 'var(--ui-stroke-tertiary)', flexShrink: 0, height: 14, width: 1 } }),
      ...[...sources, ...extra].map(source =>
        jsx('button', {
          'aria-pressed': active.has(source),
          key: `source-${source}`,
          onClick: () => onEdit(toggleSource(text, source)),
          onMouseDown: event => event.preventDefault(),
          style: chipStyle(active.has(source)),
          type: 'button',
          children: source
        })
      )
    ]
  })
}

function Hint({ keys: combo, label }) {
  return jsxs('span', {
    style: { alignItems: 'center', display: 'inline-flex', gap: 4, whiteSpace: 'nowrap' },
    children: [...combo.map(key => jsx(Kbd, { key, size: 'sm', children: key })), jsx('span', { children: label })]
  })
}

const MOD_GLYPH = IS_MAC ? '\u2318' : 'Ctrl'

const TONE_COLOR = { fast: ACCENT, none: TEXT_2, ok: TEXT, slow: TEXT_2 }

function Footer({ count, mode, status, took }) {
  return jsxs('div', {
    style: {
      alignItems: 'center',
      borderTop: RULE,
      color: TEXT_2,
      display: 'flex',
      flexShrink: 0,
      fontSize: 11,
      gap: 14,
      height: 32,
      justifyContent: 'space-between',
      padding: '0 12px'
    },
    children: [
      jsxs('div', {
        style: { alignItems: 'center', display: 'flex', gap: 12, minWidth: 0, overflow: 'hidden' },
        children: [
          jsx(Hint, { keys: IS_MAC ? ['\u2191', '\u2193', '\u2303J', '\u2303K'] : ['\u2191', '\u2193'], label: 'move' }),
          jsx(Hint, { keys: ['\u21b5'], label: 'open' }),
          jsx(Hint, { keys: [`${MOD_GLYPH}\u21b5`], label: 'new tab' }),
          jsx(Hint, { keys: ['Tab'], label: 'best / newest' }),
          jsx(Hint, { keys: [IS_MAC ? '\u2303R' : 'Ctrl R'], label: 'scope' }),
          jsx(Hint, { keys: ['Esc'], label: 'close' })
        ]
      }),
      jsx('div', {
        'aria-live': 'polite',
        style: {
          alignItems: 'baseline',
          display: 'flex',
          flexShrink: 0,
          fontVariantNumeric: 'tabular-nums',
          gap: 8,
          whiteSpace: 'nowrap'
        },
        children: status
          ? status
          : [
              jsx('span', {
                key: 'count',
                // The empty box has no query to count, so a bare number in the
                // corner would be a mystery: name what the time belongs to.
                children: mode === 'search' ? `${count} ${count === 1 ? 'session' : 'sessions'}` : 'recent'
              }),
              // The wait, in whole milliseconds. Tabular figures keep the bar
              // from shifting as the digits change between queries.
              took === null || took === undefined
                ? null
                : jsx('span', {
                    key: 'took',
                    style: { color: TONE_COLOR[speedTone(took)] },
                    title: `this answer took ${tookText(took)} round trip`,
                    children: tookText(took)
                  })
            ]
      })
    ]
  })
}

// One retrieval mode as a glyph. The hover is the explanation, so it says what
// the mode is and then where it stands; the state itself rides the tint, the
// border and the colour of the glyph; and the accessible name is the aria-label,
// which spells out both. Two words did not earn their space beside the box, and
// an icon is a target of its own size.
function RetrievalToggle({ disabled, icon, label, on, onToggle, title }) {
  const state = disabled
    ? 'Not available here.'
    : on
      ? 'On now, click to turn it off.'
      : 'Off now, click to turn it on.'

  return jsx('button', {
    'aria-disabled': disabled ? true : undefined,
    'aria-label': `${label} search is ${on ? 'on' : 'off'}`,
    'aria-pressed': on,
    onClick: disabled ? undefined : onToggle,
    onMouseDown: event => event.preventDefault(),
    title: `${title} ${state}`,
    type: 'button',
    style: {
      alignItems: 'center',
      background: on ? 'color-mix(in srgb, var(--theme-primary) 12%, transparent)' : 'transparent',
      border: `1px solid ${on ? 'color-mix(in srgb, var(--theme-primary) 55%, transparent)' : 'var(--ui-stroke-tertiary)'}`,
      borderRadius: 5,
      // A glyph is a graphic, so accent on the accent tint has to clear 3:1
      // rather than the 4.5:1 the word this button used to carry needed.
      color: on ? ACCENT : TEXT_2,
      cursor: disabled ? 'default' : 'pointer',
      display: 'inline-flex',
      flexShrink: 0,
      height: 24,
      justifyContent: 'center',
      opacity: disabled ? 0.4 : 1,
      padding: 0,
      width: 28
    },
    children: jsx(icon, { 'aria-hidden': true, style: { height: 14, width: 14 } })
  })
}

function SortToggle({ onChange, sort }) {
  return jsx('div', {
    role: 'group',
    'aria-label': 'Sort',
    style: { display: 'inline-flex', flexShrink: 0 },
    children: SORTS.map(id =>
      jsx('button', {
        'aria-pressed': sort === id,
        key: id,
        onClick: () => onChange(id),
        onMouseDown: event => event.preventDefault(),
        type: 'button',
        style: {
          background: 'transparent',
          border: 0,
          borderBottom: `2px solid ${sort === id ? ACCENT : 'transparent'}`,
          color: sort === id ? TEXT : TEXT_2,
          cursor: 'pointer',
          fontSize: 11.5,
          fontWeight: sort === id ? 600 : 400,
          height: 24,
          padding: '0 7px'
        },
        children: SORT_LABEL[id]
      })
    )
  })
}

// ---- the window ---------------------------------------------------------------------

function useSlowFlag(active) {
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    if (!active) {
      setSlow(false)

      return undefined
    }

    const timer = setTimeout(() => setSlow(true), SLOW_MS)

    return () => clearTimeout(timer)
  }, [active])

  return slow
}

function Finder({ inputRef }) {
  const profile = useValue(host.state.profile) || ''
  const cwd = useValue(host.state.cwd) || ''
  const meaning = useValue($meaning)
  const keywords = useValue($keywords)
  const sort = useValue($sort)
  const storedScope = useValue($scope)
  const scope = storedScope === 'repo' && !cwd ? 'all' : storedScope

  const [text, setText] = useState('')
  const [settled, setSettled] = useState('')
  const [lounged, setLounged] = useState('')
  const [hotId, setHotId] = useState(null)
  const [now, setNow] = useState(() => Date.now())
  const listRef = useRef(null)
  const reveal = useRef(false)
  const pointer = useRef({ x: -1, y: -1 })
  const pendingOpen = useRef(null)
  const shown = useRef({ error: null, key: '', mode: 'recent', q: '', rows: [] })

  // Ages repaint on a tick while the window is up.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), AGE_TICK_MS)

    return () => clearInterval(timer)
  }, [])

  // Every keystroke is a question, one timer later. DEBOUNCE_MS is 0: the wait
  // that used to sit here was the delay the owner felt, and the keyword index
  // answers too fast to need it. The timer still exists so a clear answers in
  // the same tick instead of on the next frame.
  useEffect(() => {
    if (text === settled) {
      return undefined
    }

    const timer = setTimeout(() => setSettled(text), text.trim() ? DEBOUNCE_MS : 0)

    return () => clearTimeout(timer)
  }, [text, settled])

  // The short pause that upgrades the painted keyword list to the full answer.
  // It is the step that brings the vector list in, so recall ends where it
  // always was, and it never delays the paint.
  useEffect(() => {
    const timer = setTimeout(() => setLounged(text), REFINE_PAUSE_MS)

    return () => clearTimeout(timer)
  }, [text])

  const q = settled.trim()
  const searching = q !== ''
  // What the backend can do, asked once and kept. Until the answer lands the
  // window assumes meanings, which is what a machine with a service has, and
  // which keeps the toggle from flickering off on the way in.
  const statusQuery = useQuery({
    queryFn: () => callRest('/status'),
    queryKey: keys.status(),
    retry: false,
    staleTime: 60_000
  })
  const vectors = statusQuery.data ? statusQuery.data.vectors !== false : true
  const meaningOn = meaning && vectors
  const anyRetrieval = meaningOn || keywords
  // Both halves off is a state the window answers itself: one line, no request.
  // Declared after the toggles because the hint reads their resolved values, and
  // a `const` read before its declaration throws on every render.
  const hint = searching && !anyRetrieval ? (vectors ? EMPTY_HINT : EMPTY_HINT_WORDS) : ''
  const args = { cwd, keywords, meaning: meaningOn, profile, q, scope, sort }

  // A backend with no vector half must not leave the window asking for meaning:
  // the first search a new user runs would be an error about a service they have
  // never heard of. Anyone who has already chosen a mode keeps their choice.
  useEffect(() => {
    if (!statusQuery.data || statusQuery.data.vectors !== false) {
      return
    }

    if (storage.get('meaning', null) === null && storage.get('keywords', null) === null) {
      $meaning.set(false)
      $keywords.set(true)
    }
  }, [statusQuery.data])

  // No placeholderData: an observer's "previous" answer can be a search from
  // two steps back (search, clear to recent, type again), which would flash an
  // older list. What stays on screen while a query loads is what WAS on
  // screen, held in `shown` below.
  // The paint stage: keyword index only. `signal` is the query's own abort
  // signal, which react-query fires when this key stops being observed, so a
  // keystroke typed while the previous answer is in flight cancels it rather
  // than queueing behind it.
  // There is a paint stage only when Keywords is on: it is the keyword index,
  // and it is asked for on every keystroke.
  const plain = useQuery({
    enabled: searching && keywords,
    queryFn: ({ signal }) => fetchSearch({ ...args, fast: true, keywords: true, meaning: false }, signal),
    queryKey: keys.search({ ...args, fast: true, keywords: true, meaning: false }),
    retry: false,
    staleTime: 30_000
  })

  // The full answer for the toggles as they are. With Keywords on it waits for
  // the typing pause and replaces the painted list; with Keywords off there is
  // nothing painted before it, so it is asked for on every keystroke instead.
  const refinedReady = keywords ? lounged === settled && plain.isSuccess : settled === text
  const refined = useQuery({
    enabled: searching && anyRetrieval && refinedReady,
    queryFn: ({ signal }) => fetchSearch({ ...args, fast: false }, signal),
    queryKey: keys.search({ ...args, fast: false }),
    retry: false,
    staleTime: 60_000
  })

  const recent = useQuery({
    enabled: !searching,
    queryFn: () => fetchRecent(profile),
    queryKey: keys.recent(profile),
    retry: false,
    staleTime: 15_000
  })

  // What is on screen: the answer for the current question when we hold it,
  // else the last list shown, so the list never empties while the next loads.
  // `key` names the question a list answers; Enter trusts only a list whose
  // key is the question in the box.
  const keyOf = (query, sortBy, scopeBy) => JSON.stringify(query ? [query, sortBy, scopeBy, profile] : ['', 'recent', profile])
  const current = keyOf(q, sort, scope)
  let view = null

  if (searching) {
    const useRefined = refined.data && refined.data.q === q
    const data = useRefined ? refined.data : plain.data
    const failure = plain.error || refined.error

    if (data) {
      view = { error: null, key: current, mode: 'search', q, rows: data.rows, took: data.took ?? null }
    } else if (failure) {
      view = { error: failure, key: current, mode: 'search', q, rows: [], took: null }
    }
  } else if (recent.data) {
    view = { error: null, key: current, mode: 'recent', q: '', rows: recent.data.rows, took: recent.data.took ?? null }
  } else if (recent.error) {
    view = { error: recent.error, key: current, mode: 'recent', q: '', rows: [], took: null }
  }

  if (view) {
    shown.current = view
  } else {
    view = shown.current
  }

  const fresh = view.key === keyOf(text.trim(), sort, scope)
  const rows = hint ? NO_ROWS : view.rows
  const terms = useMemo(() => highlightTerms(view.q), [view.q])
  const found = hotId ? rows.findIndex(row => row.id === hotId) : -1
  const hotIndex = rows.length === 0 ? -1 : found >= 0 ? found : 0
  const hotRow = hotIndex >= 0 ? rows[hotIndex] : null

  // A new question starts at the top row.
  useEffect(() => {
    setHotId(null)
  }, [settled, sort, scope])

  // A new list starts scrolled to its top.
  useEffect(() => {
    const viewport = listRef.current

    if (viewport) {
      viewport.scrollTop = 0
    }
  }, [view.q, view.mode, sort, scope])

  // Keep the hot row inside the list's own box after a key move. The list's
  // scrollTop is set directly: scrollIntoView would scroll every ancestor.
  useEffect(() => {
    if (!reveal.current) {
      return
    }

    reveal.current = false

    const viewport = listRef.current
    const hot = listRef.current?.querySelector('[data-nav-hot="true"]')

    if (!viewport || !hot) {
      return
    }

    if (hotIndex === 0) {
      viewport.scrollTop = 0

      return
    }

    const box = viewport.getBoundingClientRect()
    const rect = hot.getBoundingClientRect()

    if (rect.top < box.top + 4) {
      viewport.scrollTop -= box.top + 4 - rect.top
    } else if (rect.bottom > box.bottom - 4) {
      viewport.scrollTop += rect.bottom - (box.bottom - 4)
    }
  }, [hotIndex])

  // Prefetch the preview for the rows a move would reach next, once the hand
  // has stopped. Prefetching on every list change meant four extra /context
  // round trips per keystroke, each through the dashboard proxy to a state.db
  // read, competing with the search that paints the next key. Nothing needs a
  // preview until the list has settled.
  useEffect(() => {
    if (hotIndex < 0 || lounged !== settled) {
      return
    }

    prefetchContext(rows.slice(Math.max(0, hotIndex - 1), hotIndex + 1 + PREFETCH_AHEAD))
  }, [rows, hotIndex, lounged, settled])

  // An Enter pressed before the answer for the typed text landed opens the
  // top row of that answer, unless the user moved meanwhile.
  useEffect(() => {
    const pending = pendingOpen.current

    if (pending && fresh && view.q === pending.q && !(view.mode === 'search' && view.error)) {
      pendingOpen.current = null
      openRow(rows[hotIndex], pending.intent)
    }
  })

  const focusInput = useCallback(() => inputRef.current?.focus(), [inputRef])

  const onPointer = useCallback((row, event) => {
    const last = pointer.current

    // A row sliding under a parked pointer repeats the last coordinates.
    if (event.clientX === last.x && event.clientY === last.y) {
      return
    }

    pointer.current = { x: event.clientX, y: event.clientY }
    setHotId(current => (current === row.id ? current : row.id))
  }, [])

  const onKeyDown = event => {
    const action = keyAction(event)

    if (!action) {
      return
    }

    event.preventDefault()
    event.stopPropagation()

    if (action.type === 'move') {
      const next = moveIndex(hotIndex, action.delta, rows.length)

      if (next >= 0) {
        reveal.current = true
        setHotId(rows[next].id)
      }

      return
    }

    if (action.type === 'open') {
      if (!fresh) {
        pendingOpen.current = { intent: action.intent, q: text.trim() }
        setSettled(text)

        return
      }

      openRow(hotRow, action.intent)

      return
    }

    if (action.type === 'sort') {
      setPersisted($sort, 'sort', nextSort(sort))

      return
    }

    if (action.type === 'scope') {
      setPersisted($scope, 'scope', nextScope(scope, Boolean(cwd)))
    }
  }

  const sources = Array.isArray(statusQuery.data?.sources) && statusQuery.data.sources.length > 0
    ? orderSources(statusQuery.data.sources)
    : FALLBACK_SOURCES

  const slowPlain = useSlowFlag(searching && (keywords ? plain.isFetching : refined.isFetching))
  const slowRecent = useSlowFlag(!searching && recent.isFetching && !recent.data)
  const status = slowPlain || slowRecent ? 'Searching' : ''

  return jsxs('div', {
    'data-session-find': '',
    style: { display: 'flex', flexDirection: 'column', height: WINDOW_HEIGHT, minHeight: 0 },
    children: [
      jsxs('div', {
        style: { alignItems: 'center', display: 'flex', flexShrink: 0, gap: 10, padding: '10px 12px 8px' },
        children: [
          // Keys are read on the wrapper, not through SearchField's own
          // onKeyDown: older desktop builds' SearchField has no such prop, and a
          // build that has it would deliver the key twice.
          jsx('div', {
            onKeyDown,
            style: { display: 'flex', flex: 1, minWidth: 0 },
            children: jsx(SearchField, {
              'aria-label': 'Find a session',
              containerClassName: 'w-full',
              inputClassName: 'text-sm flex-1',
              inputRef,
              onChange: setText,
              placeholder: 'Find a session by what was said in it',
              value: text
            })
          }),
          jsx(SortToggle, {
            onChange: id => {
              setPersisted($sort, 'sort', id)
              focusInput()
            },
            sort
          }),
          jsx(RetrievalToggle, {
            icon: icons.Brain,
            label: 'Meaning',
            disabled: !vectors,
            on: meaningOn,
            onToggle: () => {
              setPersisted($meaning, 'meaning', !meaningOn)
              focusInput()
            },
            title: vectors
              ? 'Finds a session by what it was about, not the words it used.'
              : 'Meaning search needs a session-find service, and this Duckwork has none.'
          }),
          jsx(RetrievalToggle, {
            icon: icons.Hash,
            label: 'Keywords',
            on: keywords,
            onToggle: () => {
              setPersisted($keywords, 'keywords', !keywords)
              focusInput()
            },
            title: 'Finds an exact word, identifier or phrase.'
          })
        ]
      }),
      jsx(Chips, {
        cwd,
        onEdit: next => {
          setText(next)
          focusInput()
        },
        onScope: () => {
          setPersisted($scope, 'scope', nextScope(scope, Boolean(cwd)))
          focusInput()
        },
        profile,
        scope,
        sources,
        text
      }),
      jsxs('div', {
        style: { borderTop: RULE, display: 'flex', flex: 1, minHeight: 0 },
        children: [
          jsx('div', {
            style: { borderRight: RULE, flexShrink: 0, minHeight: 0, width: LIST_WIDTH },
            children: jsx(ResultList, {
              error: view.error,
              hint,
              hotIndex,
              listRef,
              mode: view.mode,
              now,
              onOpen: openRow,
              onPointer,
              rows,
              terms
            })
          }),
          jsx('div', {
            style: { flex: 1, minHeight: 0, minWidth: 0 },
            children: jsx(Preview, { key: hotRow ? hotRow.id : 'none', mode: view.mode, now, row: hotRow, terms })
          })
        ]
      }),
      jsx(Footer, {
        count: rows.length,
        mode: view.mode,
        status,
        // The number belongs to the list on screen: a stale view, a failure
        // or the both-toggles-off hint has no answer to time.
        took: fresh && !hint && !view.error ? view.took : null
      })
    ]
  })
}

function FinderHost() {
  const open = useValue($open)
  const inputRef = useRef(null)

  return jsx(Dialog, {
    onOpenChange: next => $open.set(next),
    open,
    children: jsxs(DialogContent, {
      blurBackdrop: false,
      bodyClassName: 'p-0 gap-0 overflow-hidden',
      'data-nav-palette': '',
      // Opened from the command palette, this window mounts while the palette
      // is still closing; the palette then hands focus back to wherever it was
      // opened from, which Radix reads as focus leaving this window and
      // dismisses it. A click outside still closes it; a stray focus does not,
      // and the trapped focus scope pulls the caret back into the box.
      onFocusOutside: event => event.preventDefault(),
      onOpenAutoFocus: event => {
        event.preventDefault()
        inputRef.current?.focus()
      },
      showCloseButton: false,
      style: {
        maxHeight: 'none',
        maxWidth: 'none',
        width: WINDOW_WIDTH,
        // In the frame of the key press; only the way out lingers.
        ...(open ? { animation: 'none' } : { animationDuration: '90ms' })
      },
      children: [
        jsx(DialogTitle, { className: 'sr-only', children: 'Find a session' }),
        jsx(DialogDescription, {
          className: 'sr-only',
          children: 'Type what you remember. Arrow keys move, Enter opens, Tab switches Best match and Newest.'
        }),
        jsx(Finder, { inputRef })
      ]
    })
  })
}

/** The bottom-bar door: an icon a person can click without knowing the keybind.
 *  Contributed as DATA, not as a render slot, so the host draws its own chip and
 *  its own tooltip. The tooltip reads the live keybind for opening the window
 *  (actionId), which is the one thing a hover has to teach. An addition to the
 *  palette row and the keybind, never a replacement: the bar can be hidden on
 *  purpose (its hide row carries the way back) and simple mode rests it hidden,
 *  so the other two doors must keep working on their own. */
const STATUSBAR_ITEM = {
  actionId: OPEN_ACTION,
  icon: jsx(icons.Search, { 'aria-hidden': true, style: { height: 13, width: 13 } }),
  id: 'sessionFind.statusbar',
  onSelect: openFinder,
  title: 'Find a session'
}

export default {
  id: ID,
  name: 'Session Find',
  description: 'Find any past session by what was said in it: keyword and meaning search, a preview, typed filters.',
  register(ctx) {
    rest = ctx.rest
    storage = ctx.storage

    $meaning.set(ctx.storage.get('meaning', true) !== false)
    $keywords.set(ctx.storage.get('keywords', false) === true)
    $sort.set(SORTS.includes(ctx.storage.get('sort', 'best')) ? ctx.storage.get('sort', 'best') : 'best')
    $scope.set(SCOPES.includes(ctx.storage.get('scope', 'all')) ? ctx.storage.get('scope', 'all') : 'all')

    // Boot marker: proves which build the app loaded, and on which connection,
    // without needing the window opened first.
    noteCall({ at: new Date().toISOString(), build: 'statusbar+diagnostics', ok: true, path: 'register' })

    ctx.onDispose(() => {
      $open.set(false)
      rest = null
      storage = null
    })

    ctx.registerMany([
      {
        id: 'statusbar-open',
        area: STATUSBAR_AREAS.left,
        order: 20,
        data: STATUSBAR_ITEM
      },
      {
        id: 'window',
        area: TITLEBAR_AREAS.center,
        render: () => jsx(FinderHost, {})
      },
      {
        id: 'palette-open',
        area: PALETTE_AREA,
        data: {
          action: OPEN_ACTION,
          id: OPEN_ACTION,
          icon: icons.Search,
          keywords: ['find', 'search', 'session', 'history', 'chat', 'past', 'message'],
          label: 'Find a session',
          run: openFinder
        }
      },
      {
        id: 'keybind-open',
        area: KEYBINDS_AREA,
        data: {
          category: 'navigation',
          defaults: [OPEN_COMBO],
          id: OPEN_ACTION,
          label: 'Find a session',
          run: openFinder
        }
      }
    ])
  }
}
