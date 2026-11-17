/** Actual Duckwork SDK/context/registry; no source-text assertions or synthetic SDK. */
import { host, KEYBINDS_AREA, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS } from '@duckwork/plugin-sdk'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// Route integration tests inspect the real registry. These imports are test-only;
// the bundled plugin itself must continue using only @duckwork/plugin-sdk.
// eslint-disable-next-line no-restricted-imports
import { createPluginContext } from '../../../apps/desktop/src/contrib/plugin'
// eslint-disable-next-line no-restricted-imports
import { $pluginDecisions, pluginActive } from '../../../apps/desktop/src/contrib/plugins-store'
// eslint-disable-next-line no-restricted-imports
import { registry } from '../../../apps/desktop/src/contrib/registry'
// eslint-disable-next-line no-restricted-imports
import office from '../desktop/plugin.js'

const disposers: (() => void)[] = []
const areas = [ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS.right, PALETTE_AREA, KEYBINDS_AREA]
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  disposers.splice(0).reverse().forEach(dispose => dispose())
  $pluginDecisions.set({})
})

function mountOffice(rest: () => Promise<unknown>, prefs?: Record<string, unknown>, withStatus = false) {
  const ctx = createPluginContext(office.id, dispose => disposers.push(dispose))

  ctx.rest = vi.fn(rest) as typeof ctx.rest

  if (prefs) {
    ctx.storage.get = vi.fn(() => prefs)
  }

  office.register(ctx)
  const route = registry.getArea(ROUTES_AREA).find(c => c.id === 'office-3d:page')!
  const status = registry.getArea(STATUSBAR_AREAS.right).find(c => c.id === 'office-3d:status')!
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })
  render(createElement(QueryClientProvider, { client },
    withStatus ? createElement('div', null, route.render!(), status.render!()) : route.render!()))

  return { client, rest: ctx.rest }
}

describe('bundled Office 3D Duckwork SDK', () => {
  it('imports and registers its route, nav, chip and commands without a disk plugin or Developer Mode', () => {
    const ctx = createPluginContext(office.id, dispose => disposers.push(dispose))
    expect(pluginActive(office.id, office.defaultEnabled)).toBe(true)
    office.register(ctx)
    const route = registry.getArea(ROUTES_AREA).find(c => c.id === 'office-3d:page')
    expect(route?.data).toEqual({ path: '/office-3d' })
    expect(typeof route?.render).toBe('function')
    expect(registry.getArea(SIDEBAR_NAV_AREA).find(c => c.id === 'office-3d:nav')?.data)
      .toMatchObject({ path: '/office-3d', label: 'Văn phòng' })

    for (const [area, id] of [[STATUSBAR_AREAS.right, 'status'], [PALETTE_AREA, 'palette-open'], [KEYBINDS_AREA, 'keybind-open']]) {
      expect(registry.getArea(area).some(c => c.id === 'office-3d:' + id)).toBe(true)
    }
  })

  it('obeys the existing persisted plugin-disable decision despite defaultEnabled', () => {
    $pluginDecisions.set({ 'office-3d': false })
    expect(pluginActive(office.id, office.defaultEnabled)).toBe(false)
    $pluginDecisions.set({ 'office-3d': true })
    expect(pluginActive(office.id, office.defaultEnabled)).toBe(true)
  })

  it('disposes every registered surface through the real scoped context', () => {
    office.register(createPluginContext(office.id, dispose => disposers.push(dispose)))
    expect(registry.getArea(ROUTES_AREA).some(c => c.id === 'office-3d:page')).toBe(true)
    disposers.splice(0).reverse().forEach(dispose => dispose())

    for (const area of areas) {
      expect(registry.getArea(area).some(c => c.source === 'plugin:office-3d')).toBe(false)
    }
  })
})

describe('Office dashboard route', () => {
  const worker = {
    profile: 'worker_alpha', display_name: 'Nghiên cứu', online: true, busy: true,
    active_sessions: 2, session_stats_available: true, tokens_total: 2450, cost_total: 0.35,
    last_session_activity: 1760000000
  }

  it('opens the data-backed dashboard first, with scoped states and no invented model or task', async () => {
    const navigate = vi.spyOn(host, 'navigate').mockImplementation(() => undefined)
    const newChat = vi.spyOn(host, 'newChat')
    mountOffice(async () => [worker, {
      profile: 'quiet', display_name: 'Yên tĩnh', online: false, busy: false,
      active_sessions: 0, tokens_total: 0, cost_total: 0
    }])
    expect(await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Bảng điều khiển' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.queryByRole('button', { name: 'Zoom in' })).toBeNull()
    expect(screen.getByText(/2 agent/)).toBeTruthy()
    expect(screen.getByText(/2 phiên có hoạt động trong 90 giây/)).toBeTruthy()
    // Vietnamese decimal separator ("2,5k"), not the English point.
    expect(screen.getAllByText('2,5k').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chưa rõ').length).toBeGreaterThan(0)
    expect(screen.queryByText(/GPT-6-luna|Giải bài toán mã đi tuần/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' }))
    expect(navigate).toHaveBeenCalledWith('/agents')
    expect(newChat).not.toHaveBeenCalled()
    expect(screen.getAllByRole('button', { name: 'Tạm dừng · chưa hỗ trợ' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Tạm dừng · chưa hỗ trợ' }).every(button => (button as HTMLButtonElement).disabled)).toBe(true)
    expect(screen.getByRole('region', { name: 'Cần bạn xử lý' }).textContent).toContain('không cung cấp cảnh báo chi tiết')
    expect(screen.getByRole('button', { name: /Thêm agent/ })).toBeTruthy()
    expect(screen.queryByText(/đang làm việc|Đang làm/)).toBeNull()
  })

  it('navigates to supported app-wide jobs and profile management without mutating an agent', async () => {
    const navigate = vi.spyOn(host, 'navigate').mockImplementation(() => undefined)
    const rest = vi.fn(async () => [worker])
    mountOffice(rest)
    await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })
    fireEvent.click(screen.getByRole('button', { name: 'Lịch chạy' }))
    fireEvent.click(screen.getByRole('button', { name: 'Quản lý hồ sơ' }))
    expect(navigate.mock.calls).toEqual([['/cron'], ['/profiles']])
    expect(rest).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /Thêm agent/ }))
    expect(navigate).toHaveBeenLastCalledWith('/profiles')
  })

  it('offers scheduling only for the active profile, without submitting work to another profile', async () => {
    const navigate = vi.spyOn(host, 'navigate').mockImplementation(() => undefined)
    const request = vi.spyOn(host, 'request')
    const newChat = vi.spyOn(host, 'newChat')
    const previous = host.state.profile.get()
    host.state.profile.set('default')

    try {
      mountOffice(async () => [worker, {
        profile: 'default', display_name: 'Chính', online: true, busy: false,
      }])
      const secondary = (await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).closest('article')!
      const primary = screen.getByRole('button', { name: 'Tìm Bot Chat của Chính' }).closest('article')!
      expect(secondary.textContent).toContain('Đổi hồ sơ trong bộ chọn agent')
      expect(secondary.querySelectorAll('button:not(:disabled)')).toHaveLength(1)
      expect(primary.textContent).toContain('Lịch chạy của Chính')
      fireEvent.click(screen.getByRole('button', { name: 'Lịch chạy của Chính' }))
      expect(navigate).toHaveBeenCalledExactlyOnceWith('/cron')
      expect(request).not.toHaveBeenCalled()
      expect(newChat).not.toHaveBeenCalled()
    } finally {
      act(() => host.state.profile.set(previous))
    }
  })

  it('opens only the secondary profile session supplied by its own Office backend', async () => {
    const open = vi.spyOn(host, 'openSession').mockResolvedValue(undefined)
    const request = vi.spyOn(host, 'request')
    mountOffice(async () => [{
      ...worker, current_task: 'Đọc báo cáo', current_model: 'worker-model',
      latest_session_id: 'worker-session'
    }, {
      profile: 'default', display_name: 'Chính', online: true, busy: false,
      latest_session_id: 'root-session'
    }])
    const secondary = (await screen.findByText('worker-model')).closest('article')!
    expect(secondary.textContent).toContain('Tiêu đề phiên gần đây: Đọc báo cáo')
    expect(secondary.textContent).not.toContain('root-session')
    fireEvent.click(screen.getAllByRole('button', { name: 'Mở phiên gần nhất' })[0])
    await waitFor(() => expect(open).toHaveBeenCalledWith('worker-session', { profile: 'worker_alpha' }))
    expect(request).not.toHaveBeenCalled()
    expect(secondary.textContent).toContain('Đổi hồ sơ trong bộ chọn agent')
  })

  it('never treats recent session metadata as a live task or a pause permission', async () => {
    const request = vi.spyOn(host, 'request')
    const open = vi.spyOn(host, 'openSession')
    mountOffice(async () => [{
      ...worker, current_task: 'Báo cáo tuần', current_model: 'model-a',
      latest_session_id: 'session-a', active_sessions: 0, busy: false,
      session_stats_available: true
    }])
    const card = (await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).closest('article')!
    expect(card.textContent).toContain('Tiêu đề phiên gần đây: Báo cáo tuần')
    expect(card.textContent).not.toContain('Đang làm')
    expect((card.querySelector('button:disabled') as HTMLButtonElement).textContent).toContain('Tạm dừng')
    fireEvent.click(card.querySelector('button:disabled')!)
    expect(request).not.toHaveBeenCalled()
    expect(open).not.toHaveBeenCalled()
  })

  it('reads the most recent recorded session for the agent card and writes numbers in Vietnamese', async () => {
    mountOffice(async () => [{
      ...worker, recent_task: 'Báo cáo quý', recent_model: 'gpt-6-luna',
      current_task: null, current_model: null, latest_session_id: 'session-a',
      tokens_total: 27_700, session_stats_available: true, busy: false, active_sessions: 0
    }])
    const card = (await screen.findByText('gpt-6-luna')).closest('article')!

    // A finished session is still what ran most recently — "Chưa rõ" would be wrong —
    // but it must not be announced as live work.
    expect(card.textContent).toContain('Tiêu đề phiên gần đây: Báo cáo quý')
    expect(card.textContent).toContain('27,7k')
    expect(card.textContent).not.toContain('27.7k')
    expect(card.textContent).not.toContain('Đang làm')
    // The dashed add card sits in the same grid as the agents.
    expect(screen.getByRole('button', { name: '+ Thêm agent (quản lý hồ sơ)' })).toBeTruthy()
  })

  it('pauses and resumes only the selected profile after the owner confirms the status', async () => {
    const previous = host.state.profile.get()
    const connection = vi.spyOn(host.state.connectionId, 'get').mockReturnValue('local')

    const request = vi.spyOn(host, 'request').mockImplementation(async (method, params) => {
      if (method === 'profile.pause.status') {
        return { paused: false } as never
      }

      if (method === 'profile.pause.set') {
        return { paused: params.paused } as never
      }

      throw new Error('unexpected request')
    })

    act(() => host.state.profile.set('default'))

    try {
      mountOffice(async () => [worker, { profile: 'default', display_name: 'Chính', online: true }])
      const secondary = (await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).closest('article')!
      expect((secondary.querySelector('button:disabled') as HTMLButtonElement).textContent).toContain('Tạm dừng')
      fireEvent.click(await screen.findByRole('button', { name: 'Tạm dừng agent' }))
      await screen.findByRole('button', { name: 'Tiếp tục agent' })
      fireEvent.click(screen.getByRole('button', { name: 'Tiếp tục agent' }))
      await screen.findByRole('button', { name: 'Tạm dừng agent' })
      expect(request.mock.calls).toEqual([
        ['profile.pause.status', { profile: 'default' }],
        ['profile.pause.set', { profile: 'default', paused: true }],
        ['profile.pause.set', { profile: 'default', paused: false }],
      ])
    } finally {
      connection.mockRestore()
      act(() => host.state.profile.set(previous))
    }
  })

  it('keeps the authoritative status and reports a refused pause without a fake success', async () => {
    const previous = host.state.profile.get()
    const connection = vi.spyOn(host.state.connectionId, 'get').mockReturnValue('local')

    const request = vi.spyOn(host, 'request').mockImplementation(async method => {
      if (method === 'profile.pause.status') {
        return { paused: false } as never
      }

      throw new Error('permission_denied')
    })

    act(() => host.state.profile.set('default'))

    try {
      mountOffice(async () => [{ profile: 'default', display_name: 'Chính', online: true }])
      fireEvent.click(await screen.findByRole('button', { name: 'Tạm dừng agent' }))
      await screen.findByRole('alert')
      expect(screen.getByRole('button', { name: 'Tạm dừng agent' })).toBeTruthy()
      expect(request).toHaveBeenLastCalledWith('profile.pause.set', { profile: 'default', paused: true })
    } finally {
      connection.mockRestore()
      act(() => host.state.profile.set(previous))
    }
  })

  it('ignores a late pause status from the previous selected profile', async () => {
    const previous = host.state.profile.get()
    const connection = vi.spyOn(host.state.connectionId, 'get').mockReturnValue('local')
    const pending = new Map<string, (value: { paused: boolean }) => void>()
    const request = vi.spyOn(host, 'request').mockImplementation(async (_method, params) =>
      new Promise(resolve => pending.set(String(params.profile), resolve)) as never)

    act(() => host.state.profile.set('default'))

    try {
      mountOffice(async () => [worker, { profile: 'default', display_name: 'Chính', online: true }])
      await screen.findByRole('button', { name: 'Tìm Bot Chat của Chính' })
      await waitFor(() => expect(pending.has('default')).toBe(true))

      act(() => host.state.profile.set('worker_alpha'))
      await waitFor(() => expect(pending.has('worker_alpha')).toBe(true))
      await act(async () => pending.get('default')!({ paused: false }))
      expect(screen.queryByRole('button', { name: 'Tạm dừng agent' })).toBeNull()
      await act(async () => pending.get('worker_alpha')!({ paused: true }))
      expect(screen.getByRole('button', { name: 'Tiếp tục agent' })).toBeTruthy()
      expect(request).toHaveBeenCalledTimes(2)
    } finally {
      connection.mockRestore()
      act(() => host.state.profile.set(previous))
    }
  })

  it('does not enable an unsupported backend with a malformed pause status', async () => {
    const previous = host.state.profile.get()
    const connection = vi.spyOn(host.state.connectionId, 'get').mockReturnValue('local')
    const request = vi.spyOn(host, 'request').mockResolvedValue({ paused: 'yes' } as never)

    act(() => host.state.profile.set('default'))

    try {
      mountOffice(async () => [{ profile: 'default', display_name: 'Chính', online: true }])
      expect(await screen.findByRole('alert')).toBeTruthy()
      expect((screen.getByRole('button', { name: 'Tạm dừng · chưa hỗ trợ' }) as HTMLButtonElement).disabled).toBe(true)
      expect(request).toHaveBeenCalledExactlyOnceWith('profile.pause.status', { profile: 'default' })
    } finally {
      connection.mockRestore()
      act(() => host.state.profile.set(previous))
    }
  })

  it('keeps unavailable usage and activity unknown without fabricating timeline events', async () => {
    mountOffice(async () => [{
      profile: 'unreadable', display_name: 'Dữ liệu thiếu', online: true, busy: true,
      session_stats_available: false, active_sessions: 0, tokens_total: 0,
      last_session_activity: 1760000000
    }])
    const card = (await screen.findByRole('button', { name: 'Tìm Bot Chat của Dữ liệu thiếu' })).closest('article')!
    expect(card.textContent).toContain('Phiên ghi nhận gần đây')
    expect(card.textContent).toContain('Chưa rõ')
    expect(screen.getByRole('region', { name: 'Hoạt động gần đây' }).textContent)
      .toContain('Chưa có mốc hoạt động phiên được ghi nhận.')
  })

  it('retains positive recorded activity from an older backend without an availability flag', async () => {
    mountOffice(async () => [{ ...worker, session_stats_available: undefined }])
    const card = (await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).closest('article')!
    expect(card.textContent).toContain('2 phiên có hoạt động trong 90 giây')
    expect(screen.getByRole('region', { name: 'Hoạt động gần đây' }).textContent).toContain('Nghiên cứu')
  })

  it('reports job navigation failure instead of pretending to open another profile', async () => {
    const error = new Error('no route')
    vi.spyOn(host, 'navigate').mockImplementation(() => { throw error })
    const notify = vi.spyOn(host, 'notifyError').mockImplementation(() => undefined)
    const previous = host.state.profile.get()
    host.state.profile.set('worker_alpha')

    try {
      mountOffice(async () => [worker])
      fireEvent.click(await screen.findByRole('button', { name: 'Lịch chạy của Nghiên cứu' }))
      expect(notify).toHaveBeenCalledWith(error, 'Không mở được lịch chạy')
    } finally {
      act(() => host.state.profile.set(previous))
    }
  })

  it('reports failed session opens without falling back to another profile', async () => {
    const error = new Error('session unavailable')
    const open = vi.spyOn(host, 'openSession').mockRejectedValue(error)
    const notify = vi.spyOn(host, 'notifyError').mockImplementation(() => undefined)
    mountOffice(async () => [{ ...worker, latest_session_id: 'secondary-session' }])
    fireEvent.click(await screen.findByRole('button', { name: 'Mở phiên gần nhất' }))
    await waitFor(() => expect(notify).toHaveBeenCalledWith(error, 'Không mở được phiên đã ghi nhận'))
    expect(open).toHaveBeenCalledWith('secondary-session', { profile: 'worker_alpha' })
  })

  it('switches to the retained scene and back without showing its canvas by default', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    mountOffice(async () => [worker])
    await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })
    fireEvent.click(screen.getByRole('button', { name: 'Sơ đồ văn phòng' }))
    expect(screen.getByRole('button', { name: 'Sơ đồ văn phòng' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText(/Nhân vật gõ phím chỉ minh họa hoạt động phiên gần đây/)).toBeTruthy()
    expect(document.querySelector('[data-office-page] canvas')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Bảng điều khiển' }))
    expect(document.querySelector('[data-office-page] canvas')).toBeNull()
  })

  it('shows Vietnamese scene empty state when no profiles are enabled', async () => {
    mountOffice(async () => [])
    await screen.findByText('Chưa có agent nào trong phạm vi văn phòng này.')
    fireEvent.click(screen.getByRole('button', { name: 'Sơ đồ văn phòng' }))
    expect(screen.getByText('Chưa có hồ sơ được hiển thị')).toBeTruthy()
  })

  it('does not present an offline gateway fallback count as zero in scene details', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    mountOffice(async () => [{ profile: 'offline_one', online: false, active_agents: 0,
      active_sessions: 0, open_sessions: 0, tokens_total: 0, cost_total: 0 }])
    await screen.findByRole('button', { name: 'Tìm Bot Chat của offline_one' })
    fireEvent.click(screen.getByRole('button', { name: 'Sơ đồ văn phòng' }))
    const profileRow = document.querySelector('[data-profile-row="offline_one"]') as HTMLButtonElement
    fireEvent.click(profileRow)
    expect(screen.getByText('Agent gateway báo về').parentElement?.textContent).toContain('Chưa rõ')
    expect(screen.getByText('Agent gateway báo về').parentElement?.textContent).not.toContain('0')
  })

  it('scopes cards and chart to enabled profiles and keeps ambiguous zero usage unknown when changing units', async () => {
    mountOffice(async () => [worker, {
      profile: 'zero_agent', display_name: '', online: true, busy: false,
      tokens_total: 0, cost_total: 0
    }, {
      profile: 'excluded', display_name: 'Không hiển thị', online: true, busy: true,
      tokens_total: 999, cost_total: 99
    }], { excludedProfileIds: ['excluded'] })
    await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })
    expect(screen.getByRole('button', { name: 'Tìm Bot Chat của zero_agent' })).toBeTruthy()
    expect(screen.getByText(/2 agent/)).toBeTruthy()
    expect(screen.queryByText('Không hiển thị')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Chi phí' }))
    expect(screen.getByRole('button', { name: 'Chi phí' }).getAttribute('aria-pressed')).toBe('true')
    const chart = screen.getByRole('region', { name: 'Mức dùng đã ghi nhận' })
    expect(chart.textContent).toContain('$0.35')
    expect(chart.textContent).toContain('Chưa rõ')
    expect(chart.textContent).not.toContain('$0.00')
  })

  it('shows measured zero usage only with successful profile database reads', async () => {
    mountOffice(async () => [{
      profile: 'readable', online: false, busy: false,
      session_stats_available: true, tokens_total: 0, cost_total: 0,
    }, {
      profile: 'unreadable', online: false, busy: false,
      session_stats_available: false, tokens_total: 0, cost_total: 0,
    }])
    const readable = (await screen.findByRole('button', { name: 'Tìm Bot Chat của readable' })).closest('article')!
    const unreadable = screen.getByRole('button', { name: 'Tìm Bot Chat của unreadable' }).closest('article')!
    expect(readable.textContent).toContain('0')
    expect(unreadable.textContent).toContain('Chưa rõ')
    const chart = screen.getByRole('region', { name: 'Mức dùng đã ghi nhận' })
    fireEvent.click(screen.getByRole('button', { name: 'Chi phí' }))
    expect(chart.textContent).toContain('$0.00')
    expect(chart.textContent).toContain('Chưa rõ')
  })

  it('reports a failed Agent-list handoff instead of creating a different chat', async () => {
    const error = new Error('route unavailable')
    vi.spyOn(host, 'navigate').mockImplementation(() => { throw error })
    const notify = vi.spyOn(host, 'notifyError').mockImplementation(() => undefined)
    const newChat = vi.spyOn(host, 'newChat')
    mountOffice(async () => [worker])
    fireEvent.click(await screen.findByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' }))
    expect(notify).toHaveBeenCalledWith(error, 'Không mở được danh sách agent để tìm Bot Chat của Nghiên cứu')
    expect(newChat).not.toHaveBeenCalled()
  })

  it('reports load failures with an explicit retry and hidden technical details', async () => {
    let fail = true

    const rest = vi.fn(async () => {
      if (fail) {
        throw new Error('office backend 502')
      }

      return [worker]
    })

    mountOffice(rest)
    expect(await screen.findByText('Không tải được trạng thái văn phòng')).toBeTruthy()
    expect(screen.getByText('office backend 502').closest('details')?.open).toBe(false)
    fireEvent.click(screen.getByText('Chi tiết kỹ thuật'))
    expect(screen.getByText('office backend 502').closest('details')?.open).toBe(true)
    fail = false
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Tìm Bot Chat của Nghiên cứu' })).toBeTruthy())
    expect(rest).toHaveBeenCalledTimes(2)
  })

  it('hides cached status on failed refresh and does not toast a stale transition on recovery', async () => {
    let state: 'recent' | 'error' | 'offline' = 'recent'
    const notify = vi.spyOn(host, 'notify').mockImplementation(() => undefined)

    const rest = vi.fn(async () => {
      if (state === 'error') {
        throw new Error('refresh unavailable')
      }

      return [{ ...worker, online: state !== 'offline', busy: state === 'recent' }]
    })

    const { client } = mountOffice(rest, { notifyOnChange: true }, true)
    await waitFor(() => expect(screen.getByText('1 có hoạt động gần đây')).toBeTruthy())
    state = 'error'
    await act(async () => { await client.invalidateQueries({ queryKey: ['office-3d', 'state'] }) })
    await screen.findByText('Không tải được trạng thái văn phòng')
    expect(screen.getByText('Không tải được')).toBeTruthy()
    expect(screen.queryByText('1 có hoạt động gần đây')).toBeNull()
    expect(screen.getByText('Trạng thái agent: Chưa rõ')).toBeTruthy()
    expect(notify).not.toHaveBeenCalled()

    state = 'offline'
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    await waitFor(() => expect(screen.getByText('0 trực tuyến')).toBeTruthy())
    expect(notify).not.toHaveBeenCalled()
  })
})
