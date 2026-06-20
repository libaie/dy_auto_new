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
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { items: [], summary: {} } })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
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

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: mocks.listAgencyRepairTasks,
  retryAgencyRepairTask: mocks.retryAgencyRepairTask,
  authorizeAgencyRepairRetry: mocks.authorizeAgencyRepairRetry,
}))

describe('VideoProductionMonitorPage responsive layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_approved', current_stage: 'image_review', storyboard_json: { frames: [] } },
        asset_summary: {},
      },
    })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { blocks: [] } } })
    mocks.getRunProductionTree.mockResolvedValue({
      data: {
        ok: true,
        plan: { id: 'plan-1', status: 'ready', current_cost: 0, budget_limit: 10 },
        page: 1,
        page_size: 50,
        total_segments: 0,
        episodes: [],
      },
    })
    mocks.getSegmentDetail.mockResolvedValue({ data: { ok: true, latest_assets: {}, allowed_actions: [] } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.getSegmentRetryImpact.mockResolvedValue({ data: { ok: true, allowed: true } })
  })

  it('uses a single-column mobile layout that expands to a three-pane desktop control room', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    await flushPromises()

    const controlRoom = wrapper.find('[data-test="control-room-grid"]')
    expect(controlRoom.exists()).toBe(true)
    expect(wrapper.text()).toContain('生产树')
    expect(wrapper.text()).toContain('片段预览')
    expect(wrapper.text()).toContain('操作')
    expect(wrapper.find('[data-test="mobile-action-bar"]').exists()).toBe(true)
  })
})
