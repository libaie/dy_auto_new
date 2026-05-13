import { describe, it, expect } from 'vitest'
import { NAV_ITEMS } from '../constants/navigation.js'

describe('NAV_ITEMS', () => {
  it('contains all required new menu items', () => {
    const paths = NAV_ITEMS.map(i => i.path)
    expect(paths).toContain('/series')
    expect(paths).toContain('/characters')
    expect(paths).toContain('/ai-config')
    expect(paths).toContain('/video-studio')
  })

  it('every item has name, path, and icon', () => {
    for (const item of NAV_ITEMS) {
      expect(item.name).toBeTruthy()
      expect(item.path).toBeTruthy()
      expect(item.icon).toBeTruthy()
    }
  })

  it('no duplicate paths', () => {
    const paths = NAV_ITEMS.map(i => i.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('series management is before video management', () => {
    const seriesIdx = NAV_ITEMS.findIndex(i => i.path === '/series')
    const videosIdx = NAV_ITEMS.findIndex(i => i.path === '/videos')
    expect(seriesIdx).toBeLessThan(videosIdx)
  })
})
