import { describe, expect, it, vi } from 'vitest'

describe('vite proxy defaults', () => {
  it('targets the dy_auto backend port when VITE_API_PROXY_TARGET is unset', async () => {
    delete process.env.VITE_API_PROXY_TARGET
    vi.resetModules()

    const config = (await import('../../vite.config.js')).default

    expect(config.server.proxy['/api'].target).toBe('http://localhost:8001')
    expect(config.server.proxy['/static'].target).toBe('http://localhost:8001')
  })
})
