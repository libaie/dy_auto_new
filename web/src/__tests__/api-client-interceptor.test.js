import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('API client interceptor', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  async function loadClient() {
    let rejectHandler
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => ({
          interceptors: {
            request: { use: vi.fn() },
            response: {
              use: vi.fn((resolve, reject) => {
                rejectHandler = reject
              }),
            },
          },
        })),
      },
    }))
    const clientModule = await import('../api/client.js')
    return { clientModule, rejectHandler }
  }

  it('does not redirect on silent 401 responses', async () => {
    const { clientModule, rejectHandler } = await loadClient()
    const authStore = { logout: vi.fn() }
    const router = { push: vi.fn() }
    clientModule.setupAuthInterceptor(authStore, router)

    await expect(rejectHandler({
      response: { status: 401 },
      config: { silent: true },
    })).rejects.toMatchObject({ response: { status: 401 } })

    expect(authStore.logout).not.toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('still redirects on normal 401 responses', async () => {
    const { clientModule, rejectHandler } = await loadClient()
    const authStore = { logout: vi.fn() }
    const router = { push: vi.fn() }
    clientModule.setupAuthInterceptor(authStore, router)

    await expect(rejectHandler({
      response: { status: 401 },
      config: {},
    })).rejects.toMatchObject({ response: { status: 401 } })

    expect(authStore.logout).toHaveBeenCalledOnce()
    expect(router.push).toHaveBeenCalledWith('/login')
  })

  it('does not show global toasts for silent optional failures', async () => {
    const { clientModule, rejectHandler } = await loadClient()
    const toastStore = { error: vi.fn() }
    clientModule.setupToastInterceptor(toastStore)

    await expect(rejectHandler({
      response: { status: 404, data: { detail: 'Not Found' } },
      config: { silent: true },
    })).rejects.toMatchObject({ response: { status: 404 } })

    expect(toastStore.error).not.toHaveBeenCalled()
  })
})
