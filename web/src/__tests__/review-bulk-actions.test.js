import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: { run_id: 'run-1' } },
  router: { push: vi.fn() },
  listReviewItems: vi.fn(),
  bulkReviewProductionAssets: vi.fn(() => Promise.resolve({ data: { ok: true, result: { approved: 2, skipped_stale: 1 } } })),
  imageEditProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  voidProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { items: [], summary: {} } })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}))
vi.mock('../api/videoProduction.js', () => ({
  listReviewItems: mocks.listReviewItems,
  bulkReviewProductionAssets: mocks.bulkReviewProductionAssets,
  getVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { status: 'image_review_pending', run_type: 'mock_series_scale' } } })),
  reviewAsset: vi.fn(),
  retryAssetPersistence: vi.fn(),
  startAssetRegeneration: vi.fn(),
  syncAssetRegeneration: vi.fn(),
  syncImageStage: vi.fn(),
  runRealWorkerStep: vi.fn(),
  imageEditProductionAsset: mocks.imageEditProductionAsset,
  voidProductionAsset: mocks.voidProductionAsset,
}))

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: mocks.listAgencyRepairTasks,
  retryAgencyRepairTask: mocks.retryAgencyRepairTask,
  authorizeAgencyRepairRetry: mocks.authorizeAgencyRepairRetry,
}))

describe('AIVideoReviewPage bulk actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = { run_id: 'run-1' }
    mocks.router.push.mockImplementation(({ query }) => {
      mocks.route.query = query
      return Promise.resolve()
    })
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [
          { id: 'a1', frame_id: 'seg-1', version: 1, status: 'review_pending', stage: 'image_generation', asset_type: 'image', url: 'a.png', copy_status: 'persisted', checksum: 'sha256:a1', storage_path: 'assets/a1.png' },
          { id: 'a2', frame_id: 'seg-2', version: 1, status: 'review_pending', stage: 'image_generation', asset_type: 'image', url: 'b.png', copy_status: 'persisted', checksum: 'sha256:a2', storage_path: 'assets/a2.png' },
        ],
      },
    })
  })

  it('bulk approves selected assets after impact confirmation', async () => {
    const Page = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    await wrapper.find('button[data-test="bulk-approve"]').trigger('click')
    await flushPromises()

    expect(mocks.bulkReviewProductionAssets).toHaveBeenCalledWith({
      asset_ids: ['a1', 'a2'],
      action: 'approve',
      comment: 'Bulk approved from review center',
    })
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已选 0 个')
    expect(wrapper.text()).toContain('已通过 2 个，跳过过期 1 个。')
  })
})
