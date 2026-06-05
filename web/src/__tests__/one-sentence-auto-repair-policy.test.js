import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  router: { push: vi.fn() },
  createOneSentenceVideo: vi.fn(),
  getVideoProductionRun: vi.fn(),
  runRealWorkerStep: vi.fn(),
  syncImageStage: vi.fn(),
  startVideoStage: vi.fn(),
  syncVideoStage: vi.fn(),
  startComposeStage: vi.fn(),
  syncComposeStage: vi.fn(),
}))

vi.mock('../api/videoProduction.js', () => ({
  createOneSentenceVideo: mocks.createOneSentenceVideo,
  getVideoProductionRun: mocks.getVideoProductionRun,
  runRealWorkerStep: mocks.runRealWorkerStep,
  syncImageStage: mocks.syncImageStage,
  startVideoStage: mocks.startVideoStage,
  syncVideoStage: mocks.syncVideoStage,
  startComposeStage: mocks.startComposeStage,
  syncComposeStage: mocks.syncComposeStage,
}))

describe('OneSentenceVideoPage auto repair policy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createOneSentenceVideo.mockResolvedValue({
      data: {
        ok: true,
        route: '/video-production/run-1',
        series: { id: 'series-1', title: '老李控糖' },
        episode: { id: 'episode-1', storyboard_json: { frame_count: 1, total_duration: 60 } },
        run: { id: 'run-1', status: 'image_review_pending', run_type: 'real_short_e2e' },
        steps: [],
      },
    })
    mocks.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { id: 'run-1', status: 'image_review_pending' } } })
    mocks.runRealWorkerStep.mockResolvedValue({ data: { ok: true } })
  })

  it('sends confirmed auto repair policy when starting production', async () => {
    const Page = (await import('../views/OneSentenceVideoPage.vue')).default
    const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })

    await wrapper.find('textarea').setValue('做一个老李控糖的现实题材短片。')
    await wrapper.find('[data-test="auto-repair-enabled"]').setChecked(true)
    await wrapper.find('[data-test="auto-repair-budget"]').setValue('1.5')
    await wrapper.find('[data-test="submit-one-sentence"]').trigger('click')
    await flushPromises()
    await flushPromises()

    const payload = mocks.createOneSentenceVideo.mock.calls[0][0]
    expect(payload.auto_repair_policy.enabled).toBe(true)
    expect(payload.auto_repair_policy.budget_limit).toBe(1.5)
    expect(payload.auto_repair_policy.requires_human_gate_after_repair).toBe(true)
  })
})
