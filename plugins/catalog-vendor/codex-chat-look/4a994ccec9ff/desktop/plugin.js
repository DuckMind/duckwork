import { host, PALETTE_AREA, THEMES_AREA, TITLEBAR_AREAS, useQuery, useValue, DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, Codicon } from '@duckwork/plugin-sdk'
import { useRef, useState } from 'react'
import { jsx } from 'react/jsx-runtime'

const ID = 'codex-chat-look'
const SYSTEM_FONT = `-apple-system, system-ui, "Segoe UI", sans-serif`

const CODEX_THEME = {
  name: 'codex-chat',
  label: 'Duckwork Quiet · Catppuccin',
  description: 'Catppuccin palette — Latte in light, Mocha in dark, peach accent',
  colors: {
    background: '#eff1f5',
    foreground: '#4c4f69',
    card: '#ffffff',
    cardForeground: '#4c4f69',
    muted: '#dce0e8',
    mutedForeground: '#5c5f77',
    popover: '#ffffff',
    popoverForeground: '#4c4f69',
    primary: '#fe640b',
    primaryForeground: '#11111b',
    secondary: '#dce0e8',
    secondaryForeground: '#4c4f69',
    accent: '#ccd0da',
    accentForeground: '#4c4f69',
    border: '#ccd0da',
    input: '#ccd0da',
    ring: '#fe640b',
    composerRing: '#bcc0cc',
    destructive: '#d20f39',
    destructiveForeground: '#ffffff',
    sidebarBackground: '#e6e9ef',
    sidebarBorder: '#ccd0da',
    userBubble: '#dce0e8',
    userBubbleBorder: '#ccd0da'
  },
  darkColors: {
    background: '#1e1e2e',
    foreground: '#cdd6f4',
    card: '#313244',
    cardForeground: '#cdd6f4',
    muted: '#313244',
    mutedForeground: '#a6adc8',
    popover: '#313244',
    popoverForeground: '#cdd6f4',
    primary: '#fab387',
    primaryForeground: '#11111b',
    secondary: '#313244',
    secondaryForeground: '#cdd6f4',
    accent: '#45475a',
    accentForeground: '#cdd6f4',
    border: '#313244',
    input: '#313244',
    ring: '#fab387',
    composerRing: '#45475a',
    destructive: '#f38ba8',
    destructiveForeground: '#11111b',
    sidebarBackground: '#222231',
    sidebarBorder: '#313244',
    userBubble: '#1e1e2e',
    userBubbleBorder: '#313244'
  },
  typography: {
    fontSans: SYSTEM_FONT,
    fontMono: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
  }
}

async function switchHeaderProfile(name, connectionId) {
  if (name === host.state.profile.get() && connectionId === host.activeConnectionId()) return
  await host.ensureAgent(connectionId, name)
}

function gatewayHeaderName(connection) {
  if (connection.kind === 'local') return 'Laptop'
  if (/^mr[- ]chips(?:\s+\d+)?$/i.test(connection.label)) return 'Mr Chips'
  if (/^scooter$/i.test(connection.label)) return 'Scooter'
  return connection.label
}

function buildFleetHeaderChoices(connections, roster = {}) {
  const sources = roster.sources || [], agents = roster.agents || []
  const rank = label => ['Laptop', 'Mr Chips', 'Scooter'].indexOf(label)
  const rows = connections.map(connection => {
    const source = sources.find(row => row.connectionId === connection.id)
    const label = gatewayHeaderName(connection)
    return {
      key: `${connection.id}::default`, connectionId: connection.id, profile: 'default', label,
      icon: connection.kind === 'local' ? 'device-desktop' : 'server',
      detail: source?.needsSignIn ? 'Sign in required' : source?.reachable === false ? 'Unavailable' : source?.error === 'connect-on-demand' ? 'Connect on demand' : connection.kind === 'local' ? 'This Mac' : 'Gateway'
    }
  }).sort((a, b) => (rank(a.label) < 0 ? 3 : rank(a.label)) - (rank(b.label) < 0 ? 3 : rank(b.label)) || a.label.localeCompare(b.label))
  const chips = connections.find(connection => gatewayHeaderName(connection) === 'Mr Chips')
  if (chips && agents.some(agent => agent.connectionId === chips.id && agent.profile === 'media')) {
    rows.push({ key: `${chips.id}::media`, connectionId: chips.id, profile: 'media', label: 'Media', icon: 'play-circle', detail: 'Profile on Mr Chips' })
  }
  return rows
}

function fleetHeaderLabel(rows, connectionId, profile) {
  return rows.find(row => row.connectionId === connectionId && row.profile === profile)?.label || profile || 'Laptop'
}

async function loadFleetHeaderData() {
  const [connections, roster] = await Promise.allSettled([host.connections(), host.agents()])
  if (connections.status === 'rejected') throw connections.reason
  return { connections: connections.value, roster: roster.status === 'fulfilled' ? roster.value : {}, error: roster.status === 'rejected' ? String(roster.reason?.message || roster.reason) : '' }
}

function CodexProfileHeader() {
  const active = useValue(host.state.profile)
  useValue(host.state.gateway)
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(null)
  const switching = useRef(false)
  const query = useQuery({ queryKey: [ID, 'header-fleet'], queryFn: loadFleetHeaderData, staleTime: 60000 })
  const connections = query.data?.connections || []
  const connectionId = host.activeConnectionId() || connections.find(row => row.primary)?.id || 'local'
  const rows = buildFleetHeaderChoices(connections, query.data?.roster || {})
  const label = fleetHeaderLabel(rows, connectionId, active)
  const select = async row => {
    if (switching.current) return
    switching.current = true; setPending(row.key)
    try { await switchHeaderProfile(row.profile, row.connectionId) }
    catch (error) { host.notify({ kind: 'error', message: `Could not connect to ${row.label}: ${error?.message || error}` }) }
    finally { switching.current = false; setPending(null) }
  }
  return jsx('div', { 'data-codex-profile-header': '', style: { display: 'flex', alignItems: 'center', gap: 6 }, children: jsx(DropdownMenu, {
    open, onOpenChange: value => { setOpen(value); if (value) query.refetch() },
    children: [
      jsx(DropdownMenuTrigger, { asChild: true, children: jsx('button', {
        type: 'button', style: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 8px', border: 0, borderRadius: 6, background: 'transparent', color: 'var(--foreground)', font: 'inherit', cursor: 'pointer' }, 'aria-label': `Switch gateway or profile: ${label}`, 'aria-busy': Boolean(pending),
        children: [jsx('span', { children: label }), jsx(Codicon, { name: pending ? 'loading' : 'chevron-down', size: '0.75rem', className: pending ? 'animate-spin' : '', 'aria-hidden': true })]
      }) }),
      jsx(DropdownMenuContent, { align: 'start', side: 'bottom', sideOffset: 8, collisionPadding: 12,
        'data-codex-profile-menu': '', children: [
          ...rows.map(row => {
            const selected = row.connectionId === connectionId && row.profile === active
            return jsx(DropdownMenuItem, {
              role: 'menuitemradio', 'aria-checked': selected, 'data-codex-fleet-choice': row.key,
              disabled: Boolean(pending), onSelect: () => select(row),
              children: [
                jsx(Codicon, { name: row.icon, size: '1rem', 'aria-hidden': true }),
                jsx('span', { style: { display: 'flex', flexDirection: 'column', flex: 1 }, children: [jsx('span', { children: row.label }), jsx('span', { style: { fontSize: '0.75rem', color: 'var(--muted-foreground)' }, children: row.detail })] }),
                selected ? jsx(Codicon, { name: 'check', size: '0.875rem', style: { color: 'var(--primary)' }, 'aria-hidden': true }) : null
              ]
            }, row.key)
          }),
          query.isPending ? jsx(DropdownMenuItem, { disabled: true, children: 'Loading gateways…' }) : null,
          query.isError || query.data?.error ? jsx(DropdownMenuItem, { onSelect: event => { event.preventDefault(); query.refetch() }, children: 'Refresh gateway list' }) : null,
          jsx(DropdownMenuSeparator, {}),
          jsx(DropdownMenuItem, { onSelect: () => host.navigate('/settings?tab=gateway'), children: [jsx(Codicon, { name: 'plug', size: '0.875rem', 'aria-hidden': true }), jsx('span', { children: 'Manage gateways…' })] }),
          jsx(DropdownMenuItem, { onSelect: () => host.navigate('/profiles'), children: [jsx(Codicon, { name: 'settings-gear', size: '0.875rem', 'aria-hidden': true }), jsx('span', { children: 'Manage profiles…' })] })
        ]
      })
    ]
  }) })
}

export default {
  id: ID,
  name: 'Duckwork Quiet',
  register(ctx) {
    ctx.register({ id: 'toggle-sidebar-density', area: PALETTE_AREA, data: {
      id: 'codex-chat-look.toggle-sidebar-density',
      label: 'Duckwork Quiet: Native session list density',
      detail: () => host.settings.get('sessionListDensity'),
      detailVariant: 'state', keepOpen: true,
      keywords: ['sidebar', 'density', 'compact', 'comfortable', 'detailed'],
      run: () => {
        const modes = ['compact', 'comfortable', 'detailed']
        const current = host.settings.get('sessionListDensity')
        host.settings.set('sessionListDensity', modes[(modes.indexOf(current) + 1) % modes.length])
      }
    } })
    ctx.register({ id: 'theme' , area: THEMES_AREA, data: CODEX_THEME })
    ctx.register({ id: 'profile-header', area: TITLEBAR_AREAS.left, order: 0, render: () => jsx(CodexProfileHeader, {}) })
  }
}
