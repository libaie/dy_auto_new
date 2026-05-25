import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  listReviewItems: vi.fn(() => Promise.resolve({ data: { ok: true, items: [] } })),
  reviewAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  push: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/videoProduction.js', () => ({
  listReviewItems: mocks.listReviewItems,
  reviewAsset: mocks.reviewAsset,
}))

describe('AIVideoReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listReviewItems.mockResolvedValue({ data: { ok: true, items: [] } })
  })

  it('renders loading state initially', async () => {
    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    expect(wrapper.text()).toContain('Loading review queue')
    await flushPromises()
    expect(wrapper.text()).toContain('No assets need human review')
  })

  it('renders review items after load', async () => {
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-1',
          run_id: 'run-1',
          frame_id: 'frame-001',
          version: 1,
          status: 'review_pending',
          stage: 'image_generation',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.text()).toContain('frame-001')
    expect(wrapper.text()).toContain('Pending review: 1')
  })

  it('approve button calls reviewAsset and reloads', async () => {
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-1',
          run_id: 'run-1',
          frame_id: 'frame-001',
          version: 1,
          status: 'review_pending',
          stage: 'image_generation',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const approveBtn = wrapper.find('button.bg-emerald-600')
    await approveBtn.trigger('click')
    await flushPromises()

    expect(mocks.reviewAsset).toHaveBeenCalledWith('asset-1', 'approve', 'Approved from review center')
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
  })
})
