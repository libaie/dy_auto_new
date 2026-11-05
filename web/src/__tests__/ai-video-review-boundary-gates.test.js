import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: { run_id: 'run-1' } },
  router: { push: vi.fn() },
  listReviewItems: vi.fn(),
  getVideoProductionRun: vi.fn(),
  reviewAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  bulkReviewProductionAssets: vi.fn(() => Promise.resolve({ data: { ok: true, result: { approved: 1, skipped_stale: 0 } } })),
  retryAssetPersistence: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startAssetRegeneration: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncAssetRegeneration: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}))

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { ok: true, items: [], summary: {} } })),
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  listReviewItems: mocks.listReviewItems,
  reviewAsset: mocks.reviewAsset,
  bulkReviewProductionAssets: mocks.bulkReviewProductionAssets,
  retryAssetPersistence: mocks.retryAssetPersistence,
  startAssetRegeneration: mocks.startAssetRegeneration,
  syncAssetRegeneration: mocks.syncAssetRegeneration,
  syncImageStage: mocks.syncImageStage,
}))

function reviewAssetPayload(overrides = {}) {
  return {
    id: 'asset-1',
    run_id: 'run-1',
    frame_id: 'frame-001',
    version: 1,
    asset_type: 'image',
    status: 'review_pending',
    stage: 'image_generation',
    url: 'https://cdn.test/img.png',
    copy_status: 'persisted',
    checksum: 'sha256:asset-1',
    storage_path: 'video-production/asset-1.png',
    ...overrides,
  }
}

async function mountWithAsset(asset) {
  return mountWithAssets([asset])
}

async function mountWithAssets(assets) {
  mocks.listReviewItems.mockResolvedValue({
    data: {
      ok: true,
      items: assets,
      gate_counts: { image: assets.length, video_segment: 0, final_video: 0 },
    },
  })
  const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
  const wrapper = mount(AIVideoReviewPage)
  await flushPromises()
  return wrapper
}

describe('AIVideoReviewPage boundary approval gates', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = { run_id: 'run-1' }
    mocks.getVideoProductionRun.mockResolvedValue({
      data: { ok: true, run: { status: 'image_review_pending', run_type: 'real_short_e2e' } },
    })
  })

  it.each([
    [reviewAssetPayload({ copy_status: 'registered' }), '资产尚未持久化'],
    [reviewAssetPayload({ status: 'superseded' }), '旧版本不能审批'],
    [reviewAssetPayload({ status: 'failed' }), '资产不在待审查状态'],
    [reviewAssetPayload({ permission: { can_approve: false } }), '当前账号没有审批权限'],
  ])('blocks approval and shows the reason for asset %j', async (asset, reason) => {
    const wrapper = await mountWithAsset(asset)

    const approveButton = wrapper.find('[data-test="approve-asset"]')
    expect(approveButton.attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="approval-disabled-reason"]').text()).toContain(reason)

    await approveButton.trigger('click')
    await flushPromises()
    expect(mocks.reviewAsset).not.toHaveBeenCalled()
  })

  it('shows a persistence retry entry for storage failed assets', async () => {
    const wrapper = await mountWithAsset(reviewAssetPayload({
      status: 'storage_failed',
      copy_status: 'storage_failed',
      storage_error_json: { message: '远端文件下载失败' },
    }))

    expect(wrapper.text()).toContain('远端文件下载失败')
    const retryButton = wrapper.find('[data-test="retry-asset-persistence"]')
    expect(retryButton.exists()).toBe(true)

    await retryButton.trigger('click')
    await flushPromises()

    expect(mocks.retryAssetPersistence).toHaveBeenCalledWith('asset-1')
  })

  it('excludes unsafe assets from bulk approval', async () => {
    mocks.getVideoProductionRun.mockResolvedValue({
      data: { ok: true, run: { status: 'image_review_pending', run_type: 'mock_series_scale' } },
    })
    const wrapper = await mountWithAssets([
      reviewAssetPayload({ id: 'asset-safe', frame_id: 'frame-safe' }),
      reviewAssetPayload({ id: 'asset-unsafe', frame_id: 'frame-unsafe', copy_status: 'registered' }),
    ])

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes[1].attributes('disabled')).toBeDefined()
    await checkboxes[0].setValue(true)
    await checkboxes[1].trigger('click')
    await wrapper.find('[data-test="bulk-approve"]').trigger('click')
    await flushPromises()

    expect(mocks.bulkReviewProductionAssets).toHaveBeenCalledWith({
      asset_ids: ['asset-safe'],
      action: 'approve',
      comment: 'Bulk approved from review center',
    })
  })
})
