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
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({ data: { items: [], summary: {} } })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
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

vi.mock('../api/agency.js', () => ({
  listAgencyRepairTasks: mocks.listAgencyRepairTasks,
  retryAgencyRepairTask: mocks.retryAgencyRepairTask,
  authorizeAgencyRepairRetry: mocks.authorizeAgencyRepairRetry,
}))

describe('VideoProductionMonitorPage boundary states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params.runId = 'run-1'
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'running', current_stage: 'image_generation', run_type: 'real_short_e2e' },
        asset_summary: { image: { storage_failed: 1 } },
      },
    })
    mocks.getRunReadiness.mockResolvedValue({
      data: {
        ok: true,
        readiness: {
          next_action: { label: '等待调度' },
          next_repair_action: { label: '重试资产持久化', route: '/ai-video-review?run_id=run-1' },
          provider_throttle: {
            active_tasks: 1,
            max_concurrent_tasks: 1,
            retry_after: '2026-06-01T12:00:00Z',
          },
        },
      },
    })
    mocks.getRunCosts.mockResolvedValue({
      data: {
        ok: true,
        active_reserved_cost: 0.2,
        stale_needs_repair_cost: 0.1,
        settled_cost: 0.3,
        released_cost: 0,
      },
    })
    mocks.getRunProductionTree.mockResolvedValue({ data: { ok: true, episodes: [], total_segments: 0, page: 1, page_size: 50 } })
    mocks.getProviderStageTasks.mockResolvedValue({
      data: {
        ok: true,
        tasks: [{
          id: 'task-1',
          stage: 'image_generation',
          provider: 'pixelle',
          model_name: 'seedance',
          status: 'sync_required',
          cost_reservation: { status: 'stale_needs_repair', reserved_cost: 0.1, currency: 'CNY' },
        }],
      },
    })
  })

  it('renders repair CTA, provider throttle, cost reservation, stage task, and storage failed state', async () => {
    const VideoProductionMonitorPage = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(VideoProductionMonitorPage)
    await flushPromises()

    expect(wrapper.text()).toContain('重试资产持久化')
    expect(wrapper.text()).toContain('Provider 并发额度')
    expect(wrapper.text()).toContain('待修复预留')
    expect(wrapper.text()).toContain('存储失败')
    expect(wrapper.text()).toContain('Provider 阶段任务')
    expect(wrapper.text()).toContain('pixelle')
  })
})
