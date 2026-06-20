import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-1' } },
  router: { push: vi.fn() },
  getVideoProductionRun: vi.fn(),
  getRunProductionTree: vi.fn(),
  getRunReadiness: vi.fn(),
  getSegmentDetail: vi.fn(),
  getRunCosts: vi.fn(),
  getProviderStageTasks: vi.fn(),
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
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { summary: {}, items: [] } })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  getRunProductionTree: mocks.getRunProductionTree,
  getRunReadiness: mocks.getRunReadiness,
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

describe('Production control room autopilot state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_batch_running', current_stage: 'image_generation', storyboard_json: { frames: [] } },
        asset_summary: {},
      },
    })
    mocks.getRunProductionTree.mockResolvedValue({ data: { ok: true, episodes: [] } })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { next_action: { label: '生成任务运行中' }, blocks: [] } } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
  })

  it('shows provider work as the primary path and tucks sync controls into developer tools', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })
    await flushPromises()

    const primaryAction = wrapper.find('[data-test="primary-next-action"]')
    const developerControls = wrapper.find('[data-test="developer-sync-controls"]')

    expect(primaryAction.exists()).toBe(true)
    expect(primaryAction.attributes('disabled')).toBeDefined()
    expect(primaryAction.text()).not.toContain('Sync')
    expect(developerControls.exists()).toBe(true)
    expect(developerControls.findAll('button').length).toBeGreaterThan(0)
  })
})
