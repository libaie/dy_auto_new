import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-123' } },
  router: { push: vi.fn() },
  getVideoProductionRun: vi.fn(),
  getRunProductionTree: vi.fn(),
  getRunReadiness: vi.fn(),
  runMockSchedulerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  runRealWorkerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  getSegmentDetail: vi.fn(),
  getRunCosts: vi.fn(),
  getProviderStageTasks: vi.fn(),
  getSegmentRetryImpact: vi.fn(),
  backfillRunTextArtifacts: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  retryProductionSegment: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  listAgencyRepairTasks: vi.fn(),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  getStoryboardImageState: vi.fn(() => Promise.resolve({ data: { ok: true, summary: {}, frames: [] } })),
  promoteStoryboardImageAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  getRunProductionTree: mocks.getRunProductionTree,
  getRunReadiness: mocks.getRunReadiness,
  runMockSchedulerStep: mocks.runMockSchedulerStep,
  runRealWorkerStep: mocks.runRealWorkerStep,
  getSegmentDetail: mocks.getSegmentDetail,
  getRunCosts: mocks.getRunCosts,
  getProviderStageTasks: mocks.getProviderStageTasks,
  getSegmentRetryImpact: mocks.getSegmentRetryImpact,
  backfillRunTextArtifacts: mocks.backfillRunTextArtifacts,
  retryProductionSegment: mocks.retryProductionSegment,
  startImageStage: mocks.startImageStage,
  syncImageStage: mocks.syncImageStage,
  startVideoStage: mocks.startVideoStage,
  syncVideoStage: mocks.syncVideoStage,
  startComposeStage: mocks.startComposeStage,
  syncComposeStage: mocks.syncComposeStage,
}))

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: mocks.listAgencyRepairTasks,
  retryAgencyRepairTask: mocks.retryAgencyRepairTask,
  authorizeAgencyRepairRetry: mocks.authorizeAgencyRepairRetry,
}))

vi.mock('../api/storyboardImages.js', () => ({
  getStoryboardImageState: mocks.getStoryboardImageState,
  promoteStoryboardImageAsset: mocks.promoteStoryboardImageAsset,
}))

function runPayload(status, runType = 'real_short_e2e', modelTrace = {}, consumedTextArtifacts = []) {
  return {
    data: {
      ok: true,
      run: {
        id: 'run-123',
        series_id: 'sid',
        episode_id: 'ep1',
        status,
        run_type: runType,
        current_stage: status,
        storyboard_json: { frames: [{ id: 'frame-1' }] },
        model_trace_json: modelTrace,
        consumed_text_artifacts: consumedTextArtifacts,
      },
      asset_summary: { image: { approved: 1 } },
    },
  }
}

function readinessPayload(overrides = {}) {
  return {
    data: {
      ok: true,
      readiness: {
        next_action: { label: '等待真人审查' },
        blocks: [{
          message: '图像审查未完成',
          repair_action: '打开审查中心',
          repair_route: '/ai-video-review?run_id=run-123',
        }],
        ...overrides,
      },
    },
  }
}

function treePayload() {
  return {
    data: {
      ok: true,
      plan: { id: 'plan-1', status: 'running', current_cost: 4.2, budget_limit: 10 },
      page: 1,
      page_size: 50,
      total_segments: 1,
      episodes: [{
        id: 'pe-1',
        order_index: 1,
        scenes: [{
          id: 'scene-1',
          scene_id: 'scene-a',
          shots: [{
            id: 'shot-1',
            shot_id: 'shot-a',
            segments: [{
              id: 'seg-1',
              segment_id: 'seg-a',
              status: 'failed',
              continuity_mode: 'continuous_action',
              duration_seconds: 5,
              version: 1,
            }],
          }],
        }],
      }],
    },
  }
}

function defaultResolvedApis(status, runType = 'real_short_e2e', modelTrace = {}) {
  mocks.getVideoProductionRun.mockResolvedValue(runPayload(status, runType, modelTrace))
  mocks.getRunReadiness.mockResolvedValue(readinessPayload())
  mocks.getRunProductionTree.mockResolvedValue(treePayload())
  mocks.getSegmentDetail.mockResolvedValue({
    data: {
      ok: true,
      segment: { id: 'seg-1', segment_id: 'seg-a' },
      latest_assets: {
        image: { id: 'asset-1', asset_type: 'image', frame_id: 'frame-1', status: 'approved', url: 'img.png' },
      },
      allowed_actions: ['retry'],
    },
  })
  mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 4.2, estimate_status: 'unknown' } })
  mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  mocks.getSegmentRetryImpact.mockResolvedValue({ data: { ok: true, allowed: true, estimated_extra_cost: 0 } })
  mocks.listAgencyRepairTasks.mockResolvedValue({
    data: {
      summary: { total: 0, active: 0, manual_required: 0, estimated_cost: 0 },
      items: [],
    },
  })
}

async function mountPage(status, runType = 'real_short_e2e', modelTrace = {}) {
  const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
  defaultResolvedApis(status, runType, modelTrace)
  const wrapper = mount(VideoProductionMonitorPage, {
    global: {
      mocks: {
        $router: mocks.router,
      },
    },
  })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

async function mountPageWithTreeFailure(status) {
  const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
  mocks.getVideoProductionRun.mockResolvedValue(runPayload(status))
  mocks.getRunReadiness.mockResolvedValue(readinessPayload())
  mocks.getRunProductionTree.mockRejectedValue({ response: { data: { detail: 'Production plan is not linked' } } })
  mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 4.2, estimate_status: 'unknown' } })
  mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  const wrapper = mount(VideoProductionMonitorPage, {
    global: {
      mocks: {
        $router: mocks.router,
      },
    },
  })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

const mountedWrappers = []

describe('VideoProductionMonitorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params.runId = 'run-123'
    mocks.runMockSchedulerStep.mockResolvedValue({ data: { ok: true } })
    mocks.runRealWorkerStep.mockResolvedValue({ data: { ok: true } })
    mocks.getStoryboardImageState.mockReset()
    mocks.getStoryboardImageState.mockResolvedValue({ data: { ok: true, summary: {}, frames: [] } })
    mocks.promoteStoryboardImageAsset.mockReset()
    mocks.promoteStoryboardImageAsset.mockResolvedValue({ data: { ok: true } })
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount()
    }
    vi.useRealTimers()
  })

  it('shows run type, readiness next action, and readiness blocks', async () => {
    const wrapper = await mountPage('image_review_pending')

    expect(wrapper.text()).toContain('真实短片')
    expect(wrapper.text()).toContain('等待真人审查')
    expect(wrapper.find('[data-test="readiness-blocks"]').text()).toContain('图像审查未完成')
    expect(wrapper.find('[data-test="readiness-blocks"]').text()).toContain('打开审查中心')
    expect(wrapper.find('[data-test="readiness-blocks"]').text()).toContain('/ai-video-review?run_id=run-123')
  })

  it('shows consumed AI text artifact versions for traceability', async () => {
    mocks.getVideoProductionRun.mockResolvedValue(runPayload('storyboard_ready', 'real_short_e2e', {}, [
      {
        artifact_id: 'artifact-series-bible',
        artifact_type: 'series_bible',
        version: 1,
        status: 'approved',
        target_type: 'series',
        target_id: 'series-1',
        source_type: 'ai',
      },
      {
        artifact_id: 'artifact-storyboard',
        artifact_type: 'storyboard',
        version: 3,
        status: 'approved',
        target_type: 'episode',
        target_id: 'episode-1',
        source_type: 'human_edit',
      },
    ]))
    mocks.getRunReadiness.mockResolvedValue(readinessPayload())
    mocks.getRunProductionTree.mockResolvedValue(treePayload())
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.listAgencyRepairTasks.mockResolvedValue({
      data: { summary: { total: 0, active: 0, manual_required: 0, estimated_cost: 0 }, items: [] },
    })

    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    mountedWrappers.push(wrapper)
    await flushPromises()

    const ledger = wrapper.find('[data-test="consumed-text-artifacts"]')
    expect(ledger.exists()).toBe(true)
    expect(ledger.text()).toContain('AI 文本版本')
    expect(ledger.text()).toContain('series_bible')
    expect(ledger.text()).toContain('v1')
    expect(ledger.text()).toContain('storyboard')
    expect(ledger.text()).toContain('v3')
    expect(ledger.text()).toContain('human_edit')
  })

  it('shows storyboard image readiness and promotes approved frame images', async () => {
    mocks.getStoryboardImageState.mockResolvedValue({
      data: {
        ok: true,
        summary: { total: 2, approved: 1, missing: 1, pending: 0, running: 0, blocked: 0 },
        frames: [
          {
            frame_id: 'shot-001',
            time_range: '0-2秒',
            status: 'approved',
            asset: {
              id: 'asset-approved',
              version: 1,
              url: '/static/image-creation/storyboard.png',
              allowed_actions: ['promote_to_video_asset'],
            },
          },
          { frame_id: 'shot-002', time_range: '2-4秒', status: 'missing', asset: null },
        ],
      },
    })

    const wrapper = await mountPage('storyboard_ready')

    expect(mocks.getStoryboardImageState).toHaveBeenCalledWith('ep1', { series_id: 'sid', run_id: 'run-123' })
    expect(wrapper.find('[data-test="storyboard-image-readiness"]').text()).toContain('分镜图')
    expect(wrapper.find('[data-test="storyboard-image-readiness"]').text()).toContain('已通过 1')
    expect(wrapper.find('[data-test="storyboard-image-readiness"]').text()).toContain('缺失 1')

    await wrapper.find('[data-test="promote-storyboard-image-asset-approved"]').trigger('click')
    await flushPromises()

    expect(mocks.promoteStoryboardImageAsset).toHaveBeenCalledWith('asset-approved', {
      run_id: 'run-123',
      frame_id: 'shot-001',
      episode_id: 'ep1',
      asset_version: 1,
    })
  })

  it('backfills missing consumed AI text artifacts from the monitor', async () => {
    const consumed = [{
      artifact_id: 'artifact-storyboard',
      artifact_type: 'storyboard',
      version: 1,
      status: 'approved',
      target_type: 'episode',
      target_id: 'episode-1',
      source_type: 'legacy_run_backfill',
    }]
    mocks.getVideoProductionRun
      .mockResolvedValueOnce(runPayload('completed'))
      .mockResolvedValue(runPayload('completed', 'real_short_e2e', {}, consumed))
    mocks.getRunReadiness.mockResolvedValue(readinessPayload({ blocks: [] }))
    mocks.getRunProductionTree.mockResolvedValue(treePayload())
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.listAgencyRepairTasks.mockResolvedValue({
      data: { summary: { total: 0, active: 0, manual_required: 0, estimated_cost: 0 }, items: [] },
    })

    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    mountedWrappers.push(wrapper)
    await flushPromises()

    const button = wrapper.find('[data-test="backfill-text-artifacts"]')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    await flushPromises()

    expect(mocks.backfillRunTextArtifacts).toHaveBeenCalledWith('run-123')
    expect(mocks.getVideoProductionRun).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-test="consumed-text-artifacts"]').text()).toContain('storyboard')
    expect(wrapper.find('[data-test="consumed-text-artifacts"]').text()).toContain('legacy_run_backfill')
  })

  it('shows agency auto repair tasks on the production monitor', async () => {
    mocks.listAgencyRepairTasks.mockResolvedValueOnce({
      data: {
        summary: { total: 1, active: 0, manual_required: 1, estimated_cost: 0 },
        items: [{
          id: 'repair-job-1',
          type: 'storyboard_missing_references',
          status: 'blocked',
          reason: '分镜缺少角色参考图',
          expected_result: '补齐参考后重新复审',
          repair_action_label: '去分镜处理',
          repair_route: '/series/s1',
          estimated_cost: 0,
          retry_actions: { retry_enabled: false },
        }],
      },
    })

    const wrapper = await mountPage('image_batch_running')

    expect(mocks.listAgencyRepairTasks).toHaveBeenCalledWith({ run_id: 'run-123', page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('分镜缺少角色参考图')
    expect(wrapper.text()).not.toMatch(/宸茶|閸|锟/)
  })

  it('keeps agency auto repair load failures visible on the production monitor', async () => {
    mocks.listAgencyRepairTasks.mockRejectedValueOnce(new Error('repair API unavailable'))

    const wrapper = await mountPage('image_batch_running')

    expect(mocks.listAgencyRepairTasks).toHaveBeenCalledWith({ run_id: 'run-123', page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('返修任务加载失败，请稍后重试')
  })

  it('shows mock worker controls for mock scale runs and runs one step', async () => {
    const wrapper = await mountPage('image_batch_running', 'mock_series_scale')

    const button = wrapper.find('[data-test="mock-worker-step"]')
    expect(wrapper.text()).toContain('模拟长剧调度')
    expect(button.exists()).toBe(true)
    expect(button.text()).toContain('模拟 worker')

    await button.trigger('click')
    await flushPromises()

    expect(mocks.runMockSchedulerStep).toHaveBeenCalledWith('run-123', { lease_id: 'ui-worker', batch_size: 1 })
    expect(mocks.getVideoProductionRun).toHaveBeenCalledTimes(2)
    expect(mocks.getRunReadiness).toHaveBeenCalledTimes(2)
    expect(mocks.getRunProductionTree).toHaveBeenCalledTimes(2)
    expect(mocks.getRunCosts).toHaveBeenCalledTimes(2)
  })

  it('does not run duplicate mock worker requests while an action is active', async () => {
    let resolveStep
    mocks.runMockSchedulerStep.mockImplementation(() => new Promise(resolve => {
      resolveStep = resolve
    }))
    const wrapper = await mountPage('image_batch_running', 'mock_series_scale')
    const button = wrapper.find('[data-test="mock-worker-step"]')

    button.trigger('click')
    await button.trigger('click')

    expect(mocks.runMockSchedulerStep).toHaveBeenCalledTimes(1)
    resolveStep({ data: { ok: true } })
    await flushPromises()
  })

  it('shows an error when the mock worker step fails', async () => {
    mocks.runMockSchedulerStep.mockRejectedValue(new Error('模拟 worker 执行失败'))
    const wrapper = await mountPage('image_batch_running', 'mock_series_scale')

    await wrapper.find('[data-test="mock-worker-step"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('模拟 worker 执行失败')
  })

  it.each([
    ['image_batch_running', '运行真实 worker 一步', mocks.runRealWorkerStep],
    ['image_approved', '启动视频片段', mocks.startVideoStage],
    ['video_batch_running', '运行真实 worker 一步', mocks.runRealWorkerStep],
    ['video_segments_approved', '合成最终视频', mocks.startComposeStage],
    ['composing', '运行真实 worker 一步', mocks.runRealWorkerStep],
  ])('calls the %s stage action from its button', async (status, label, actionMock) => {
    const wrapper = await mountPage(status)

    const button = wrapper.findAll('button').find(btn => btn.text().includes(label))
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    if (actionMock === mocks.runRealWorkerStep) {
      expect(actionMock).toHaveBeenCalledWith('run-123', { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })
    } else {
      expect(actionMock).toHaveBeenCalledWith('run-123')
    }
    expect(mocks.getVideoProductionRun).toHaveBeenCalledTimes(2)
  })

  it('opens the review center for runs that need review', async () => {
    const wrapper = await mountPage('video_review_pending')

    const button = wrapper.findAll('button').find(btn => btn.text().includes('打开审查中心'))
    expect(button).toBeTruthy()
    await button.trigger('click')

    expect(mocks.router.push).toHaveBeenCalledWith('/ai-video-review?run_id=run-123')
  })

  it('renders operator control room from run summary and segment detail', async () => {
    const wrapper = await mountPage('image_batch_running')

    expect(wrapper.text()).toContain('运行健康')
    expect(wrapper.text()).toContain('异常队列')
    await wrapper.find('button[data-test="segment-button"]').trigger('click')
    await flushPromises()

    expect(mocks.getSegmentDetail).toHaveBeenCalledWith('seg-1', { history_limit: 10 })
    expect(mocks.getProviderStageTasks).toHaveBeenCalledWith('run-123', { page: 1, page_size: 50 })
    expect(wrapper.find('[aria-live="polite"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="mobile-action-bar"]').exists()).toBe(true)
  })

  it('keeps manual sync controls out of the primary happy path while provider work is running', async () => {
    mocks.getVideoProductionRun.mockResolvedValue(runPayload('image_batch_running'))
    mocks.getRunReadiness.mockResolvedValue(readinessPayload())
    mocks.getRunProductionTree.mockResolvedValue({ data: { ok: true, episodes: [] } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })

    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-test="primary-next-action"]').text()).not.toContain('同步')
    expect(wrapper.find('[data-test="primary-next-action"]').text()).toContain('运行真实 worker 一步')
    expect(wrapper.find('[data-test="developer-sync-controls"]').text()).not.toContain('同步图片结果')
    expect(wrapper.find('[data-test="real-worker-step"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="developer-sync-controls"]').exists()).toBe(true)
  })

  it.each([
    ['image_batch_running', '运行真实 worker 一步', mocks.runRealWorkerStep],
    ['image_approved', '启动视频片段', mocks.startVideoStage],
    ['video_batch_running', '运行真实 worker 一步', mocks.runRealWorkerStep],
    ['video_segments_approved', '合成最终视频', mocks.startComposeStage],
    ['composing', '运行真实 worker 一步', mocks.runRealWorkerStep],
  ])('keeps the %s stage action available when the production tree is unavailable', async (status, label, actionMock) => {
    const wrapper = await mountPageWithTreeFailure(status)
    expect(wrapper.text()).toContain('Production plan is not linked')
    const button = wrapper.findAll('button').find(btn => btn.text().includes(label))
    expect(button).toBeTruthy()

    await button.trigger('click')
    await flushPromises()

    if (actionMock === mocks.runRealWorkerStep) {
      expect(actionMock).toHaveBeenCalledWith('run-123', { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })
    } else {
      expect(actionMock).toHaveBeenCalledWith('run-123')
    }
  })

  it('keeps the review center available when the production tree is unavailable', async () => {
    const wrapper = await mountPageWithTreeFailure('video_review_pending')

    expect(wrapper.text()).toContain('Production plan is not linked')
    const button = wrapper.findAll('button').find(btn => btn.text().includes('打开审查中心'))
    expect(button).toBeTruthy()
    await button.trigger('click')

    expect(mocks.router.push).toHaveBeenCalledWith('/ai-video-review?run_id=run-123')
  })

  it('automatically starts image generation when run autopilot is enabled', async () => {
    vi.useFakeTimers()
    await mountPage('storyboard_ready', 'real_short_e2e', { autopilot: { enabled: true } })

    await vi.runOnlyPendingTimersAsync()
    await flushPromises()

    expect(mocks.startImageStage).toHaveBeenCalledWith('run-123')
  })

  it('does not automatically start image generation without autopilot marker', async () => {
    vi.useFakeTimers()
    await mountPage('storyboard_ready')

    await vi.runOnlyPendingTimersAsync()
    await flushPromises()

    expect(mocks.startImageStage).not.toHaveBeenCalled()
  })

  it('polls running production status without autopilot and reveals the review gate', async () => {
    vi.useFakeTimers()
    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    defaultResolvedApis('image_batch_running')
    mocks.getVideoProductionRun
      .mockResolvedValueOnce(runPayload('image_batch_running'))
      .mockResolvedValue(runPayload('image_review_pending'))

    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    mountedWrappers.push(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('image_batch_running')
    expect(wrapper.get('[data-test="primary-next-action"]').text()).toContain('运行真实 worker 一步')

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()

    expect(mocks.getVideoProductionRun).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('image_review_pending')
    expect(wrapper.get('[data-test="primary-next-action"]').text()).toContain('需要审查')
    expect(mocks.startImageStage).not.toHaveBeenCalled()
  })

  it('refreshes the selected segment detail during status polling so new images appear without page refresh', async () => {
    vi.useFakeTimers()
    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    defaultResolvedApis('image_batch_running')
    mocks.getSegmentDetail
      .mockResolvedValueOnce({
        data: {
          ok: true,
          segment: { id: 'seg-1', segment_id: 'seg-a' },
          latest_assets: {},
          allowed_actions: ['retry'],
        },
      })
      .mockResolvedValue({
        data: {
          ok: true,
          segment: { id: 'seg-1', segment_id: 'seg-a' },
          latest_assets: {
            image: { id: 'asset-live', asset_type: 'image', frame_id: 'frame-1', status: 'review_pending', url: 'live.png' },
          },
          allowed_actions: ['retry'],
        },
      })

    const wrapper = mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    mountedWrappers.push(wrapper)
    await flushPromises()

    await wrapper.find('button[data-test="segment-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('暂无素材')

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()

    expect(mocks.getSegmentDetail).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('review_pending')
    expect(wrapper.text()).toContain('live.png')
  })

  it('drives a fully automatic real provider run across image, video, and compose stages', async () => {
    vi.useFakeTimers()
    const modelTrace = { autopilot: { enabled: true, source: 'episode_start' } }
    mocks.getVideoProductionRun
      .mockResolvedValueOnce(runPayload('storyboard_ready', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('image_batch_running', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('image_approved', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('video_batch_running', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('video_segments_approved', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('composing', 'real_short_e2e', modelTrace))
      .mockResolvedValueOnce(runPayload('completed', 'real_short_e2e', modelTrace))
    mocks.getRunReadiness.mockResolvedValue(readinessPayload({ blocks: [] }))
    mocks.getRunProductionTree.mockResolvedValue(treePayload())
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.listAgencyRepairTasks.mockResolvedValue({
      data: { summary: { total: 0, active: 0, manual_required: 0, estimated_cost: 0 }, items: [] },
    })

    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    mount(VideoProductionMonitorPage, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    await flushPromises()

    for (let i = 0; i < 6; i += 1) {
      await vi.runOnlyPendingTimersAsync()
      await flushPromises()
    }

    expect(mocks.startImageStage).toHaveBeenCalledWith('run-123')
    expect(mocks.runRealWorkerStep).toHaveBeenCalledTimes(3)
    expect(mocks.runRealWorkerStep).toHaveBeenNthCalledWith(1, 'run-123', { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })
    expect(mocks.runRealWorkerStep).toHaveBeenNthCalledWith(2, 'run-123', { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })
    expect(mocks.runRealWorkerStep).toHaveBeenNthCalledWith(3, 'run-123', { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })
    expect(mocks.startVideoStage).toHaveBeenCalledWith('run-123')
    expect(mocks.startComposeStage).toHaveBeenCalledWith('run-123')
  })
})
