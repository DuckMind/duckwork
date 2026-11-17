/**
 * Plex Music — statusbar player for a Plex music library.
 * Mini-Plexamp: Playing / Browse / Playlists tabs, likes synced to the
 * server, custom playlists, repeat, sleep timer, and OS media keys.
 *
 * Setup: open the panel, set Server + Token, Save & test.
 * Token lives in plugin storage only. Local server default: http://127.0.0.1:32400
 * Local admin token: %LOCALAPPDATA%\Plex Media Server\.LocalAdminToken
 *
 * Likes: tapping the heart writes rating 10, which is what feeds Plex's
 * Liked Songs smart playlist. Tapping again clears it. (Plex stores 0–10;
 * this plugin is intentionally binary — finer scores set in Plexamp show
 * as unliked until tapped.)
 *
 * Plain ESM, loaded uncompiled — jsx() calls, not JSX syntax.
 * Only these imports resolve: @duckwork/plugin-sdk, react, react/jsx-runtime.
 */
import {
  atom, Button, GlyphSpinner, icons, Popover, PopoverContent, PopoverTrigger,
  RowButton, SearchField, STATUSBAR_AREAS, Tip, usePluginI18n, useQuery, useValue
} from '@duckwork/plugin-sdk'
import { Component, useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'plex-music'
const SECTION_FALLBACK = '13'
const PAGE = 50

const EN = {
  plex: 'Plex Music',
  browse: 'Browse Plex music',
  play: 'Play', pause: 'Pause', next: 'Next track', prev: 'Previous track',
  shuffle: 'Shuffle', shuffleOn: 'Shuffle on', shuffleOff: 'Shuffle off',
  live: 'Playing', paused: 'Paused', connecting: 'Loading', error: 'Playback error',
  search: 'Search songs, artists, albums…',
  tabPlaylists: 'Playlists', tabBrowse: 'Browse', tabPlaying: 'Playing',
  tracks: 'Tracks', artistsAlbums: 'Artists & albums',
  playlistsEmpty: 'No music playlists on this server yet.',
  shuffleAll: 'Shuffle Random Playlist',
  seek: 'Seek',
  songsCount: n => `${n} song${n === 1 ? '' : 's'}`,
  smart: 'Smart · auto-updates',
  artists: 'Artists', albums: 'Albums', albumTracks: 'Tracks',
  shuffleArtist: 'Shuffle artist',
  shuffleAlbum: 'Shuffle album',
  back: 'Back',
  queue: 'Up next', emptyQueue: 'Search and pick something to play.',
  volume: 'Volume', mute: 'Mute', unmute: 'Unmute',
  server: 'Server', token: 'Token', saveTest: 'Save & test',
  getToken: 'Get token…',
  signOut: 'Sign out',
  tokenHint: 'Server owners: Get token…, then paste %LOCALAPPDATA%\\Plex Media Server into the picker address bar and open .LocalAdminToken. Everyone else: Plex Web → any item → ⋯ → Get Info → View XML → copy the token from the URL.',
  settings: 'Connection', showSettings: 'Show connection settings', hideSettings: 'Hide connection settings',
  needToken: 'Set your server and token first.',
  connected: section => `Connected · Music section ${section}`,
  badServer: 'Cannot reach server — check the URL.',
  badToken: 'Unauthorized — check the token.',
  noMusic: 'No music section found on that server.',
  noResults: 'Nothing found.',
  loadError: 'Could not load tracks.',
  rateError: 'Could not save rating.',
  like: 'Like', unlike: 'Unlike',
  repeatOff: 'Repeat off', repeatAll: 'Repeat all', repeatOne: 'Repeat one',
  addTo: 'Add to…', newPlaylist: '＋ New playlist', create: 'Create',
  playlistName: 'Playlist name', added: 'Added to playlist', addFailed: 'Could not save.',
  created: 'Playlist created', remove: 'Remove', clearQueue: 'Clear',
  sleepOff: 'Sleep off', sleepTimer: 'Sleep timer',
  rename: 'Rename', save: 'Save', delete: 'Delete', confirmDelete: 'Confirm delete?',
  newName: 'New name', needSong: 'Play something first',
  nowPlaying: 'Now playing',
}
const LOCALES = { en: EN }

const CSS = `
.duckwork-plex-bar{display:flex;align-items:center;gap:2px;height:100%;color:var(--ui-text-tertiary)}
.duckwork-plex-dot{width:6px;height:6px;border-radius:50%;background:var(--ui-text-quaternary);flex-shrink:0;margin-left:4px}
.duckwork-plex-dot[data-live=true]{background:var(--ui-accent)}
.duckwork-plex-bar .plex-name{width:112px;overflow:hidden;text-overflow:ellipsis;text-align:left}
.duckwork-plex-bar .duckwork-plex-action{width:16px;height:16px;padding:0;flex-shrink:0}
.duckwork-plex-action-icon{display:flex;align-items:center;justify-content:center;width:12px;height:12px;flex-shrink:0;overflow:hidden}
.duckwork-plex-next{display:flex;align-items:center;width:12px;height:12px}
.duckwork-plex-next-flip{transform:scaleX(-1)}
.duckwork-plex-panel{width:360px;max-width:calc(100vw - 24px)}
.duckwork-plex-head{display:flex;align-items:center;gap:6px;padding:2px 4px 4px;font-size:12px;font-weight:600;color:var(--ui-text-primary)}
.duckwork-plex-conn{font-size:11px;font-weight:400;color:var(--ui-text-tertiary);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.duckwork-plex-conn[data-ok=true]{color:var(--ui-accent)}
.duckwork-plex-tabs{display:flex;gap:2px;padding:0 4px 6px}
.duckwork-plex-tab{flex:1;height:24px;font-size:12px;border:0;border-radius:4px;background:none;color:var(--ui-text-tertiary);cursor:pointer}
.duckwork-plex-tab[data-on=true]{background:var(--chrome-action-hover);color:var(--ui-text-primary)}
.duckwork-plex-settings{display:flex;flex-direction:column;gap:4px;padding:0 4px 6px}
.duckwork-plex-settings input{height:24px;font-size:12px;padding:0 6px;border-radius:4px;border:1px solid var(--ui-stroke-secondary);background:transparent;color:var(--ui-text-primary);width:100%;box-sizing:border-box}
.duckwork-plex-settings-row{display:flex;gap:4px}
.duckwork-plex-search{display:flex;align-items:center;height:32px;padding:0 4px 4px}
.duckwork-plex-search-field{flex:1;min-width:0;border:0}
.duckwork-plex-search-field input{flex:1;width:0;min-width:0}
.duckwork-plex-search-loader{display:flex;align-items:center;justify-content:center;width:16px;flex-shrink:0;font-size:12px;color:var(--ui-text-tertiary)}
.duckwork-plex-group{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ui-text-quaternary);padding:4px 6px 2px}
.duckwork-plex-list{max-height:220px;min-height:60px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}
.duckwork-plex-row{display:flex;align-items:center;gap:4px;border-radius:4px}
.duckwork-plex-row[data-current=true]{background:var(--chrome-action-hover)}
.duckwork-plex-row:hover{background:var(--chrome-action-hover)}
.duckwork-plex-row-main{display:flex;align-items:center;gap:8px;flex:1;min-width:0;text-align:left;min-height:32px;padding:3px 6px;cursor:pointer;border-radius:4px}
.duckwork-plex-art{width:28px;height:28px;border-radius:3px;flex-shrink:0;object-fit:cover;background:var(--chrome-action-hover)}
.duckwork-plex-row-copy{min-width:0;flex:1}
.duckwork-plex-row-name{display:block;font-size:12px;line-height:16px;color:var(--ui-text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.duckwork-plex-row[data-current=true] .duckwork-plex-row-name{color:var(--ui-accent)}
.duckwork-plex-row-sub{display:block;font-size:11px;line-height:14px;color:var(--ui-text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.duckwork-plex-dur{font-size:11px;color:var(--ui-text-quaternary);flex-shrink:0}
.duckwork-plex-error{font-size:11px;line-height:16px;color:var(--ui-text-secondary);padding:4px 6px}
.duckwork-plex-nowbar{display:flex;align-items:center;gap:8px;padding:6px 4px 2px;min-width:0;cursor:pointer;border-radius:4px;text-align:left;width:100%;background:none;border:0}
.duckwork-plex-nowbar:hover{background:var(--chrome-action-hover)}
.duckwork-plex-now-art{width:36px;height:36px;border-radius:4px;flex-shrink:0;object-fit:cover;background:var(--chrome-action-hover)}
.duckwork-plex-bigart{width:120px;height:120px;border-radius:8px;object-fit:cover;background:var(--chrome-action-hover);flex-shrink:0}
.duckwork-plex-hero{display:flex;gap:10px;padding:6px 4px;align-items:center}
.duckwork-plex-hero-title{font-size:13px;font-weight:600;color:var(--ui-text-primary);overflow:hidden;text-overflow:ellipsis}
.duckwork-plex-hero-sub{font-size:11px;color:var(--ui-text-tertiary);overflow:hidden;text-overflow:ellipsis}
.duckwork-plex-like{background:none;border:0;cursor:pointer;padding:0 2px;font-size:20px;line-height:1;color:var(--ui-text-quaternary)}
.duckwork-plex-like[data-on=true]{color:var(--ui-accent)}
.duckwork-plex-like:hover{color:var(--ui-accent)}
.duckwork-plex-grouprow{display:flex;align-items:center;gap:6px}
.duckwork-plex-grouprow>span:first-child{flex:1}
.duckwork-plex-mini{background:none;border:0;cursor:pointer;font-size:11px;color:var(--ui-text-tertiary);padding:0 4px}
.duckwork-plex-mini:hover{color:var(--ui-text-primary)}
.duckwork-plex-rowx{background:none;border:0;cursor:pointer;color:var(--ui-text-quaternary);font-size:13px;padding:0 6px;flex-shrink:0}
.duckwork-plex-rowx:hover{color:var(--ui-text-primary)}
.duckwork-plex-addto{display:flex;flex-direction:column;gap:2px;margin-top:4px;max-height:150px;overflow-y:auto}
.duckwork-plex-addto-row{background:none;border:0;cursor:pointer;text-align:left;font-size:12px;color:var(--ui-text-secondary);padding:3px 6px;border-radius:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.duckwork-plex-addto-row:hover{background:var(--chrome-action-hover);color:var(--ui-text-primary)}
.duckwork-plex-addto-new{display:flex;gap:4px;margin-top:2px}
.duckwork-plex-addto-new input{flex:1;min-width:0}
.duckwork-plex-transport{display:flex;align-items:center;gap:2px;height:28px;padding:2px 2px 0}
.duckwork-plex-transport-space{flex:1;min-width:6px}
.duckwork-plex-transport input{width:76px;min-width:0;height:3px;accent-color:var(--ui-accent);cursor:pointer}
.duckwork-plex-shuffle{font-size:11px;color:var(--ui-text-tertiary)}
.duckwork-plex-shuffle[data-on=true]{color:var(--ui-accent)}
.duckwork-plex-pager{display:flex;align-items:center;gap:6px;padding:4px 6px;font-size:11px;color:var(--ui-text-tertiary)}
.duckwork-plex-code{font-size:28px;font-weight:700;letter-spacing:.35em;text-align:center;color:var(--ui-text-primary);padding:6px 0 2px;font-variant-numeric:tabular-nums}
.duckwork-plex-signrow{display:flex;gap:4px;align-items:center}
.duckwork-plex-or{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ui-text-quaternary);text-align:center;padding:6px 0 2px}
.duckwork-plex-scrub{display:flex;align-items:center;gap:6px;padding:4px 4px 0}
.duckwork-plex-scrub input{flex:1;min-width:0;height:3px;accent-color:var(--ui-accent);cursor:pointer}
.duckwork-plex-time{font-size:10px;color:var(--ui-text-quaternary);font-variant-numeric:tabular-nums;flex-shrink:0}
.duckwork-plex-browsewrap{display:flex;min-height:0}
.duckwork-plex-browselist{flex:1;min-width:0;max-height:264px}
.duckwork-plex-azstrip{display:flex;flex-wrap:wrap;padding:1px 4px 3px}
.duckwork-plex-azstrip button{background:none;border:0;cursor:pointer;font-size:10px;line-height:1.7;color:var(--ui-text-quaternary);padding:0 4px;min-width:19px}
.duckwork-plex-azstrip button:disabled{opacity:.25;cursor:default}
.duckwork-plex-azstrip button:not(:disabled):hover{color:var(--ui-accent)}
`

function fileName(path) {
  if (typeof path !== 'string' || !path) return ''
  const parts = path.split(/[\\/]/)
  return (parts[parts.length - 1] || '').replace(/\.[a-z0-9]+$/i, '')
}

function formatDur(ms) {
  const s = Math.max(0, Math.round((Number(ms) || 0) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function mapTrack(m) {
  const media = Array.isArray(m.Media) ? m.Media[0] : null
  const part = media && Array.isArray(media.Part) ? media.Part[0] : null
  if (!part || typeof part.key !== 'string') return null
  const rawTitle = typeof m.title === 'string' ? m.title.trim() : ''
  return {
    ratingKey: String(m.ratingKey ?? ''),
    title: rawTitle || fileName(part.file) || 'Unknown track',
    artist: typeof m.grandparentTitle === 'string' ? m.grandparentTitle.trim() : '',
    album: typeof m.parentTitle === 'string' ? m.parentTitle.trim() : '',
    duration: Number(m.duration) || 0,
    thumb: m.grandparentThumb || m.thumb || null,
    partKey: part.key,
    userRating: typeof m.userRating === 'number' ? m.userRating : null,
  }
}

function cleanUrl(server, path) {
  return `${server.replace(/\/$/, '')}${path}`
}

async function plexJson(server, token, path, signal) {
  const sep = path.includes('?') ? '&' : '?'
  const res = await fetch(`${cleanUrl(server, path)}${sep}X-Plex-Token=${encodeURIComponent(token)}`, {
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
    credentials: 'omit',
    headers: { Accept: 'application/json' },
  })
  if (res.status === 401) throw new Error('auth')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function plexPut(server, token, path, signal) {
  const sep = path.includes('?') ? '&' : '?'
  const res = await fetch(`${cleanUrl(server, path)}${sep}X-Plex-Token=${encodeURIComponent(token)}`, {
    method: 'PUT',
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
    credentials: 'omit',
    headers: { Accept: 'application/json' },
  })
  if (res.status === 401) throw new Error('auth')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return true
}

function shuffled(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function createPlayer(ctx) {
  const server = atom(ctx.storage.get('server', 'http://127.0.0.1:32400'))
  const token = atom(ctx.storage.get('token', ''))
  const sectionId = atom(ctx.storage.get('sectionId', SECTION_FALLBACK))
  const conn = atom('idle')
  const connMsg = atom(EN.needToken)
  const queue = atom([])
  const index = atom(-1)
  const status = atom('paused')
  const storedVolume = ctx.storage.get('volume', 50)
  const volume = atom(Number.isFinite(storedVolume) ? Math.max(0, Math.min(100, storedVolume)) : 50)
  const shuffle = atom(ctx.storage.get('shuffle', false) === true)
  const open = atom(false)
  const ratingsTick = atom(0)
  const rateError = atom('')
  const repeat = atom(ctx.storage.get('repeat', 'off'))
  const sleepMins = atom(0)
  let sleepTimer = null
  let cachedMid = null
  let audio = null
  let generation = 0
  let disposed = false
  let lastVolume = volume.get() || 50
  const bus = new BroadcastChannel('duckwork:plex-music:playback')
  const windowId = crypto.randomUUID()

  const current = () => {
    const q = queue.get()
    const i = index.get()
    return i >= 0 && i < q.length ? q[i] : null
  }
  const streamUrl = item => `${cleanUrl(server.get(), item.partKey)}?X-Plex-Token=${encodeURIComponent(token.get())}`
  const artUrl = (item, size = 96) => {
    if (!item || !item.thumb) return null
    const sep = item.thumb.includes('?') ? '&' : '?'
    return `${cleanUrl(server.get(), item.thumb)}${sep}X-Plex-Token=${encodeURIComponent(token.get())}&width=${size}&height=${size}&fit=crop`
  }

  function stop(nextStatus = 'paused') {
    generation++
    setPlaybackState('none')
    if (audio) {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      audio.remove()
      audio = null
    }
    if (!disposed) status.set(nextStatus)
  }

  function playAt(i) {
    const q = queue.get()
    if (disposed || i < 0 || i >= q.length || !token.get()) return
    stop()
    const myGen = generation
    const item = q[i]
    index.set(i)
    updateMediaSession(item)
    status.set('connecting')
    bus.postMessage({ type: 'play', sender: windowId })
    const el = new Audio()
    audio = el
    el.dataset.duckworkPlexAudio = 'true'
    el.hidden = true
    el.preload = 'auto'
    el.volume = volume.get() / 100
    document.body.append(el)
    const alive = () => !disposed && myGen === generation
    el.addEventListener('playing', () => { if (alive()) { status.set('live'); setPlaybackState('playing') } })
    el.addEventListener('pause', () => { if (alive() && el.paused && !el.ended) { status.set('paused'); setPlaybackState('paused') } })
    el.addEventListener('error', () => { if (alive()) status.set('error') })
    el.addEventListener('ended', () => {
      if (!alive()) return
      const mode = repeat.get()
      if (mode === 'one') { playAt(i); return }
      if (i + 1 < queue.get().length) playAt(i + 1)
      else if (mode === 'all' && queue.get().length) playAt(0)
      else status.set('paused')
    })
    el.src = streamUrl(item)
    el.play().catch(() => { if (alive()) status.set('error') })
  }

  function playList(list, start = 0) {
    if (!list.length) return
    let q = [...list]
    let at = Math.max(0, Math.min(start, q.length - 1))
    if (shuffle.get() && q.length > 1) {
      const first = q[at]
      const rest = [...q.slice(0, at), ...q.slice(at + 1)]
      q = [first, ...shuffled(rest)]
      at = 0
    }
    queue.set(q)
    playAt(at)
  }

  function playShuffled(list) {
    if (!list.length) return
    queue.set(shuffled(list))
    playAt(0)
  }

  function toggle() {
    const item = current()
    if (status.get() === 'live' || status.get() === 'connecting') {
      if (audio) audio.pause()
      else stop()
    } else if (audio && item) {
      audio.play().catch(() => status.set('error'))
    } else if (item) {
      playAt(index.get())
    }
  }

  function next() {
    if (index.get() + 1 < queue.get().length) playAt(index.get() + 1)
  }

  function prev() {
    if (!audio && !current()) return
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0
      return
    }
    if (index.get() > 0) playAt(index.get() - 1)
    else if (audio) { audio.currentTime = 0 }
  }

  function setVolume(v) {
    const nv = Math.max(0, Math.min(100, Number(v) || 0))
    volume.set(nv)
    if (audio) audio.volume = nv / 100
    ctx.storage.set('volume', nv)
  }

  function mute() {
    if (volume.get()) { lastVolume = volume.get(); setVolume(0) }
    else setVolume(lastVolume)
  }

  function toggleShuffle() {
    const on = !shuffle.get()
    shuffle.set(on)
    ctx.storage.set('shuffle', on)
    if (on && queue.get().length - (index.get() + 1) > 1) {
      const q = queue.get()
      queue.set([...q.slice(0, index.get() + 1), ...shuffled(q.slice(index.get() + 1))])
    }
  }

  function cycleRepeat() {
    const order = ['off', 'all', 'one']
    const nextMode = order[(order.indexOf(repeat.get()) + 1) % order.length]
    repeat.set(nextMode)
    try { ctx.storage.set('repeat', nextMode) } catch {}
  }

  function removeAt(i) {
    const q = queue.get()
    if (i < 0 || i >= q.length) return
    const cur = index.get()
    if (i === cur) {
      const nq = q.filter((_, j) => j !== i)
      queue.set(nq)
      if (!nq.length) { stop(); index.set(-1); return }
      playAt(Math.min(i, nq.length - 1))
    } else {
      queue.set(q.filter((_, j) => j !== i))
      if (i < cur) index.set(cur - 1)
    }
  }

  function clearQueue() {
    stop()
    queue.set([])
    index.set(-1)
  }

  function cycleSleep() {
    const order = [0, 15, 30, 60, 90]
    const nextMins = order[(order.indexOf(sleepMins.get()) + 1) % order.length]
    if (sleepTimer) { clearTimeout(sleepTimer); sleepTimer = null }
    sleepMins.set(nextMins)
    if (nextMins > 0) {
      sleepTimer = setTimeout(() => { sleepTimer = null; sleepMins.set(0); stop() }, nextMins * 60000)
    }
  }

  function updateMediaSession(item) {
    try {
      if (!('mediaSession' in navigator)) return
      navigator.mediaSession.metadata = item ? new MediaMetadata({
        title: item.title || 'Plex Music',
        artist: item.artist || '',
        album: item.album || '',
        artwork: item.thumb ? [{ src: artUrl(item, 512), sizes: '512x512' }] : [],
      }) : null
    } catch {}
  }

  function setPlaybackState(st) {
    try {
      if ('mediaSession' in navigator) navigator.mediaSession.playbackState = st
    } catch {}
  }

  try {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.setActionHandler('play', () => { if (audio && audio.paused) audio.play().catch(() => {}) })
      navigator.mediaSession.setActionHandler('pause', () => { if (audio && !audio.paused) audio.pause() })
      navigator.mediaSession.setActionHandler('previoustrack', () => prev())
      navigator.mediaSession.setActionHandler('nexttrack', () => next())
    }
  } catch {}

  async function machineId() {
    if (cachedMid) return cachedMid
    const data = await plexJson(server.get(), token.get(), '/identity', null)
    cachedMid = data?.MediaContainer?.machineIdentifier || null
    if (!cachedMid) throw new Error('no server id')
    return cachedMid
  }

  async function trackUri(ratingKey) {
    const mid = await machineId()
    return `server://${mid}/com.plexapp.plugins.library/library/metadata/${ratingKey}`
  }

  async function createPlaylist(title, ratingKey) {
    const uri = await trackUri(ratingKey)
    const res = await fetch(
      `${cleanUrl(server.get(), '/playlists')}?title=${encodeURIComponent(title)}&type=audio&smart=0&uri=${encodeURIComponent(uri)}&X-Plex-Token=${encodeURIComponent(token.get())}`,
      { method: 'POST', headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(20000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    let key = null
    try {
      const data = await res.json()
      const meta = data?.MediaContainer?.Metadata ?? []
      if (meta.length) key = String(meta[0].ratingKey ?? '')
    } catch {}
    if (!key) {
      const lists = await plexJson(server.get(), token.get(), '/playlists', null)
      const found = (lists?.MediaContainer?.Metadata ?? []).filter(p => (p.title || '').trim() === title.trim()).pop()
      if (found) key = String(found.ratingKey ?? '')
    }
    if (!key) throw new Error('created but key unknown')
    ratingsTick.set(ratingsTick.get() + 1)
    return key
  }

  async function addToPlaylist(plKey, ratingKey) {
    const uri = await trackUri(ratingKey)
    await plexPut(server.get(), token.get(), `/playlists/${plKey}/items?uri=${encodeURIComponent(uri)}`, null)
    ratingsTick.set(ratingsTick.get() + 1)
    return true
  }

  async function renamePlaylist(plKey, title) {
    await plexPut(server.get(), token.get(), `/playlists/${plKey}?title=${encodeURIComponent(title)}`, null)
    ratingsTick.set(ratingsTick.get() + 1)
    return true
  }

  async function deletePlaylist(plKey) {
    const res = await fetch(`${cleanUrl(server.get(), `/playlists/${plKey}`)}?X-Plex-Token=${encodeURIComponent(token.get())}`, {
      method: 'DELETE', headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(15000),
    })
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)
    ratingsTick.set(ratingsTick.get() + 1)
    return true
  }

  async function testConnection() {
    const srv = server.get().replace(/\/$/, '')
    if (!token.get()) {
      conn.set('idle')
      connMsg.set(EN.needToken)
      return false
    }
    conn.set('idle')
    connMsg.set('Testing…')
    try {
      const data = await plexJson(srv, token.get(), '/library/sections', null)
      const dirs = data?.MediaContainer?.Directory ?? []
      const music = dirs.find(d => d.type === 'artist')
      if (!music) {
        conn.set('error')
        connMsg.set(EN.noMusic)
        return false
      }
      sectionId.set(String(music.key))
      ctx.storage.set('server', srv)
      ctx.storage.set('token', token.get())
      ctx.storage.set('sectionId', String(music.key))
      conn.set('ok')
      connMsg.set(EN.connected(String(music.key)))
      return true
    } catch (e) {
      conn.set('error')
      connMsg.set(e && e.message === 'auth' ? EN.badToken : EN.badServer)
      return false
    }
  }

  async function loadContainer(kind, ratingKey, signal) {
    const path = kind === 'artist'
      ? `/library/metadata/${ratingKey}/allLeaves`
      : `/library/metadata/${ratingKey}/children`
    const data = await plexJson(server.get(), token.get(), path, signal)
    const meta = data?.MediaContainer?.Metadata ?? []
    return meta.map(mapTrack).filter(Boolean)
  }

  async function fetchLiked(signal) {
    const liked = []
    const seen = new Set()
    for (let page = 0; page < 5; page++) {
      const data = await plexJson(
        server.get(), token.get(),
        `/library/sections/${sectionId.get()}/all?type=10&sort=userRating:desc&X-Plex-Container-Start=${page * 100}&X-Plex-Container-Size=100`,
        signal
      )
      const meta = data?.MediaContainer?.Metadata ?? []
      if (!meta.length) break
      let stopWalk = false
      for (const m of meta) {
        const r = typeof m.userRating === 'number' ? m.userRating : -1
        if (r < 9) { stopWalk = true; break }
        const mapped = mapTrack(m)
        if (mapped && !seen.has(mapped.partKey)) { seen.add(mapped.partKey); liked.push(mapped) }
      }
      if (stopWalk) break
    }
    return liked
  }

  async function rate(ratingKey, value) {
    rateError.set('')
    try {
      await plexPut(server.get(), token.get(), `/:/rate?key=${ratingKey}&identifier=com.plexapp.plugins.library&rating=${value}`, null)
      const next = value < 0 ? null : value
      queue.set(queue.get().map(q => (q.ratingKey === String(ratingKey) ? { ...q, userRating: next } : q)))
      // NOTE: smart-playlist counts come from live totalSize (see the
      // playlists query), so this refresh is enough — no settle polling.
      ratingsTick.set(ratingsTick.get() + 1)
      return true
    } catch {
      rateError.set(EN.rateError)
      return false
    }
  }

  function getTime() {
    const item = current()
    const fallback = item && item.duration ? item.duration / 1000 : 0
    const dur = (audio && Number.isFinite(audio.duration) && audio.duration > 0) ? audio.duration : fallback
    return { pos: audio ? audio.currentTime || 0 : 0, dur: dur || 0 }
  }

  function seek(sec) {
    if (!audio || !Number.isFinite(sec)) return
    try {
      audio.currentTime = Math.max(0, Math.min(sec, (audio.duration && Number.isFinite(audio.duration)) ? audio.duration : sec))
    } catch { /* noop */ }
  }

  async function shuffleAll() {
    const srv = server.get()
    const tok = token.get()
    const sec = sectionId.get()
    const head = await plexJson(srv, tok, `/library/sections/${sec}/all?type=10&X-Plex-Container-Start=0&X-Plex-Container-Size=0`, null)
    const total = head?.MediaContainer?.totalSize ?? 0
    if (!total) throw new Error('empty')
    const size = 100
    const starts = new Set()
    const span = Math.max(1, total - size)
    while (starts.size < 4) starts.add(Math.floor(Math.random() * span))
    const seen = new Set()
    const out = []
    for (const s of starts) {
      const d = await plexJson(srv, tok, `/library/sections/${sec}/all?type=10&X-Plex-Container-Start=${s}&X-Plex-Container-Size=${size}`, null)
      for (const m of d?.MediaContainer?.Metadata ?? []) {
        const mapped = mapTrack(m)
        if (mapped && !seen.has(mapped.partKey)) { seen.add(mapped.partKey); out.push(mapped) }
      }
    }
    if (!out.length) throw new Error('empty')
    queue.set(shuffled(out))
    playAt(0)
    return out.length
  }

  async function signOut() {
    token.set('')
    try { ctx.storage.remove('token') } catch {}
    conn.set('idle')
    connMsg.set(EN.needToken)
  }

  bus.onmessage = event => {
    if (event.data?.type === 'play' && event.data.sender !== windowId) stop()
  }

  function dispose() {
    disposed = true
    stop()
    try { bus.close() } catch { /* noop */ }
  }

  return {
    server, token, sectionId, conn, connMsg, queue, index, status, volume, shuffle, open,
    ratingsTick, rateError,
    current, streamUrl, artUrl, playAt, playList, playShuffled, toggle, next, prev,
    setVolume, mute, toggleShuffle, testConnection, loadContainer, fetchLiked, rate, dispose,
    getTime, seek, shuffleAll, signOut,
    repeat, cycleRepeat, sleepMins, cycleSleep, removeAt, clearQueue,
    createPlaylist, addToPlaylist, renamePlaylist, deletePlaylist,
  }
}

function NextArrow({ flip = false }) {
  return jsx('span', { className: `duckwork-plex-next${flip ? ' duckwork-plex-next-flip' : ''}`, 'aria-hidden': true, children: [
    jsx(icons.Play, { style: { width: 7, height: 12, flexShrink: 0 }, fill: 'currentColor' }),
    jsx(icons.Play, { style: { width: 7, height: 12, flexShrink: 0, marginLeft: -2 }, fill: 'currentColor' }),
  ] })
}

function PrevArrow() {
  return jsx(NextArrow, { flip: true })
}

function SmallAction({ label, icon, onClick, size = 'micro', pressed, className, busy = false }) {
  return jsx(Tip, { label, children: jsx(Button, {
    variant: 'ghost', size, className: `duckwork-plex-action ${className ?? ''}`,
    'aria-label': label, 'aria-pressed': pressed, onClick,
    children: jsx('span', { className: 'duckwork-plex-action-icon', children: busy ? jsx(GlyphSpinner, { ariaLabel: label }) : jsx(icon, {}) }),
  }) })
}

function LikeButton({ liked, onToggle, t }) {
  return jsx('button', {
    className: 'duckwork-plex-like', 'data-on': !!liked,
    'aria-label': liked ? t('unlike') : t('like'), 'aria-pressed': !!liked,
    title: liked ? t('unlike') : t('like'),
    onClick: e => { e.stopPropagation(); onToggle() },
    children: liked ? '♥' : '♡',
  })
}

function Transport({ player, t }) {
  const status = useValue(player.status)
  const volume = useValue(player.volume)
  const shuffleOn = useValue(player.shuffle)
  const repeat = useValue(player.repeat)
  const repeatLabel = repeat === 'all' ? t('repeatAll') : repeat === 'one' ? t('repeatOne') : t('repeatOff')
  const repeatText = repeat === 'all' ? 'Repeat all' : repeat === 'one' ? 'Repeat 1' : 'Repeat'
  return jsxs('div', { className: 'duckwork-plex-transport', children: [
    jsx(SmallAction, { label: t('prev'), icon: PrevArrow, onClick: player.prev }),
    jsx(SmallAction, { label: t(status === 'live' || status === 'connecting' ? 'pause' : 'play'), icon: status === 'live' || status === 'connecting' ? icons.Pause : icons.Play, busy: status === 'connecting', size: 'icon-xs', onClick: player.toggle }),
    jsx(SmallAction, { label: t('next'), icon: NextArrow, size: 'icon-xs', onClick: player.next }),
    jsx('button', {
      className: 'duckwork-plex-shuffle', 'data-on': shuffleOn,
      'aria-label': t(shuffleOn ? 'shuffleOn' : 'shuffleOff'), 'aria-pressed': shuffleOn,
      onClick: player.toggleShuffle, style: { background: 'none', border: 0, cursor: 'pointer', padding: '0 4px' },
      children: t('shuffle'),
    }),
    jsx('button', {
      className: 'duckwork-plex-shuffle', 'data-on': repeat !== 'off',
      'aria-label': repeatLabel,
      onClick: player.cycleRepeat, style: { background: 'none', border: 0, cursor: 'pointer', padding: '0 4px' },
      children: repeatText,
    }),
    jsx('span', { className: 'duckwork-plex-transport-space' }),
    jsx(SmallAction, { label: t(volume ? 'mute' : 'unmute'), icon: volume ? icons.Volume2 : icons.VolumeX, onClick: player.mute, size: 'icon-xs' }),
    jsx('input', { type: 'range', min: 0, max: 100, step: 1, value: volume, 'aria-label': t('volume'), onChange: e => player.setVolume(Number(e.target.value)) }),
  ] })
}

function TrackRows({ tracks, player, t, currentKey }) {
  return tracks.map((tr, i) => {
    const isCurrent = currentKey && tr.partKey === currentKey
    const sub = [tr.artist, tr.album].filter(Boolean).join(' · ')
    return jsx('div', { className: 'duckwork-plex-row', 'data-current': isCurrent, children:
      jsxs(RowButton, {
        className: 'duckwork-plex-row-main',
        'aria-label': `${tr.title}${sub ? ` — ${sub}` : ''}`,
        'aria-current': isCurrent ? 'true' : undefined,
        onClick: () => player.playList(tracks, i),
        children: [
          player.artUrl(tr, 56) && jsx('img', { className: 'duckwork-plex-art', src: player.artUrl(tr, 56), alt: '', loading: 'lazy' }),
          jsxs('span', { className: 'duckwork-plex-row-copy', children: [
            jsx('span', { className: 'duckwork-plex-row-name', children: tr.title }),
            sub && jsx('span', { className: 'duckwork-plex-row-sub', children: sub }),
          ] }),
          jsx(LikeButton, { liked: tr.userRating === 10, t, onToggle: () => player.rate(tr.ratingKey, tr.userRating === 10 ? -1 : 10) }),
          tr.duration > 0 && jsx('span', { className: 'duckwork-plex-dur', children: formatDur(tr.duration) }),
        ],
      }),
    }, tr.partKey)
  })
}

function SearchTab({ player, t }) {
  const serverVal = useValue(player.server)
  const sectionVal = useValue(player.sectionId)
  const conn = useValue(player.conn)
  const tick = useValue(player.ratingsTick)
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const current = index >= 0 && index < queue.length ? queue[index] : null
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [loadError, setLoadError] = useState('')
  const [loadingKey, setLoadingKey] = useState(null)

  const result = useQuery({
    queryKey: [ID, 'search', serverVal, sectionVal, query, tick],
    queryFn: async ({ signal }) => {
      const data = await plexJson(
        serverVal, player.token.get(),
        `/hubs/search?query=${encodeURIComponent(query)}&sectionId=${sectionVal}&limit=25`, signal
      )
      const hubs = data?.MediaContainer?.Hub ?? []
      const tracks = []
      const containers = []
      for (const hub of hubs) {
        const meta = hub.Metadata ?? []
        if (hub.type === 'track') {
          for (const m of meta) {
            const mapped = mapTrack(m)
            if (mapped) tracks.push(mapped)
          }
        } else if (hub.type === 'artist' || hub.type === 'album') {
          for (const m of meta) {
            containers.push({
              kind: hub.type,
              ratingKey: String(m.ratingKey ?? ''),
              title: (m.title || '').trim() || 'Unknown',
              sub: hub.type === 'artist'
                ? 'Artist'
                : ([m.parentTitle, m.grandparentTitle].filter(Boolean).join(' · ') || 'Album'),
              thumb: m.thumb || m.grandparentThumb || null,
            })
          }
        }
      }
      return { tracks: tracks.slice(0, 30), containers: containers.slice(0, 12) }
    },
    enabled: query.length >= 2 && text === query && conn === 'ok',
    staleTime: 60000,
    retry: false,
  })

  const openContainer = async c => {
    if (!c.ratingKey) return
    setLoadingKey(`${c.kind}:${c.ratingKey}`)
    setLoadError('')
    try {
      const tracks = await player.loadContainer(c.kind, c.ratingKey, null)
      if (!tracks.length) setLoadError(t('loadError'))
      else player.playList(tracks, 0)
    } catch {
      setLoadError(t('loadError'))
    }
    setLoadingKey(null)
  }

  const pending = text.length >= 2 && (text !== query || result.isFetching)
  const tracks = result.data?.tracks ?? []
  const containers = result.data?.containers ?? []

  return jsxs('div', { children: [
    jsx('div', { className: 'duckwork-plex-search', children: jsx(SearchField, {
      value: text,
      onChange: v => {
        setText(v)
        setLoadError('')
        if (v.trim().length >= 2) setQuery(v.trim())
      },
      placeholder: t('search'),
      containerClassName: 'duckwork-plex-search-field',
      trailingAction: pending ? jsx('span', { className: 'duckwork-plex-search-loader', children: jsx(GlyphSpinner, { ariaLabel: 'searching' }) }) : null,
    }) }),
    text.trim().length >= 2 && jsxs('div', { children: [
      tracks.length > 0 && jsx('div', { className: 'duckwork-plex-group', children: t('tracks') }),
      tracks.length > 0 && jsx('div', { className: 'duckwork-plex-list', children:
        TrackRows({ tracks, player, t, currentKey: current?.partKey }),
      }),
      containers.length > 0 && jsx('div', { className: 'duckwork-plex-group', children: t('artistsAlbums') }),
      containers.length > 0 && jsx('div', { className: 'duckwork-plex-list', children:
        containers.map(c => {
          const key = `${c.kind}:${c.ratingKey}`
          return jsx('div', { className: 'duckwork-plex-row', children:
            jsxs(RowButton, {
              className: 'duckwork-plex-row-main',
              'aria-label': `${c.title} — ${c.sub}`,
              onClick: () => openContainer(c),
              children: [
                c.thumb && jsx('img', { className: 'duckwork-plex-art', src: player.artUrl({ thumb: c.thumb }, 56), alt: '', loading: 'lazy' }),
                jsxs('span', { className: 'duckwork-plex-row-copy', children: [
                  jsx('span', { className: 'duckwork-plex-row-name', children: c.title }),
                  jsx('span', { className: 'duckwork-plex-row-sub', children: c.sub }),
                ] }),
                loadingKey === key && jsx(GlyphSpinner, { ariaLabel: c.title }),
              ],
            }),
          }, key)
        }),
      }),
      !pending && !tracks.length && !containers.length && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: t('noResults') }),
    ] }),
    loadError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: loadError }),
  ] })
}

function PlaylistsTab({ player, t, goPlaying }) {
  const serverVal = useValue(player.server)
  const conn = useValue(player.conn)
  const tick = useValue(player.ratingsTick)
  const [loadingKey, setLoadingKey] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [shuffling, setShuffling] = useState(false)
  const [naming, setNaming] = useState(false)
  const [newName, setNewName] = useState('')
  const [renaming, setRenaming] = useState(null)
  const [renameName, setRenameName] = useState('')
  const [confirmDel, setConfirmDel] = useState(null)
  const [opBusy, setOpBusy] = useState(false)
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const current = index >= 0 && index < queue.length ? queue[index] : null

  const doShuffleAll = async () => {
    setShuffling(true)
    setLoadError('')
    try {
      await player.shuffleAll()
      goPlaying()
    } catch {
      setLoadError(t('loadError'))
    }
    setShuffling(false)
  }

  const result = useQuery({
    queryKey: [ID, 'playlists', serverVal, tick],
    queryFn: async ({ signal }) => {
      const data = await plexJson(serverVal, player.token.get(), '/playlists', signal)
      const meta = data?.MediaContainer?.Metadata ?? []
      const rows = meta
        .filter(p => !p.playlistType || p.playlistType === 'audio')
        .map(p => ({
          ratingKey: String(p.ratingKey ?? ''),
          title: (p.title || '').trim() || 'Untitled playlist',
          count: Number(p.leafCount) || 0,
          duration: Number(p.duration) || 0,
          smart: p.smart === true || p.smart === 1 || p.smart === '1',
          thumb: p.composite || p.thumb || null,
        }))
      // Smart-playlist leafCount goes stale server-side (Plex only
      // recalculates it on playlist refresh) while the items are live.
      // Ask each smart row for its true size: Size=0 returns totalSize
      // with zero item payload.
      await Promise.all(rows.filter(r => r.smart && r.ratingKey).map(async r => {
        try {
          const c = await plexJson(serverVal, player.token.get(), `/playlists/${r.ratingKey}/items?X-Plex-Container-Start=0&X-Plex-Container-Size=0`, signal)
          const n = Number(c?.MediaContainer?.totalSize)
          if (Number.isFinite(n)) r.count = n
        } catch {}
      }))
      return rows
    },
    enabled: conn === 'ok',
    staleTime: 10000,
    refetchOnMount: 'always',
    retry: false,
  })

  const openPlaylist = async pl => {
    if (!pl.ratingKey) return
    setLoadingKey(pl.ratingKey)
    setLoadError('')
    try {
      const data = await plexJson(serverVal, player.token.get(),
        `/playlists/${pl.ratingKey}/items?X-Plex-Container-Start=0&X-Plex-Container-Size=500`, null)
      const tracks = (data?.MediaContainer?.Metadata ?? []).map(mapTrack).filter(Boolean)
      if (!tracks.length) setLoadError(t('loadError'))
      else { player.playList(tracks, 0); goPlaying() }
    } catch {
      setLoadError(t('loadError'))
    }
    setLoadingKey(null)
  }

  const lists = result.data ?? []
  const doCreate = async () => {
    const nm = newName.trim()
    if (!nm || opBusy || !current) return
    setOpBusy(true)
    setLoadError('')
    try { await player.createPlaylist(nm, current.ratingKey); setNewName(''); setNaming(false) }
    catch { setLoadError(t('addFailed')) }
    setOpBusy(false)
  }
  const doRename = async pl => {
    const nm = renameName.trim()
    if (!nm || opBusy) return
    setOpBusy(true)
    setLoadError('')
    try { await player.renamePlaylist(pl.ratingKey, nm); setRenaming(null) }
    catch { setLoadError(t('addFailed')) }
    setOpBusy(false)
  }
  const doDelete = async pl => {
    if (confirmDel !== pl.ratingKey) { setConfirmDel(pl.ratingKey); return }
    setConfirmDel(null)
    if (opBusy) return
    setOpBusy(true)
    setLoadError('')
    try { await player.deletePlaylist(pl.ratingKey) }
    catch { setLoadError(t('addFailed')) }
    setOpBusy(false)
  }
  return jsxs('div', { children: [
    jsxs('div', { className: 'duckwork-plex-pager', children: [
      jsx(Button, { size: 'micro', onClick: doShuffleAll, disabled: shuffling || conn !== 'ok', children: shuffling ? jsx(GlyphSpinner, { ariaLabel: t('shuffleAll') }) : t('shuffleAll') }),
      naming
        ? jsxs('span', { style: { display: 'inline-flex', gap: 4, alignItems: 'center' }, children: [
            jsx('input', { type: 'text', value: newName, 'aria-label': t('playlistName'), placeholder: t('playlistName'), onChange: e => setNewName(e.target.value), onKeyDown: e => { if (e.key === 'Enter') doCreate() }, spellCheck: false, style: { width: 130 } }),
            jsx(Button, { size: 'micro', onClick: doCreate, disabled: opBusy || !newName.trim() || !current, title: !current ? t('needSong') : undefined, children: t('create') }),
            jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => { setNaming(false); setNewName('') }, children: '×' }),
          ] })
        : jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => setNaming(true), children: t('newPlaylist') }),
    ] }),
    result.isError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: t('loadError') }),
    !result.isFetching && !result.isError && !lists.length && jsx('div', { className: 'duckwork-plex-error', children: t('playlistsEmpty') }),
    lists.length > 0 && jsx('div', { className: 'duckwork-plex-list', children:
      lists.map(pl => {
        const sub = `${t('songsCount', pl.count)}${pl.smart ? ` · ${t('smart')}` : ''}`
        if (renaming === pl.ratingKey && !pl.smart) {
          return jsxs('div', { className: 'duckwork-plex-row', children: [
            jsx('input', { type: 'text', value: renameName, 'aria-label': t('newName'), onChange: e => setRenameName(e.target.value), onKeyDown: e => { if (e.key === 'Enter') doRename(pl) }, spellCheck: false, style: { flex: 1, minWidth: 0 } }),
            jsx(Button, { size: 'micro', onClick: () => doRename(pl), disabled: opBusy || !renameName.trim(), children: t('save') }),
            jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => setRenaming(null), children: '×' }),
          ] }, pl.ratingKey)
        }
        return jsx('div', { className: 'duckwork-plex-row', children: [
          jsx(RowButton, {
            className: 'duckwork-plex-row-main',
            'aria-label': `${pl.title} — ${sub}`,
            onClick: () => openPlaylist(pl),
            children: [
              pl.thumb && jsx('img', { className: 'duckwork-plex-art', src: player.artUrl({ thumb: pl.thumb }, 56), alt: '', loading: 'lazy', onError: e => { e.currentTarget.style.display = 'none' } }),
              jsxs('span', { className: 'duckwork-plex-row-copy', children: [
                jsx('span', { className: 'duckwork-plex-row-name', children: pl.title }),
                jsx('span', { className: 'duckwork-plex-row-sub', children: sub }),
              ] }),
              loadingKey === pl.ratingKey && jsx(GlyphSpinner, { ariaLabel: pl.title }),
            ],
          }),
          !pl.smart && jsx('button', { className: 'duckwork-plex-rowx', title: t('rename'), 'aria-label': t('rename'), onClick: () => { setRenameName(pl.title); setRenaming(pl.ratingKey) }, children: '✎' }),
          !pl.smart && jsx('button', { className: 'duckwork-plex-rowx', title: t('delete'), 'aria-label': t('delete'), onClick: () => doDelete(pl), children: confirmDel === pl.ratingKey ? t('confirmDelete') : '×' }),
        ] }, pl.ratingKey)
      }),
    }),
    loadError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: loadError }),
  ] })
}

function BrowseTab({ player, t }) {
  const serverVal = useValue(player.server)
  const sectionVal = useValue(player.sectionId)
  const conn = useValue(player.conn)
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const current = index >= 0 && index < queue.length ? queue[index] : null
  const [stack, setStack] = useState([{ view: 'artists' }])
  const [visible, setVisible] = useState(60)
  const [artistShuffle, setArtistShuffle] = useState(false)
  const [pendingJump, setPendingJump] = useState(null)
  const listRef = useRef(null)
  const top = stack[stack.length - 1]

  const artists = useQuery({
    queryKey: [ID, 'artists', serverVal, sectionVal],
    queryFn: async ({ signal }) => {
      const data = await plexJson(serverVal, player.token.get(),
        `/library/sections/${sectionVal}/all?X-Plex-Container-Start=0&X-Plex-Container-Size=2000`, signal)
      const mc = data?.MediaContainer ?? {}
      return {
        total: mc.totalSize ?? (mc.Metadata ?? []).length,
        items: (mc.Metadata ?? []).map(m => ({
          ratingKey: String(m.ratingKey ?? ''),
          title: (m.title || '').trim() || 'Unknown artist',
          sort: ((m.titleSort || m.title || '').trim().charAt(0) || '#').toUpperCase(),
          thumb: m.thumb || null,
        })),
      }
    },
    enabled: conn === 'ok',
    staleTime: 300000,
    retry: false,
  })

  const artistItems = artists.data?.items ?? []
  const railLetters = ['#', ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
  const present = new Set(artistItems.map(a => (/[A-Z]/.test(a.sort) ? a.sort : '#')))

  useEffect(() => {
    if (pendingJump == null) return
    const node = listRef.current?.querySelector(`[data-aidx="${pendingJump}"]`)
    if (node) node.scrollIntoView({ block: 'start' })
    setPendingJump(null)
  }, [pendingJump, visible, artistItems.length])

  const jumpTo = letter => {
    const idx = artistItems.findIndex(a => (/[A-Z]/.test(a.sort) ? a.sort : '#') === letter)
    if (idx < 0) return
    setVisible(Math.max(60, idx + 40))
    setPendingJump(idx)
  }

  const onBrowseScroll = e => {
    const el = e.currentTarget
    if (el.scrollTop + el.clientHeight > el.scrollHeight - 300) {
      setVisible(v => (v < artistItems.length ? Math.min(artistItems.length, v + 80) : v))
    }
  }

  const drill = useQuery({
    queryKey: [ID, 'drill', serverVal, top.view, top.ratingKey],
    queryFn: async ({ signal }) => {
      const data = await plexJson(serverVal, player.token.get(),
        `/library/metadata/${top.ratingKey}/children`, signal)
      const meta = data?.MediaContainer?.Metadata ?? []
      if (top.view === 'albums') {
        return {
          albums: meta.map(m => ({
            ratingKey: String(m.ratingKey ?? ''),
            title: (m.title || '').trim() || 'Unknown album',
            sub: m.parentTitle || (m.year ? String(m.year) : '') || '',
            thumb: m.thumb || null,
          })),
        }
      }
      return { tracks: meta.map(mapTrack).filter(Boolean) }
    },
    enabled: conn === 'ok' && (top.view === 'albums' || top.view === 'tracks'),
    staleTime: 120000,
    retry: false,
  })

  const busy = artists.isFetching || drill.isFetching
  const total = artists.data?.total ?? 0

  return jsxs('div', { children: [
    jsx(SearchTab, { player, t }),
    top.view !== 'artists' && jsx('div', { className: 'duckwork-plex-pager', children:
      jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => setStack(stack.slice(0, -1)), children: `← ${t('back')}${top.title ? ` · ${top.title}` : ''}` }),
    }),
    top.view === 'artists' && jsxs('div', { children: [
      jsx('div', { className: 'duckwork-plex-group', children: `${t('artists')}${total ? ` · ${total}` : ''}` }),
      artists.isError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: t('loadError') }),
      jsx('div', { className: 'duckwork-plex-azstrip', 'aria-label': 'Jump to letter', children:
        railLetters.map(L => jsx('button', {
          disabled: !present.has(L),
          'aria-label': `Artists starting with ${L}`,
          onClick: () => jumpTo(L),
          children: L,
        }, L)),
      }),
      jsx('div', { ref: listRef, className: 'duckwork-plex-list duckwork-plex-browselist', onScroll: onBrowseScroll, children:
          artistItems.slice(0, visible).map((a, i) => jsx('div', { className: 'duckwork-plex-row', 'data-aidx': i, children:
            jsxs(RowButton, {
              className: 'duckwork-plex-row-main',
              'aria-label': a.title,
              onClick: () => setStack([...stack, { view: 'albums', ratingKey: a.ratingKey, title: a.title }]),
              children: [
                a.thumb && jsx('img', { className: 'duckwork-plex-art', src: player.artUrl({ thumb: a.thumb }, 56), alt: '', loading: 'lazy' }),
                jsx('span', { className: 'duckwork-plex-row-copy', children:
                  jsx('span', { className: 'duckwork-plex-row-name', children: a.title }),
                }),
              ],
            }),
          }, a.ratingKey)),
        }),
    ] }),
    top.view === 'albums' && jsxs('div', { children: [
      jsxs('div', { className: 'duckwork-plex-pager', children: [
        jsx('span', { className: 'duckwork-plex-group', style: { padding: 0, flex: 1 }, children: top.title || t('albums') }),
        jsx(Button, { size: 'micro', disabled: artistShuffle, onClick: async () => {
          if (!top.ratingKey || artistShuffle) return
          setArtistShuffle(true)
          try {
            const tracks = await player.loadContainer('artist', top.ratingKey, null)
            if (tracks.length) player.playShuffled(tracks)
          } catch { /* noop */ }
          setArtistShuffle(false)
        }, children: artistShuffle ? jsx(GlyphSpinner, { ariaLabel: t('shuffleArtist') }) : t('shuffleArtist') }),
      ] }),
      drill.isError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: t('loadError') }),
      jsx('div', { className: 'duckwork-plex-list', children:
        (drill.data?.albums ?? []).map(al => jsx('div', { className: 'duckwork-plex-row', children:
          jsxs(RowButton, {
            className: 'duckwork-plex-row-main',
            'aria-label': al.title,
            onClick: () => setStack([...stack, { view: 'tracks', ratingKey: al.ratingKey, title: al.title }]),
            children: [
              al.thumb && jsx('img', { className: 'duckwork-plex-art', src: player.artUrl({ thumb: al.thumb }, 56), alt: '', loading: 'lazy' }),
              jsxs('span', { className: 'duckwork-plex-row-copy', children: [
                jsx('span', { className: 'duckwork-plex-row-name', children: al.title }),
                al.sub && jsx('span', { className: 'duckwork-plex-row-sub', children: al.sub }),
              ] }),
            ],
          }),
        }, al.ratingKey)),
      }),
    ] }),
    top.view === 'tracks' && jsxs('div', { children: [
      jsxs('div', { className: 'duckwork-plex-pager', children: [
        jsx('span', { className: 'duckwork-plex-group', style: { padding: 0, flex: 1 }, children: top.title || t('albumTracks') }),
        drill.data?.tracks?.length > 1 && jsx(Button, { size: 'micro', onClick: () => player.playShuffled(drill.data.tracks), children: t('shuffleAlbum') }),
      ] }),
      drill.isError && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: t('loadError') }),
      drill.data?.tracks && jsx('div', { className: 'duckwork-plex-list', children:
        TrackRows({ tracks: drill.data.tracks, player, t, currentKey: current?.partKey }),
      }),
    ] }),
    busy && jsx('div', { className: 'duckwork-plex-pager', children: jsx(GlyphSpinner, { ariaLabel: 'loading' }) }),
  ] })
}

function fmtSec(s) {
  s = Math.max(0, Math.floor(Number(s) || 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function Scrub({ player, t }) {
  const index = useValue(player.index)
  const [now, setNow] = useState(() => player.getTime())
  useEffect(() => {
    setNow(player.getTime())
    const id = setInterval(() => setNow(player.getTime()), 500)
    return () => clearInterval(id)
  }, [player, index])
  if (!now.dur) return null
  const max = Math.floor(now.dur)
  return jsxs('div', { className: 'duckwork-plex-scrub', children: [
    jsx('span', { className: 'duckwork-plex-time', children: fmtSec(now.pos) }),
    jsx('input', {
      type: 'range', min: 0, max, step: 1,
      value: Math.min(Math.floor(now.pos), max),
      'aria-label': t('seek'),
      onChange: e => { const v = Number(e.target.value); player.seek(v); setNow({ pos: v, dur: now.dur }) },
    }),
    jsx('span', { className: 'duckwork-plex-time', children: fmtSec(now.dur) }),
  ] })
}

function AddTo({ player, t, ratingKey }) {
  const [open, setOpen] = useState(false)
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState('')
  const serverVal = useValue(player.server)
  const conn = useValue(player.conn)
  const tick = useValue(player.ratingsTick)
  const lists = useQuery({
    queryKey: [ID, 'playlists', serverVal, tick],
    queryFn: async ({ signal }) => {
      const data = await plexJson(serverVal, player.token.get(), '/playlists', signal)
      const meta = data?.MediaContainer?.Metadata ?? []
      return meta
        .filter(p => !p.playlistType || p.playlistType === 'audio')
        .map(p => ({ ratingKey: String(p.ratingKey ?? ''), title: (p.title || '').trim() || 'Untitled' }))
    },
    enabled: open && conn === 'ok',
    staleTime: 10000,
    retry: false,
  })
  const doAdd = async plKey => {
    if (busy || !plKey) return
    setBusy(true)
    try { await player.addToPlaylist(plKey, ratingKey); setDone(t('added')); setOpen(false) }
    catch { setDone(t('addFailed')) }
    setBusy(false)
  }
  const doCreate = async () => {
    const nm = name.trim()
    if (!nm || busy) return
    setBusy(true)
    try { await player.createPlaylist(nm, ratingKey); setName(''); setNaming(false); setOpen(false); setDone(t('created')) }
    catch { setDone(t('addFailed')) }
    setBusy(false)
  }
  return jsxs('div', { children: [
    jsx(Button, { size: 'micro', variant: 'ghost', onClick: () => { setOpen(!open); setDone('') }, children: t('addTo') }),
    open && jsxs('div', { className: 'duckwork-plex-addto', children: [
      lists.isFetching && jsx(GlyphSpinner, { ariaLabel: t('addTo') }),
      ...(lists.data ?? []).map(pl => jsx('button', {
        className: 'duckwork-plex-addto-row', disabled: busy,
        onClick: () => doAdd(pl.ratingKey), children: pl.title,
      }, pl.ratingKey)),
      naming
        ? jsxs('div', { className: 'duckwork-plex-addto-new', children: [
            jsx('input', { type: 'text', value: name, 'aria-label': t('playlistName'), placeholder: t('playlistName'), onChange: e => setName(e.target.value), onKeyDown: e => { if (e.key === 'Enter') doCreate() }, spellCheck: false }),
            jsx(Button, { size: 'micro', onClick: doCreate, disabled: busy || !name.trim(), children: t('create') }),
          ] })
        : jsx('button', { className: 'duckwork-plex-addto-row', onClick: () => setNaming(true), children: t('newPlaylist') }),
    ] }),
    done && jsx('div', { className: 'duckwork-plex-row-sub', children: done }),
  ] })
}

function PlayingTab({ player, t }) {
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const current = index >= 0 && index < queue.length ? queue[index] : null
  const sleepMins = useValue(player.sleepMins)
  // Anchor the queue list on the current song at open: put its row at the
  // top of the list viewport (runs once per mount — popover content mounts
  // fresh each open). Free scroll up/down afterwards is untouched.
  const anchorCurrent = el => {
    if (!el) return
    const list = el.closest('.duckwork-plex-list')
    if (!list) return
    requestAnimationFrame(() => {
      const lr = list.getBoundingClientRect()
      const rr = el.getBoundingClientRect()
      list.scrollTop += (rr.top - lr.top)
    })
  }

  if (!current) return jsx('div', { className: 'duckwork-plex-error', children: t('emptyQueue') })

  return jsxs('div', { children: [
    jsxs('div', { className: 'duckwork-plex-hero', children: [
      player.artUrl(current, 240) && jsx('img', { className: 'duckwork-plex-bigart', src: player.artUrl(current, 240), alt: '' }),
      jsxs('div', { style: { minWidth: 0 }, children: [
        jsx('div', { className: 'duckwork-plex-hero-title', children: current.title }),
        current.artist && jsx('div', { className: 'duckwork-plex-hero-sub', children: current.artist }),
        current.album && jsx('div', { className: 'duckwork-plex-hero-sub', children: current.album }),
        jsxs('div', { style: { marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }, children: [
          jsx(LikeButton, { liked: current.userRating === 10, t, onToggle: () => player.rate(current.ratingKey, current.userRating === 10 ? -1 : 10) }),
          jsx(AddTo, { player, t, ratingKey: current.ratingKey }),
        ] }),
      ] }),
    ] }),
    jsx(Scrub, { player, t }),
    jsx(Transport, { player, t }),
    queue.length > 1 && jsxs('div', { children: [
      jsxs('div', { className: 'duckwork-plex-grouprow', children: [
        jsx('span', { className: 'duckwork-plex-group', children: `${t('queue')} · ${queue.length}` }),
        jsx('button', { className: 'duckwork-plex-mini', title: t('sleepTimer'), onClick: player.cycleSleep, children: sleepMins > 0 ? `${sleepMins}m` : t('sleepOff') }),
        jsx('button', { className: 'duckwork-plex-mini', onClick: player.clearQueue, children: t('clearQueue') }),
      ] }),
      jsx('div', { className: 'duckwork-plex-list', children:
        queue.slice(0, 200).map((q, i) => jsx('div', { className: 'duckwork-plex-row', 'data-current': i === index, ref: i === index ? anchorCurrent : undefined, children: [
          jsx(RowButton, {
            className: 'duckwork-plex-row-main', 'aria-label': q.title,
            'aria-current': i === index ? 'true' : undefined,
            onClick: () => player.playAt(i),
            children: jsxs('span', { className: 'duckwork-plex-row-copy', children: [
              jsx('span', { className: 'duckwork-plex-row-name', children: `${i === index ? '▶ ' : ''}${q.title}` }),
              q.artist && jsx('span', { className: 'duckwork-plex-row-sub', children: q.artist }),
            ] }),
          }),
          jsx('button', { className: 'duckwork-plex-rowx', 'aria-label': t('remove'), title: t('remove'), onClick: e => { e.stopPropagation(); player.removeAt(i) }, children: '×' }),
        ] }, `${q.partKey}:${i}`)),
      }),
    ] }),
  ] })
}

// Crash boundary so a Panel render error shows its message instead of a vanishing popup
class PanelCrash extends Component {
  constructor(p) { super(p); this.state = { err: null } }
  static getDerivedStateFromError(err) { return { err } }
  render() {
    if (this.state.err) return jsx('div', { style: { padding: 16, color: '#ff8080', fontSize: 12, maxWidth: 360 }, children: `PANEL CRASH: ${String(this.state.err && this.state.err.message || this.state.err)}` })
    return this.props.children
  }
}

function Panel({ player, ctx }) {
  const t = usePluginI18n(ID)
  const conn = useValue(player.conn)
  const connMsg = useValue(player.connMsg)
  const serverVal = useValue(player.server)
  const rateErr = useValue(player.rateError)
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const current = index >= 0 && index < queue.length ? queue[index] : null
  const [tab, setTab] = useState('playing')
  const [showSettings, setShowSettings] = useState(conn !== 'ok')
  const [draftServer, setDraftServer] = useState(serverVal)
  const [draftToken, setDraftToken] = useState('')
  const [testing, setTesting] = useState(false)
  const fileRef = useRef(null)

  const doSave = async (srv, tok) => {
    setTesting(true)
    player.server.set((srv || '').trim().replace(/\/$/, '') || 'http://127.0.0.1:32400')
    if ((tok || '').trim()) player.token.set(tok.trim())
    const ok = await player.testConnection()
    if (ok) { setDraftToken(''); setShowSettings(false) }
    setTesting(false)
    return ok
  }
  const saveTest = () => doSave(draftServer, draftToken)
  // "Get token": let the user pick their .LocalAdminToken file (server
  // owners: paste %LOCALAPPDATA%\Plex Media Server into the picker address
  // bar); read it with FileReader and connect immediately.
  const pickTokenFile = () => { try { fileRef.current && fileRef.current.click() } catch {} }
  const onTokenFile = () => {
    const f = fileRef.current && fileRef.current.files && fileRef.current.files[0]
    try { if (fileRef.current) fileRef.current.value = '' } catch {}
    if (!f) return
    const rd = new FileReader()
    rd.onload = () => {
      const tok = String(rd.result || '').trim()
      if (!tok) return
      setDraftToken(tok)
      doSave(draftServer, tok)
    }
    try { rd.readAsText(f) } catch {}
  }
  const doSignOut = async () => {
    await player.signOut()
    setDraftToken('')
    setShowSettings(true)
  }

  const tabs = [
    ['playing', t('tabPlaying')],
    ['browse', t('tabBrowse')],
    ['playlists', t('tabPlaylists')],
  ]

  return jsxs('div', { children: [
    jsxs('div', { className: 'duckwork-plex-head', children: [
      jsx('span', { children: t('plex') }),
      jsx('span', { className: 'duckwork-plex-conn', 'data-ok': conn === 'ok', children: connMsg }),
      jsx(SmallAction, { label: t(showSettings ? 'hideSettings' : 'showSettings'), icon: icons.ExternalLink, onClick: () => setShowSettings(!showSettings) }),
    ] }),
    showSettings && jsxs('div', { className: 'duckwork-plex-settings', children: [
      jsx('input', { type: 'text', value: draftServer, 'aria-label': t('server'), placeholder: 'http://127.0.0.1:32400', onChange: e => setDraftServer(e.target.value), spellCheck: false }),
      jsx('input', { type: 'password', value: draftToken, 'aria-label': t('token'), placeholder: conn === 'ok' ? 'Token saved · paste to replace' : 'Paste Plex token', onChange: e => setDraftToken(e.target.value), spellCheck: false }),
      jsx('input', { ref: fileRef, type: 'file', style: { display: 'none' }, 'aria-hidden': true, tabIndex: -1, onChange: onTokenFile }),
      jsxs('div', { className: 'duckwork-plex-settings-row', children: [
        jsx(Button, { size: 'micro', onClick: saveTest, disabled: testing, children: testing ? jsx(GlyphSpinner, { ariaLabel: t('saveTest') }) : t('saveTest') }),
        jsx(Button, { size: 'micro', variant: 'ghost', onClick: pickTokenFile, disabled: testing, children: t('getToken') }),
        conn === 'ok' && jsx(Button, { size: 'micro', variant: 'ghost', onClick: doSignOut, disabled: testing, children: t('signOut') }),
      ] }),
      jsx('div', { className: 'duckwork-plex-row-sub', children: t('tokenHint') }),
    ] }),
    rateErr && jsx('div', { className: 'duckwork-plex-error', role: 'status', children: rateErr }),
    conn === 'ok' && jsx('div', { className: 'duckwork-plex-tabs', role: 'tablist', children:
      tabs.map(([id, label]) => jsx('button', {
        className: 'duckwork-plex-tab', 'data-on': tab === id, role: 'tab',
        'aria-selected': tab === id, onClick: () => setTab(id), children: label,
      }, id)),
    }),
    conn === 'ok' && tab === 'playing' && jsx(PlayingTab, { player, t }),
    conn === 'ok' && tab === 'browse' && jsx(BrowseTab, { player, t }),
    conn === 'ok' && tab === 'playlists' && jsx(PlaylistsTab, { player, t, goPlaying: () => setTab('playing') }),
    conn === 'ok' && tab !== 'playing' && current && jsxs('button', {
      className: 'duckwork-plex-nowbar', 'aria-label': t('nowPlaying'),
      onClick: () => setTab('playing'),
      children: [
        player.artUrl(current, 72) && jsx('img', { className: 'duckwork-plex-now-art', src: player.artUrl(current, 72), alt: '' }),
        jsxs('span', { className: 'duckwork-plex-row-copy', children: [
          jsx('span', { className: 'duckwork-plex-row-name', children: `▶ ${current.title}` }),
          (current.artist || current.album) && jsx('span', { className: 'duckwork-plex-row-sub', children: [current.artist, current.album].filter(Boolean).join(' · ') }),
        ] }),
      ],
    }),
  ] })
}

function PlexBar({ player, ctx }) {
  const t = usePluginI18n(ID)
  const queue = useValue(player.queue)
  const index = useValue(player.index)
  const status = useValue(player.status)
  const [open, setOpen] = useState(false)
  const onOpenChange = v => { setOpen(v) }
  const triggerRef = useRef(null)
  const active = status === 'live' || status === 'connecting'
  const current = index >= 0 && index < queue.length ? queue[index] : null
  const label = current
    ? [current.artist, current.title].filter(Boolean).join(' – ') || current.title
    : t('plex')
  return jsxs('div', { className: 'duckwork-plex-bar', 'data-plex-status': status, children: [
    jsx('span', { className: 'duckwork-plex-dot', 'data-live': status === 'live' }),
    jsxs(Popover, { open, onOpenChange, children: [
      jsx(PopoverTrigger, { asChild: true, children: jsx(Button, {
        ref: triggerRef, variant: 'ghost', size: 'micro',
        'aria-label': `${t('browse')}: ${label}`,
        children: jsx('span', { className: 'plex-name', children: label }),
      }) }),
      jsx(PopoverContent, { side: 'top', align: 'end', className: 'duckwork-plex-panel', 'aria-label': t('plex'), onFocusOutside: e => e.preventDefault(), children:
        jsx(PanelCrash, { children: jsx(Panel, { player, ctx }) }),
      }),
    ] }),
    jsx(SmallAction, { label: t(active ? 'pause' : 'play'), icon: active ? icons.Pause : icons.Play, busy: status === 'connecting', onClick: player.toggle }),
    jsx(SmallAction, { label: t('next'), icon: NextArrow, size: 'icon-xs', onClick: player.next }),
  ] })
}

export default {
  id: ID,
  name: 'Plex Music',
  description: 'Mini-Plexamp: play, browse, and manage your Plex music — likes, playlists, repeat, sleep timer.',
  register(ctx) {
    ctx.i18n.register(LOCALES)
    const style = document.createElement('style')
    style.textContent = CSS
    document.head.append(style)
    const player = createPlayer(ctx)
    ctx.onDispose(() => { style.remove(); player.dispose() })
    ctx.register({ id: 'player', area: STATUSBAR_AREAS.right, order: 11, render: () => jsx(PlexBar, { player, ctx }) })
    if (player.token.get()) void player.testConnection().catch(() => {})
  },
}
