import { describe, it, expect } from 'vitest'
import { NAV_CATEGORIES, ROUTE_CATEGORY_MAP, getCategoryByRoute } from '../constants/navigation.js'

function allItems() {
  return NAV_CATEGORIES.flatMap(c => c.items)
}

describe('NAV_CATEGORIES', () => {
  it('contains all 5 categories', () => {
    const keys = NAV_CATEGORIES.map(c => c.key)
    expect(keys).toEqual(['ops', 'tasks', 'data', 'ai-video', 'system'])
  })

  it('every category has key, label, and items', () => {
    for (const cat of NAV_CATEGORIES) {
      expect(cat.key).toBeTruthy()
      expect(cat.label).toBeTruthy()
      expect(Array.isArray(cat.items)).toBe(true)
      expect(cat.items.length).toBeGreaterThan(0)
    }
  })

  it('contains all required menu items', () => {
    const paths = allItems().map(i => i.path)
    expect(paths).toContain('/series')
    expect(paths).toContain('/characters')
    expect(paths).toContain('/ai-config')
    expect(paths).toContain('/video-studio')
  })

  it('every item has name, path, and icon', () => {
    for (const item of allItems()) {
      expect(item.name).toBeTruthy()
      expect(item.path).toBeTruthy()
      expect(item.icon).toBeTruthy()
    }
  })

  it('no duplicate paths across all categories', () => {
    const paths = allItems().map(i => i.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('series management is before video management in AI video category', () => {
    const aiCat = NAV_CATEGORIES.find(c => c.key === 'ai-video')
    const seriesIdx = aiCat.items.findIndex(i => i.path === '/series')
    const videosIdx = aiCat.items.findIndex(i => i.path === '/videos')
    expect(seriesIdx).toBeLessThan(videosIdx)
  })
})

describe('ROUTE_CATEGORY_MAP', () => {
  it('maps every static route to a valid category', () => {
    for (const [path, key] of Object.entries(ROUTE_CATEGORY_MAP)) {
      expect(NAV_CATEGORIES.some(c => c.key === key)).toBe(true)
    }
  })

  it('has no orphan keys — all keys belong to a NAV_CATEGORIES entry', () => {
    const validKeys = new Set(NAV_CATEGORIES.map(c => c.key))
    const mapKeys = new Set(Object.values(ROUTE_CATEGORY_MAP))
    for (const key of mapKeys) {
      expect(validKeys.has(key)).toBe(true)
    }
  })
})

describe('getCategoryByRoute', () => {
  it('returns ops for /', () => {
    expect(getCategoryByRoute({ path: '/' })).toBe('ops')
  })

  it('returns tasks for /tasks', () => {
    expect(getCategoryByRoute({ path: '/tasks' })).toBe('tasks')
  })

  it('returns ai-video for /video-studio', () => {
    expect(getCategoryByRoute({ path: '/video-studio' })).toBe('ai-video')
  })

  it('returns system for /settings', () => {
    expect(getCategoryByRoute({ path: '/settings' })).toBe('system')
  })

  it('matches dynamic route /series/:id via matched[0].path', () => {
    expect(getCategoryByRoute({
      path: '/series/abc123',
      matched: [{ path: '/series/:id' }],
    })).toBe('ai-video')
  })

  it('matches dynamic route /director/:x/:y via matched[0].path', () => {
    expect(getCategoryByRoute({
      path: '/director/s1/e1',
      matched: [{ path: '/director/:seriesId/:episodeId' }],
    })).toBe('ai-video')
  })

  it('falls back to ops for unknown routes', () => {
    expect(getCategoryByRoute({ path: '/nonexistent' })).toBe('ops')
  })
})
