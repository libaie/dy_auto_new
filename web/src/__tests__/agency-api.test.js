import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()

vi.mock('../api/client.js', () => ({
  default: { get: mockGet },
}))

describe('agency API', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('loads expert detail and paginated invocations', async () => {
    const { getAgencyExpert, listAgencyInvocations } = await import('../api/agency.js')

    await getAgencyExpert('prompt_engineer')
    await listAgencyInvocations({ series_id: 'sid', page: 1, page_size: 20 })

    expect(mockGet).toHaveBeenCalledWith('/agency/experts/prompt_engineer')
    expect(mockGet).toHaveBeenCalledWith('/agency/invocations', {
      params: { series_id: 'sid', page: 1, page_size: 20 },
    })
  })

  it('loads invocation detail by id', async () => {
    const { getAgencyInvocation } = await import('../api/agency.js')

    await getAgencyInvocation('inv-1')

    expect(mockGet).toHaveBeenCalledWith('/agency/invocations/inv-1')
  })
})
