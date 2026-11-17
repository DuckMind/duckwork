/**
 * All Pets — browse EVERY installed pet in its own docked workspace pane.
 *
 * Why this exists: the built-in picker (Settings > Appearance > Pet) renders at most
 * 60 rows (`RENDER_CAP` in app/settings/pet-settings.tsx) and the palette page caps at
 * 50, so a store with a couple hundred pets can only be browsed by typing a search term.
 *
 * Why a PANE and not a page: a contributed full-page route lands inside the workspace
 * zone, so on a layout parked on a session tile the navigation looks dead (the tile stays
 * on screen, #72602). `host.openWorkspace` is the supported door for a plugin surface of
 * its own: a closeable tab docked beside main that takes over the chat area when active,
 * re-opening the same id fronts the existing tab instead of stacking a duplicate.
 *
 * Data is read-only until a tile is clicked: `pet.gallery` with `localOnly: true` lists
 * installed pets without touching the network manifest, `pet.thumb` fills tiles, and a
 * click runs `pet.select` (install-if-needed + make active), the same call the picker makes.
 */

import { createElement, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { host, KEYBINDS_AREA, PALETTE_AREA, STATUSBAR_AREAS } from '@duckwork/plugin-sdk'

const PANE_ID = 'pets-all'
const THUMB_BATCH = 6
const GRID_MIN = 140
const PAGE_SIZE = 240

// The app's own theme variables; fallbacks keep the pane readable if a name moves.
const T = {
  fg: 'var(--foreground, #e6e6e6)',
  muted: 'var(--muted-foreground, #9a9a9a)',
  border: 'var(--border, #333)',
  card: 'var(--card, rgba(255,255,255,0.04))',
  accent: 'var(--accent, #4aa3df)'
}

const norm = value => String(value || '').trim().toLowerCase()

function useInstalledPets() {
  const [state, setState] = useState({ status: 'loading', pets: [], active: '', enabled: false, error: '' })

  const reload = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'loading', error: '' }))
    try {
      const res = await host.request('pet.gallery', { localOnly: true })
      const rows = (res && Array.isArray(res.pets) ? res.pets : []).filter(pet => pet.installed)
      const active = (res && res.active) || ''
      rows.sort((a, b) => {
        if (a.slug === active) return -1
        if (b.slug === active) return 1
        if (Boolean(a.generated) !== Boolean(b.generated)) return a.generated ? -1 : 1
        return String(a.displayName || a.slug).localeCompare(String(b.displayName || b.slug))
      })
      setState({ status: 'ready', pets: rows, active, enabled: Boolean(res && res.enabled), error: '' })
    } catch (err) {
      setState(prev => ({ ...prev, status: 'error', error: err && err.message ? err.message : String(err) }))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  return { ...state, reload, setActive: slug => setState(prev => ({ ...prev, active: slug })) }
}

/** Idle-frame thumbnails, fetched in small batches so a big store never blocks the paint. */
function useThumbs(status, pets) {
  const cache = useRef({})
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (status !== 'ready') {
      return undefined
    }
    let cancelled = false
    const queue = pets.map(pet => pet.slug).filter(slug => cache.current[slug] === undefined)

    void (async () => {
      for (let i = 0; i < queue.length && !cancelled; i += THUMB_BATCH) {
        const batch = queue.slice(i, i + THUMB_BATCH)
        await Promise.all(
          batch.map(async slug => {
            try {
              const res = await host.request('pet.thumb', { slug })
              cache.current[slug] = res && res.ok ? res.dataUri : ''
            } catch {
              cache.current[slug] = ''
            }
          })
        )
        if (!cancelled) {
          setTick(value => value + 1)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [status, pets])

  return { cache, tick }
}

function Tile({ pet, active, thumb, busy, onPick }) {
  const isActive = pet.slug === active
  return createElement(
    'button',
    {
      type: 'button',
      onClick: () => onPick(pet.slug),
      disabled: busy,
      title: pet.slug,
      style: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
        padding: '10px 8px',
        borderRadius: 10,
        border: `1px solid ${isActive ? T.accent : T.border}`,
        background: T.card,
        color: T.fg,
        cursor: busy ? 'progress' : 'pointer',
        textAlign: 'center',
        font: 'inherit'
      }
    },
    createElement('div', {
      key: 'thumb',
      style: {
        width: 64,
        height: 69,
        imageRendering: 'pixelated',
        backgroundImage: thumb ? `url("${thumb}")` : 'none',
        backgroundSize: 'contain',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center',
        opacity: thumb ? 1 : 0.25
      }
    }),
    createElement('div', { key: 'name', style: { fontSize: 12, fontWeight: isActive ? 600 : 400, lineHeight: 1.2 } }, pet.displayName || pet.slug),
    createElement('div', { key: 'slug', style: { fontSize: 10, color: T.muted, wordBreak: 'break-all' } }, pet.slug),
    isActive ? createElement('div', { key: 'badge', style: { fontSize: 10, color: T.accent } }, 'active') : null,
    pet.generated ? createElement('div', { key: 'gen', style: { fontSize: 10, color: T.muted } }, 'generated') : null
  )
}

function PetsAllPane() {
  const { status, pets, active, error, reload, setActive } = useInstalledPets()
  const { cache, tick } = useThumbs(status, pets)
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')

  const shown = useMemo(() => {
    const needle = norm(query)
    return needle
      ? pets.filter(pet => norm(pet.slug).includes(needle) || norm(pet.displayName).includes(needle))
      : pets
  }, [pets, query])

  // A new search starts at the first page again.
  useEffect(() => setLimit(PAGE_SIZE), [query])

  const visible = shown.slice(0, limit)

  const pick = useCallback(
    async slug => {
      setBusy(slug)
      setNotice('')
      try {
        await host.request('pet.select', { slug })
        setActive(slug)
        setNotice(`${slug} is now active`)
      } catch (err) {
        setNotice(err && err.message ? err.message : 'could not adopt that pet')
      } finally {
        setBusy('')
      }
    },
    [setActive]
  )

  // `tick` bumps as thumbnails land; it is not read directly, it forces the repaint.
  void tick

  const header = createElement(
    'div',
    { key: 'head', style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 } },
    createElement('div', { key: 'count', style: { fontSize: 13, color: T.muted } },
      status === 'ready'
        ? `${Math.min(limit, shown.length)} shown of ${shown.length} matching (${pets.length} installed)`
        : status === 'error'
          ? 'could not read the pet store'
          : 'loading pets...'
    ),
    createElement('input', {
      key: 'search',
      value: query,
      placeholder: 'Search installed pets...',
      onChange: event => setQuery(event.target.value),
      style: {
        flex: '1 1 200px',
        minWidth: 160,
        padding: '7px 10px',
        borderRadius: 8,
        border: `1px solid ${T.border}`,
        background: 'transparent',
        color: T.fg,
        font: 'inherit'
      }
    }),
    createElement('button', {
      key: 'reload',
      type: 'button',
      onClick: () => void reload(),
      style: {
        padding: '7px 12px',
        borderRadius: 8,
        border: `1px solid ${T.border}`,
        background: T.card,
        color: T.fg,
        cursor: 'pointer',
        font: 'inherit'
      }
    }, 'Refresh')
  )

  const body = status === 'error'
    ? createElement('div', { key: 'err', style: { color: T.muted, fontSize: 13 } }, `Error: ${error}`)
    : createElement(
        'div',
        {
          key: 'grid',
          style: {
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, minmax(${GRID_MIN}px, 1fr))`,
            gap: 10,
            paddingBottom: 16
          }
        },
        visible.map(pet =>
          createElement(Tile, {
            key: pet.slug,
            pet,
            active,
            thumb: cache.current[pet.slug],
            busy: busy === pet.slug,
            onPick: pick
          })
        ),
        shown.length > limit
          ? createElement('button', {
              key: 'more',
              type: 'button',
              onClick: () => setLimit(value => value + PAGE_SIZE),
              style: {
                gridColumn: '1 / -1',
                padding: '8px 16px',
                borderRadius: 8,
                border: `1px solid ${T.border}`,
                background: T.card,
                color: T.fg,
                cursor: 'pointer',
                font: 'inherit'
              }
            }, `Load ${Math.min(PAGE_SIZE, shown.length - limit)} more (${shown.length - limit} left)`)
          : null
      )

  return createElement(
    'div',
    {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '14px 16px',
        height: '100%',
        overflowY: 'auto',
        color: T.fg,
        font: 'inherit'
      }
    },
    // Sticky header: a 200-pet grid is taller than the pane, and the search box is
    // useless once it scrolls away.
    createElement(
      'div',
      {
        key: 'sticky',
        style: {
          position: 'sticky',
          top: 0,
          zIndex: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          paddingBottom: 10,
          background: 'var(--ui-panel-background, var(--background, #16181d))'
        }
      },
      createElement('div', { key: 'hint', style: { fontSize: 12, color: T.muted } },
        'Every pet installed for this profile. Click a tile to make it active.'
      ),
      header,
      notice ? createElement('div', { key: 'notice', style: { fontSize: 12, color: T.accent } }, notice) : null
    ),
    body
  )
}

/** Open the pane, or front the tab when it is already open (host.openWorkspace is idempotent). */
function openPetsPane() {
  host.openWorkspace(PANE_ID, {
    title: 'All pets',
    dock: { pane: 'workspace', pos: 'right' },
    minWidth: '20rem',
    render: () => createElement(PetsAllPane)
  })
}

export default {
  id: 'pets-all',
  name: 'All Pets',
  description: 'Every installed pet in its own workspace pane, beyond the 60-row settings preview.',
  defaultEnabled: true,
  register(ctx) {
    // Older desktops have no openWorkspace: fall back to a full page route so the
    // feature still exists there, even though a page can land behind a session tile.
    if (typeof host.openWorkspace !== 'function') {
      ctx.register({
        id: 'page-fallback',
        area: 'routes',
        data: { path: '/pets' },
        render: () => createElement(PetsAllPane)
      })
      return
    }

    ctx.registerMany([
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'petsAll.open',
          label: 'Pets: Open the pet gallery pane',
          keywords: ['pets', 'mascot', 'gallery', 'all', 'adopt'],
          run: openPetsPane
        }
      },
      {
        id: 'openKey',
        area: KEYBINDS_AREA,
        data: {
          id: 'petsAll.open',
          category: 'view',
          defaults: ['mod+alt+p'],
          label: 'Open the pet gallery pane',
          run: openPetsPane
        }
      },
      {
        // The clickable door in the app's own status bar, so the pane is reachable
        // without remembering a chord or opening the palette.
        id: 'chip',
        area: STATUSBAR_AREAS.right,
        order: 55,
        render: () =>
          createElement(
            'button',
            {
              type: 'button',
              onClick: openPetsPane,
              title: 'Open the pet gallery pane (Ctrl+Alt+P)',
              style: {
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '0 4px',
                border: 'none',
                background: 'transparent',
                color: 'inherit',
                font: 'inherit',
                cursor: 'pointer'
              }
            },
            createElement('span', { key: 'icon', 'aria-hidden': 'true' }, '🐾'),
            createElement('span', { key: 'label' }, 'pets')
          )
      }
    ])
  }
}
