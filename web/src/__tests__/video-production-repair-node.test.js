import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { runId: 'run-123' } },
  router: { push: vi.fn() },
  getVideoProductionRun: vi.fn(),
  getRunProductionTree: vi.fn(),
  getRunReadiness: vi.fn(),
  getRunCosts: vi.fn(),
  getProviderStageTasks: vi.fn(),
  getSegmentDetail: vi.fn(),
  getSegmentRetryImpact: vi.fn(),
  retryProductionSegment: vi.fn(),
  runMockSchedulerStep: vi.fn(),
  runRealWorkerStep: vi.fn(),
  startImageStage: vi.fn(),
  syncImageStage: vi.fn(),
  startVideoStage: vi.fn(),
  syncVideoStage: vi.fn(),
  startComposeStage: vi.fn(),
  syncComposeStage: vi.fn(),
  listAgencyRepairTasks: vi.fn(),
  retryAgencyRepairTask: vi.fn(),
  authorizeAgencyRepairRetry: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
}))

vi.mock('../api/videoProduction.js', () => ({
  getVideoProductionRun: mocks.getVideoProductionRun,
  getRunProductionTree: mocks.getRunProductionTree,
  getRunReadiness: mocks.getRunReadiness,
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

describe('VideoProductionMonitorPage repair node', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-123', status: 'image_batch_running', run_type: 'real_short_e2e', current_stage: 'image_batch_running', storyboard_json: { frames: [] } },
        asset_summary: {},
      },
    })
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { next_action: { label: '等待调度' }, blocks: [] } } })
    mocks.getRunProductionTree.mockResolvedValue({ data: { ok: true, plan: { id: 'plan-1' }, episodes: [], total_segments: 0 } })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 0 } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.listAgencyRepairTasks.mockResolvedValue({
      data: {
        summary: { total: 2, active: 1, manual_required: 1, estimated_cost: 0.5 },
        items: [{
          id: 'repair-job-1',
          type: 'storyboard_missing_references',
          status: 'blocked',
          reason: '分镜缺少角色参考图',
          expected_result: '补齐后复审',
          repair_action_label: '去系列详情补分镜参考',
          estimated_cost: 0,
          retry_actions: { retry_enabled: false },
        }],
      },
    })
  })

  it('shows aggregated repair counts before details', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })
    await flushPromises()

    expect(wrapper.find('[data-test="auto-repair-summary"]').text()).toContain('全部 2')
    expect(wrapper.find('[data-test="auto-repair-summary"]').text()).toContain('需人工 1')
    expect(wrapper.text()).toContain('分镜缺少角色参考图')
  })
})
