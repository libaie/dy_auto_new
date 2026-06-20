import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-empty' } },
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

describe('Production control room empty states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-empty', status: 'storyboard_ready', current_stage: 'storyboard_ready', storyboard_json: { frames: [] } },
        asset_summary: {},
      },
    })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { blocks: [] } } })
    mocks.getRunProductionTree.mockResolvedValue({ data: { ok: true, episodes: [], total_segments: 0 } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  })

  it('shows clear empty states without hiding the control room', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })
    await flushPromises()

    expect(wrapper.find('[data-test="control-room-grid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无片段')
    expect(wrapper.text()).toContain('未选择片段')
  })
})
