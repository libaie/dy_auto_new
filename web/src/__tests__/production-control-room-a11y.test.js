import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-1' } },
  router: { push: vi.fn() },
  getVideoProductionRun: vi.fn(),
  getRunReadiness: vi.fn(),
  getRunProductionTree: vi.fn(),
  getSegmentDetail: vi.fn(),
  getRunCosts: vi.fn(),
  getProviderStageTasks: vi.fn(),
  getSegmentRetryImpact: vi.fn(),
  runMockSchedulerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  runRealWorkerStep: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  retryProductionSegment: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncVideoStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  syncComposeStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { ok: true, items: [], summary: {} } })),
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  getRunReadiness: mocks.getRunReadiness,
  getRunProductionTree: mocks.getRunProductionTree,
  getSegmentDetail: mocks.getSegmentDetail,
  getRunCosts: mocks.getRunCosts,
  getProviderStageTasks: mocks.getProviderStageTasks,
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

describe('Production control room accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_review_pending', current_stage: 'image_review', storyboard_json: { frames: [] } },
        asset_summary: {},
      },
    })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { blocks: [] } } })
    mocks.getRunProductionTree.mockResolvedValue({
      data: {
        ok: true,
        episodes: [{ id: 'ep-1', scenes: [{ id: 'sc-1', shots: [{ id: 'shot-1', segments: [{ id: 'seg-1', segment_id: 'seg-1', status: 'failed_retryable' }] }] }] }],
      },
    })
    mocks.getSegmentDetail.mockResolvedValue({ data: { ok: true, latest_assets: {}, allowed_actions: ['retry'] } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  })

  it('announces status changes and supports keyboard selection on segment buttons', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })
    await flushPromises()

    const live = wrapper.find('[aria-live="polite"]')
    expect(live.exists()).toBe(true)

    const segmentButton = wrapper.find('[data-test="segment-button"]')
    await segmentButton.trigger('keydown.space')
    await flushPromises()
    expect(segmentButton.attributes('aria-current')).toBe('true')
    expect(mocks.getSegmentDetail).toHaveBeenCalledWith('seg-1', { history_limit: 10 })
  })
})
