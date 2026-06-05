import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: {} },
  router: { push: vi.fn() },
  listReviewItems: vi.fn(() => Promise.resolve({ data: { ok: true, items: [] } })),
  getVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { status: 'image_review_pending', run_type: 'real_short_e2e' } } })),
  reviewAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  bulkReviewProductionAssets: vi.fn(() => Promise.resolve({ data: { ok: true, result: { approved: 1, skipped_stale: 0 } } })),
  startAssetRegeneration: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncAssetRegeneration: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  imageEditProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true, asset: { id: 'asset-2' } } })),
  voidProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  runRealWorkerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { summary: {}, items: [] } })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  listReviewItems: mocks.listReviewItems,
  reviewAsset: mocks.reviewAsset,
  bulkReviewProductionAssets: mocks.bulkReviewProductionAssets,
  startAssetRegeneration: mocks.startAssetRegeneration,
  syncAssetRegeneration: mocks.syncAssetRegeneration,
  imageEditProductionAsset: mocks.imageEditProductionAsset,
  voidProductionAsset: mocks.voidProductionAsset,
  syncImageStage: mocks.syncImageStage,
  runRealWorkerStep: mocks.runRealWorkerStep,
}))

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: mocks.listAgencyRepairTasks,
  retryAgencyRepairTask: mocks.retryAgencyRepairTask,
  authorizeAgencyRepairRetry: mocks.authorizeAgencyRepairRetry,
}))

describe('AIVideoReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
    mocks.router.push.mockImplementation(({ query }) => {
      mocks.route.query = query
      return Promise.resolve()
    })
    mocks.listReviewItems.mockResolvedValue({ data: { ok: true, items: [] } })
    mocks.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { status: 'image_review_pending', run_type: 'real_short_e2e' } } })
    mocks.imageEditProductionAsset.mockResolvedValue({ data: { ok: true, asset: { id: 'asset-2' } } })
    mocks.voidProductionAsset.mockResolvedValue({ data: { ok: true } })
    mocks.listAgencyRepairTasks.mockResolvedValue({ data: { summary: {}, items: [] } })
  })

  it('renders loading state initially', async () => {
    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    expect(wrapper.text()).toContain('正在加载审查队列')
    await flushPromises()
    expect(wrapper.text()).toContain('暂无需要人工审查的素材')
  })

  it('loads review queue with all default actionable statuses', async () => {
    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    mount(AIVideoReviewPage)
    await flushPromises()

    expect(mocks.listReviewItems).toHaveBeenCalledWith({
      run_id: undefined,
      statuses: 'review_pending,regenerating,failed,rejected',
    })
  })

  it('shows auto repair tasks in the review center for the current run', async () => {
    mocks.route.query = { run_id: 'run-1' }
    mocks.listAgencyRepairTasks.mockResolvedValue({
      data: {
        summary: { total: 1, active: 0, manual_required: 1, estimated_cost: 0 },
        items: [{
          id: 'repair-job-1',
          type: 'image_generation_failed',
          status: 'blocked',
          reason: '图像生成失败，需要重新提交',
          expected_result: '重新生成后回到图像审查',
          repair_action_label: '去处理图像问题',
          retry_actions: { retry_enabled: false },
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(mocks.listAgencyRepairTasks).toHaveBeenCalledWith({ run_id: 'run-1' })
    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('图像生成失败，需要重新提交')
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
          copy_status: 'persisted',
          checksum: 'sha256:asset-1',
          storage_path: 'video-production/asset-1.png',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.text()).toContain('frame-001')
    expect(wrapper.text()).toContain('待审查：1')
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
          copy_status: 'persisted',
          checksum: 'sha256:asset-1',
          storage_path: 'video-production/asset-1.png',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const approveBtn = wrapper.findAll('button').find(btn => btn.text().includes('通过当前版本'))
    await approveBtn.trigger('click')
    await flushPromises()

    expect(mocks.reviewAsset).toHaveBeenCalledWith('asset-1', 'approve', 'Approved from review center')
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
  })

  it('reject button calls reviewAsset with the provided reason and reloads', async () => {
    vi.stubGlobal('prompt', vi.fn(() => 'bad continuity'))
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

    const rejectBtn = wrapper.findAll('button').find(btn => btn.text().includes('驳回'))
    await rejectBtn.trigger('click')
    await flushPromises()

    expect(mocks.reviewAsset).toHaveBeenCalledWith('asset-1', 'reject', 'bad continuity')
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
    vi.unstubAllGlobals()
  })

  it('regenerate button calls startAssetRegeneration and reloads', async () => {
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-3',
          run_id: 'run-1',
          frame_id: 'frame-003',
          version: 1,
          asset_type: 'image',
          status: 'rejected',
          stage: 'image_generation',
          url: 'https://cdn.test/img3.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const regenBtn = wrapper.findAll('button').find(btn => btn.text() === '重新生成')
    await regenBtn.trigger('click')
    await flushPromises()

    expect(mocks.startAssetRegeneration).toHaveBeenCalledWith('asset-3')
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
  })

  it('shows reference evidence and submits image edit instruction with the selected version', async () => {
    mocks.imageEditProductionAsset.mockResolvedValue({
      data: { ok: true, status: 'pending', message: '改图任务已提交，等待生成结果同步。' },
    })
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-2',
          run_id: 'run-1',
          frame_id: 'frame-002',
          version: 3,
          asset_type: 'image',
          status: 'review_pending',
          stage: 'image_generation',
          copy_status: 'persisted',
          checksum: 'sha256:asset-2',
          storage_path: 'video-production/asset-2.png',
          url: 'https://cdn.test/img2.png',
          reference_evidence: {
            reference_urls: ['https://cdn.test/front.png', 'https://cdn.test/wide.png'],
            character_reference_urls: ['https://cdn.test/front.png'],
            style_reference_urls: ['https://cdn.test/wide.png'],
            scene_id: 'scene-1',
            character_ids: ['char-1'],
          },
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.text()).toContain('参考图依据')
    expect(wrapper.html()).toContain('https://cdn.test/front.png')
    expect(wrapper.text()).toContain('scene-1')
    expect(wrapper.text()).toContain('char-1')

    await wrapper.find('[data-test="open-image-edit"]').trigger('click')
    await wrapper.find('[data-test="image-edit-instruction"]').setValue('  修正脸部一致性  ')
    await wrapper.find('[data-test="submit-image-edit"]').trigger('click')
    await flushPromises()

    expect(mocks.imageEditProductionAsset).toHaveBeenCalledWith('asset-2', {
      instruction: '修正脸部一致性',
      expected_version: 3,
    })
    expect(wrapper.text()).toContain('改图任务已提交，等待生成结果同步。')
  })

  it('keeps pending image edit notice visible when reload returns an empty queue', async () => {
    mocks.imageEditProductionAsset.mockResolvedValue({
      data: { ok: true, status: 'pending', message: '改图任务已提交，等待生成结果同步。' },
    })
    mocks.listReviewItems
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-2',
            run_id: 'run-1',
            frame_id: 'frame-002',
            version: 3,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-2',
            storage_path: 'video-production/asset-2.png',
            url: 'https://cdn.test/img2.png',
          }],
        },
      })
      .mockResolvedValueOnce({ data: { ok: true, items: [] } })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    await wrapper.find('[data-test="open-image-edit"]').trigger('click')
    await wrapper.find('[data-test="image-edit-instruction"]').setValue('修正脸部一致性')
    await wrapper.find('[data-test="submit-image-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('改图任务已提交，等待生成结果同步。')
    expect(wrapper.text()).toContain('暂无需要人工审查的素材')
  })

  it('selects the returned image edit asset after reload', async () => {
    mocks.imageEditProductionAsset.mockResolvedValue({
      data: { ok: true, asset: { id: 'asset-2' } },
    })
    mocks.listReviewItems
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-1',
            run_id: 'run-1',
            frame_id: 'frame-001',
            version: 1,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-1',
            storage_path: 'video-production/asset-1.png',
            url: 'https://cdn.test/img1.png',
          }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [
            {
              id: 'asset-1',
              run_id: 'run-1',
              frame_id: 'frame-001',
              version: 1,
              asset_type: 'image',
              status: 'review_pending',
              stage: 'image_generation',
              copy_status: 'persisted',
              checksum: 'sha256:asset-1',
              storage_path: 'video-production/asset-1.png',
              url: 'https://cdn.test/img1.png',
            },
            {
              id: 'asset-2',
              run_id: 'run-1',
              frame_id: 'frame-002',
              version: 2,
              asset_type: 'image',
              status: 'review_pending',
              stage: 'image_generation',
              copy_status: 'persisted',
              checksum: 'sha256:asset-2',
              storage_path: 'video-production/asset-2.png',
              url: 'https://cdn.test/img2.png',
            },
          ],
        },
      })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    await wrapper.find('[data-test="open-image-edit"]').trigger('click')
    await wrapper.find('[data-test="image-edit-instruction"]').setValue('修正脸部一致性')
    await wrapper.find('[data-test="submit-image-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('素材 asset-2')
  })

  it('reloads the latest asset and shows a conflict message when image edit version is stale', async () => {
    mocks.imageEditProductionAsset.mockRejectedValue({
      response: { data: { detail: { code: 'STALE_ASSET_VERSION', message: 'stale' } } },
    })
    mocks.listReviewItems
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-old',
            run_id: 'run-1',
            frame_id: 'frame-old',
            version: 1,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-old',
            storage_path: 'video-production/asset-old.png',
            url: 'https://cdn.test/old.png',
          }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-latest',
            run_id: 'run-1',
            frame_id: 'frame-latest',
            version: 2,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-latest',
            storage_path: 'video-production/asset-latest.png',
            url: 'https://cdn.test/latest.png',
          }],
        },
      })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    await wrapper.find('[data-test="open-image-edit"]').trigger('click')
    await wrapper.find('[data-test="image-edit-instruction"]').setValue('修正脸部一致性')
    await wrapper.find('[data-test="submit-image-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('版本已过期')
    expect(wrapper.text()).toContain('素材 asset-latest')
    expect(wrapper.find('[data-test="image-edit-instruction"]').element.value).toBe('修正脸部一致性')
  })

  it('voids the selected asset with the selected version', async () => {
    vi.stubGlobal('prompt', vi.fn(() => 'bad frame'))
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-2',
          run_id: 'run-1',
          frame_id: 'frame-002',
          version: 3,
          asset_type: 'image',
          status: 'review_pending',
          stage: 'image_generation',
          copy_status: 'persisted',
          checksum: 'sha256:asset-2',
          storage_path: 'video-production/asset-2.png',
          url: 'https://cdn.test/img2.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const voidBtn = wrapper.findAll('button').find(btn => btn.text() === '作废当前版本')
    await voidBtn.trigger('click')
    await flushPromises()

    expect(mocks.voidProductionAsset).toHaveBeenCalledWith('asset-2', {
      comment: 'bad frame',
      expected_version: 3,
    })
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
    vi.unstubAllGlobals()
  })

  it('reloads the latest asset and shows a conflict message when void version is stale', async () => {
    vi.stubGlobal('prompt', vi.fn(() => 'bad frame'))
    mocks.voidProductionAsset.mockRejectedValue({
      response: { data: { detail: { code: 'STALE_ASSET_VERSION', message: 'stale' } } },
    })
    mocks.listReviewItems
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-old',
            run_id: 'run-1',
            frame_id: 'frame-old',
            version: 1,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-old',
            storage_path: 'video-production/asset-old.png',
            url: 'https://cdn.test/old.png',
          }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          items: [{
            id: 'asset-latest',
            run_id: 'run-1',
            frame_id: 'frame-latest',
            version: 2,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            copy_status: 'persisted',
            checksum: 'sha256:asset-latest',
            storage_path: 'video-production/asset-latest.png',
            url: 'https://cdn.test/latest.png',
          }],
        },
      })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const voidBtn = wrapper.findAll('button').find(btn => btn.text() === '作废当前版本')
    await voidBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('版本已过期')
    expect(wrapper.text()).toContain('素材 asset-latest')
    expect(mocks.voidProductionAsset).toHaveBeenCalledWith('asset-old', {
      comment: 'bad frame',
      expected_version: 1,
    })
    vi.unstubAllGlobals()
  })

  it('keeps the synchronous regeneration entry for regenerating assets', async () => {
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        items: [{
          id: 'asset-2',
          run_id: 'run-1',
          frame_id: 'frame-002',
          version: 2,
          asset_type: 'image',
          status: 'regenerating',
          stage: 'image_generation',
          url: 'https://cdn.test/img2.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const syncButton = wrapper.findAll('button').find(btn => btn.text().includes('同步重生成'))
    expect(syncButton).toBeTruthy()
    expect(wrapper.findAll('button').some(btn => btn.text() === '重新生成')).toBe(false)
    await syncButton.trigger('click')
    await flushPromises()

    expect(mocks.syncAssetRegeneration).toHaveBeenCalledWith('asset-2')
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
  })

  it('shows gate tabs with counts and loads the active final gate from route query', async () => {
    mocks.route.query = { run_id: 'run-1', asset_type: 'final_video', statuses: 'review_pending' }
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 2, video_segment: 3, final_video: 1 },
        items: [{
          id: 'asset-final',
          run_id: 'run-1',
          frame_id: 'final-cut',
          version: 1,
          asset_type: 'final_video',
          status: 'review_pending',
          stage: 'final_video',
          url: 'https://cdn.test/final.mp4',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.find('[data-test="gate-tab-image"]').text()).toContain('图像审查')
    expect(wrapper.find('[data-test="gate-tab-image"]').text()).toContain('2')
    expect(wrapper.find('[data-test="gate-tab-video-segment"]').text()).toContain('视频片段审查')
    expect(wrapper.find('[data-test="gate-tab-video-segment"]').text()).toContain('3')
    expect(wrapper.find('[data-test="gate-tab-final-video"]').text()).toContain('最终审查')
    expect(wrapper.find('[data-test="gate-tab-final-video"]').text()).toContain('1')
    expect(wrapper.text()).toContain('最终人工审查')
    expect(wrapper.text()).toContain('终审通过并入库')
    expect(wrapper.find('[data-test="bulk-approve"]').exists()).toBe(false)
    expect(mocks.listReviewItems).toHaveBeenCalledWith({
      run_id: 'run-1',
      statuses: 'review_pending',
      asset_type: 'final_video',
    })
  })

  it('keeps bulk approve for image and video segment gates', async () => {
    mocks.route.query = { run_id: 'run-1' }
    mocks.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { status: 'image_review_pending', run_type: 'mock_series_scale' } } })
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 1, video_segment: 1, final_video: 0 },
        items: [{
          id: 'asset-1',
          run_id: 'run-1',
          frame_id: 'frame-001',
          version: 1,
          asset_type: 'image',
          status: 'review_pending',
          stage: 'image_generation',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.find('[data-test="bulk-approve"]').exists()).toBe(true)
  })

  it('hides bulk approve for real short review gates', async () => {
    mocks.route.query = { run_id: 'run-1' }
    mocks.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { status: 'image_review_pending', run_type: 'real_short_e2e' } } })
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 1, video_segment: 0, final_video: 0 },
        items: [{
          id: 'asset-1',
          run_id: 'run-1',
          frame_id: 'frame-001',
          version: 1,
          asset_type: 'image',
          status: 'review_pending',
          stage: 'image_generation',
          url: 'https://cdn.test/img.png',
        }],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.find('[data-test="bulk-approve"]').exists()).toBe(false)
  })

  it('advances real short running image stages through the real worker', async () => {
    mocks.route.query = { run_id: 'run-1' }
    mocks.getVideoProductionRun.mockResolvedValue({
      data: { ok: true, run: { status: 'image_batch_running', run_type: 'real_short_e2e' } },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const syncButton = wrapper.findAll('button').find(btn => btn.text().includes('推进真实任务'))
    expect(syncButton).toBeTruthy()
    await syncButton.trigger('click')
    await flushPromises()

    expect(mocks.runRealWorkerStep).toHaveBeenCalledWith('run-1')
    expect(mocks.syncImageStage).not.toHaveBeenCalled()
  })

  it('keeps legacy running image stages on the legacy sync route', async () => {
    mocks.route.query = { run_id: 'run-1' }
    mocks.getVideoProductionRun.mockResolvedValue({
      data: { ok: true, run: { status: 'image_batch_running', run_type: 'legacy_episode_run' } },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    const syncButton = wrapper.findAll('button').find(btn => btn.text().includes('同步结果'))
    expect(syncButton).toBeTruthy()
    await syncButton.trigger('click')
    await flushPromises()

    expect(mocks.syncImageStage).toHaveBeenCalledWith('run-1')
    expect(mocks.runRealWorkerStep).not.toHaveBeenCalled()
  })

  it('hides bulk approve when the queue contains any final video item', async () => {
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 1, video_segment: 0, final_video: 1 },
        items: [
          {
            id: 'asset-1',
            run_id: 'run-1',
            frame_id: 'frame-001',
            version: 1,
            asset_type: 'image',
            status: 'review_pending',
            stage: 'image_generation',
            url: 'https://cdn.test/img.png',
          },
          {
            id: 'asset-final',
            run_id: 'run-1',
            frame_id: 'final-cut',
            version: 1,
            asset_type: 'final_video',
            status: 'review_pending',
            stage: 'final_video',
            url: 'https://cdn.test/final.mp4',
          },
        ],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    expect(wrapper.find('[data-test="bulk-approve"]').exists()).toBe(false)
  })

  it('updates route query and reloads when a gate tab is clicked', async () => {
    mocks.route.query = { run_id: 'run-1', statuses: 'review_pending', page: '2' }
    mocks.listReviewItems.mockResolvedValue({
      data: {
        ok: true,
        gate_counts: { image: 1, video_segment: 4, final_video: 0 },
        items: [],
      },
    })

    const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
    const wrapper = mount(AIVideoReviewPage)
    await flushPromises()

    await wrapper.find('[data-test="gate-tab-video-segment"]').trigger('click')
    await flushPromises()

    expect(mocks.router.push).toHaveBeenCalledWith({
      query: {
        run_id: 'run-1',
        statuses: 'review_pending',
        page: '2',
        asset_type: 'video_segment',
      },
    })
    expect(mocks.listReviewItems).toHaveBeenCalledTimes(2)
    expect(mocks.listReviewItems).toHaveBeenLastCalledWith({
      run_id: 'run-1',
      statuses: 'review_pending',
      asset_type: 'video_segment',
    })
  })
})
