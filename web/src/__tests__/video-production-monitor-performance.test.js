import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-1' } },
  router: { push: vi.fn() },
  getVideoProductionRun: vi.fn(),
  getRunReadiness: vi.fn(),
  getRunProductionTree: vi.fn(),
  getRunCosts: vi.fn(),
  getProviderStageTasks: vi.fn(),
  getSegmentDetail: vi.fn(),
  getSegmentRetryImpact: vi.fn(),
  retryProductionSegment: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  runMockSchedulerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  runRealWorkerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  getRunReadiness: mocks.getRunReadiness,
  getRunProductionTree: mocks.getRunProductionTree,
  getRunCosts: mocks.getRunCosts,
  getProviderStageTasks: mocks.getProviderStageTasks,
  getSegmentDetail: mocks.getSegmentDetail,
  getSegmentRetryImpact: mocks.getSegmentRetryImpact,
  retryProductionSegment: mocks.retryProductionSegment,
  runMockSchedulerStep: mocks.runMockSchedulerStep,
  runRealWorkerStep: mocks.runRealWorkerStep,
  startImageStage: mocks.startImageStage,
  syncImageStage: mocks.syncImageStage,
  startVideoStage: mocks.startVideoStage,
  syncVideoStage: mocks.syncVideoStage,
  startComposeStage: mocks.startComposeStage,
  syncComposeStage: mocks.syncComposeStage,
}))

describe('VideoProductionMonitorPage performance boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params.runId = 'run-1'
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'running', current_stage: 'image_generation', run_type: 'real_short_e2e' },
        asset_summary: {},
      },
    })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: {} } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true } })
    mocks.getRunProductionTree.mockResolvedValue({
      data: { ok: true, episodes: [], total_segments: 2400, page: 1, page_size: 50 },
    })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  })

  it('loads a bounded tree page and does not load segment detail by default', async () => {
    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    mount(VideoProductionMonitorPage)
    await flushPromises()

    expect(mocks.getRunProductionTree).toHaveBeenCalledWith('run-1', expect.objectContaining({ page: 1, page_size: 50 }))
    expect(mocks.getSegmentDetail).not.toHaveBeenCalled()
  })
})
