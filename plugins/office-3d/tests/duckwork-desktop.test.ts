/** Actual Duckwork SDK/context/registry; no source-text assertions or synthetic SDK. */
import { afterEach, describe, expect, it } from 'vitest'
import office from '../desktop/plugin.js'
import { createPluginContext } from '../../../apps/desktop/src/contrib/plugin'
import { registry } from '../../../apps/desktop/src/contrib/registry'
import { $pluginDecisions, pluginActive } from '../../../apps/desktop/src/contrib/plugins-store'
import { ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS, PALETTE_AREA, KEYBINDS_AREA } from '@duckwork/plugin-sdk'

const disposers: (() => void)[] = []
const areas = [ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS.right, PALETTE_AREA, KEYBINDS_AREA]
afterEach(() => {
  disposers.splice(0).reverse().forEach(dispose => dispose())
  $pluginDecisions.set({})
})

describe('bundled Office 3D Duckwork SDK', () => {
  it('imports and registers its route, nav, chip and commands without a disk plugin or Developer Mode', () => {
    const ctx = createPluginContext(office.id, dispose => disposers.push(dispose))
    expect(pluginActive(office.id, office.defaultEnabled)).toBe(true)
    office.register(ctx)
    const route = registry.getArea(ROUTES_AREA).find(c => c.id === 'office-3d:page')
    expect(route?.data).toEqual({ path: '/office-3d' })
    expect(typeof route?.render).toBe('function')
    expect(registry.getArea(SIDEBAR_NAV_AREA).find(c => c.id === 'office-3d:nav')?.data)
      .toMatchObject({ path: '/office-3d', label: 'Office' })
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
