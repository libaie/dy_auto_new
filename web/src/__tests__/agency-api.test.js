import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()

vi.mock('../api/client.js', () => ({
  default: { get: mockGet, post: mockPost, patch: mockPatch },
}))

describe('agency API', () => {
  beforeEach(() => {
    mockGet.mockReset()
    mockPost.mockReset()
    mockPatch.mockReset()
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

  it('manages creative patch APIs', async () => {
    const {
      listAgencyCreativePatches,
      updateAgencyCreativePatch,
      approveAgencyCreativePatch,
      rejectAgencyCreativePatch,
      applyAgencyCreativePatch,
      applyApprovedAgencyCreativePatches,
      runAgencyAssetMultimodalReview,
    } = await import('../api/agency.js')

    await listAgencyCreativePatches({ series_id: 'sid' })
    await updateAgencyCreativePatch('patch-1', { after: { image_prompt: 'new prompt' } })
    await approveAgencyCreativePatch('patch-1')
    await rejectAgencyCreativePatch('patch-1', { reason: 'skip it' })
    await applyAgencyCreativePatch('patch-1')
    await applyApprovedAgencyCreativePatches({ run_id: 'run-1' })
    await runAgencyAssetMultimodalReview('asset-1')

    expect(mockGet).toHaveBeenCalledWith('/agency/creative-patches', { params: { series_id: 'sid' } })
    expect(mockPatch).toHaveBeenCalledWith('/agency/creative-patches/patch-1', { after: { image_prompt: 'new prompt' } })
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/approve')
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/reject', { reason: 'skip it' })
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/apply')
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/apply-approved', { run_id: 'run-1' })
    expect(mockPost).toHaveBeenCalledWith('/agency/assets/asset-1/multimodal-review')
  })
})
