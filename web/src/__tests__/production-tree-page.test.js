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

function runPayload(status = 'video_review_pending') {
  return {
    data: {
      ok: true,
      run: {
        id: 'run-1',
        status,
        current_stage: 'video_review',
        storyboard_json: { frames: [{ frame_id: 'seg-a' }] },
      },
      asset_summary: { video_segment: { failed: 1 } },
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
        status: 'running',
        scenes: [{
          id: 'scene-1',
          scene_id: 'scene-a',
          status: 'running',
          shots: [{
            id: 'shot-1',
            shot_id: 'shot-a',
            status: 'running',
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

describe('VideoProductionMonitorPage production tree', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params.runId = 'run-1'
    mocks.getVideoProductionRun.mockResolvedValue(runPayload())
    mocks.getRunReadiness.mockResolvedValue({ data: { ok: true, readiness: { blocks: [] } } })
    mocks.getRunProductionTree.mockResolvedValue(treePayload())
    mocks.getSegmentDetail.mockResolvedValue({
      data: {
        ok: true,
        latest_assets: {
          video_segment: {
            id: 'asset-1',
            asset_type: 'video_segment',
            frame_id: 'seg-a',
            status: 'failed',
            url: 'https://cdn.test/seg-a.mp4',
          },
        },
        allowed_actions: ['retry'],
      },
    })
    mocks.getRunCosts.mockResolvedValue({ data: { ok: true, actual_cost: 4.2, estimate_status: 'unknown' } })
    mocks.getProviderStageTasks.mockResolvedValue({ data: { ok: true, tasks: [] } })
    mocks.getSegmentRetryImpact.mockResolvedValue({ data: { ok: true, allowed: true, estimated_extra_cost: 0 } })
  })

  it('renders tree, selected segment preview, and retry action', async () => {
    const Page = (await import('../views/VideoProductionMonitorPage.vue')).default
    const wrapper = mount(Page, {
      global: {
        mocks: {
          $router: mocks.router,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('生产运行监控')
    expect(wrapper.text()).toContain('seg-a')
    expect(wrapper.text()).toContain('重试片段')

    await wrapper.find('button[data-test="segment-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('continuous_action')
    expect(mocks.getSegmentDetail).toHaveBeenCalledWith('seg-1', { history_limit: 10 })

    await wrapper.find('button[data-test="retry-segment"]').trigger('click')
    await flushPromises()
    expect(mocks.getSegmentRetryImpact).toHaveBeenCalledWith('seg-1')

    const confirm = wrapper.findAll('button').find(btn => btn.text().includes('确认重试'))
    await confirm.trigger('click')
    await flushPromises()

    expect(mocks.retryProductionSegment).toHaveBeenCalledWith('seg-1')
    expect(mocks.getRunProductionTree).toHaveBeenCalledWith('run-1', { page: 1, page_size: 50, status: undefined })
  })
})
