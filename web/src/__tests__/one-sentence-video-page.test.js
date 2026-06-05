import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

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

function oneSentenceResponse(status = 'image_batch_running') {
  return {
    data: {
      ok: true,
      route: '/video-production/run-1',
      series: { id: 'series-1', title: '短片测试' },
      episode: { id: 'episode-1', storyboard_json: { frame_count: 2, total_duration: 60 } },
      run: { id: 'run-1', status, run_type: 'real_short_e2e' },
      agency_trace_status: 'complete',
      agency_trace: {
        style_lock: {
          stage: 'style_lock',
          stage_status: 'completed',
          invocation_ids: ['style-1'],
          invocations: [{ expert_id: 'visual_storyteller', result_status: 'passed' }],
        },
        storyboard: {
          stage: 'storyboard',
          stage_status: 'completed',
          invocation_ids: ['story-1'],
          invocations: [{ expert_id: 'narrative_designer', result_status: 'passed' }],
        },
      },
      steps: [
        { key: 'prompt', label: '提示词已接收', status: 'done' },
        { key: 'series', label: '系列与剧集已创建', status: 'done' },
        { key: 'style_lock', label: '风格已锁定', status: 'done' },
        { key: 'storyboard', label: '分镜已生成', status: 'done' },
        { key: 'production_plan', label: '生产计划已关联', status: 'done' },
        { key: 'image_generation', label: '画面生成', status: 'running' },
        { key: 'image_review', label: '画面审核', status: 'pending' },
        { key: 'video_generation', label: '视频生成', status: 'waiting' },
        { key: 'video_review', label: '视频审核', status: 'waiting' },
        { key: 'compose', label: '最终合成', status: 'waiting' },
        { key: 'final_review', label: '终审', status: 'waiting' },
        { key: 'completed', label: '成片完成', status: 'waiting' },
      ],
    },
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

async function mountPage() {
  const Page = (await import('../views/OneSentenceVideoPage.vue')).default
  return mount(Page, { global: { mocks: { $router: mocks.router } } })
}

async function submitPrompt(wrapper, prompt = '雨夜里，年轻探险家发现会发光的古地图。') {
  await wrapper.find('textarea').setValue(prompt)
  await wrapper.find('[data-test="submit-one-sentence"]').trigger('click')
  await flushPromises()
  await flushPromises()
}

describe('OneSentenceVideoPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createOneSentenceVideo.mockResolvedValue(oneSentenceResponse())
    mocks.runRealWorkerStep.mockResolvedValue({ data: { ok: true, processed: 1 } })
    mocks.syncImageStage.mockResolvedValue({ data: { ok: true } })
    mocks.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_review_pending' },
      },
    })
  })

  it('renders Chinese mode copy without mojibake markers', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('真实短片')
    expect(wrapper.text()).toContain('模拟长剧调度')
    expect(wrapper.text()).toContain('一句话成片')
    expect(wrapper.text()).not.toMatch(/涓€|鍙ヨ|鐪熷疄|妯℃嫙|鎻愮ず|瀹℃牳|�/)

    wrapper.unmount()
  })

  it('defaults to real short mode and submits the real run type with 60 seconds', async () => {
    const wrapper = await mountPage()

    await submitPrompt(wrapper)

    expect(mocks.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      prompt: '雨夜里，年轻探险家发现会发光的古地图。',
      title: undefined,
      run_type: 'real_short_e2e',
      target_duration_seconds: 60,
      budget_limit: 1,
      autostart_images: true,
      auto_repair_policy: expect.objectContaining({
        enabled: true,
        requires_human_gate_after_repair: true,
      }),
    }))
    expect(mocks.runRealWorkerStep).toHaveBeenCalledWith('run-1')
    expect(mocks.syncImageStage).not.toHaveBeenCalled()
    expect(mocks.getVideoProductionRun).toHaveBeenCalledWith('run-1')
    expect(wrapper.text()).toContain('image_review_pending')

    wrapper.unmount()
  })

  it('submits mock series scale mode with a long duration', async () => {
    mocks.createOneSentenceVideo.mockResolvedValueOnce({
      data: {
        ...oneSentenceResponse('queued').data,
        run: { id: 'run-1', status: 'queued', run_type: 'mock_series_scale' },
      },
    })
    const wrapper = await mountPage()

    await wrapper.find('[data-test="mode-mock-series-scale"]').trigger('click')
    await wrapper.find('[data-test="target-duration-seconds"]').setValue(28800)
    await submitPrompt(wrapper, '模拟一部长剧生产排期。')

    expect(mocks.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      prompt: '模拟一部长剧生产排期。',
      title: undefined,
      run_type: 'mock_series_scale',
      target_duration_seconds: 28800,
      autostart_images: true,
      auto_repair_policy: expect.objectContaining({
        enabled: true,
      }),
    }))
    expect(wrapper.text()).toContain('mock_series_scale')
    expect(wrapper.text()).toContain('调度')
    expect(wrapper.text()).toContain('worker')
    await wrapper.find('[data-test="mock-scheduler-entry"]').trigger('click')
    expect(mocks.router.push).toHaveBeenCalledWith('/video-production/run-1')

    wrapper.unmount()
  })

  it('does not start real autopilot when a delayed mock submit returns after switching modes', async () => {
    const pendingCreate = deferred()
    mocks.createOneSentenceVideo.mockReturnValueOnce(pendingCreate.promise)
    const wrapper = await mountPage()

    await wrapper.find('[data-test="mode-mock-series-scale"]').trigger('click')
    await wrapper.find('[data-test="target-duration-seconds"]').setValue(28800)
    await wrapper.find('textarea').setValue('模拟一部长剧生产排期。')
    await wrapper.find('[data-test="submit-one-sentence"]').trigger('click')
    await wrapper.find('[data-test="mode-real-short"]').trigger('click')

    pendingCreate.resolve({
      data: {
        ...oneSentenceResponse('image_batch_running').data,
        run: { id: 'run-1', status: 'image_batch_running', run_type: 'mock_series_scale' },
      },
    })
    await flushPromises()
    await flushPromises()

    expect(mocks.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      run_type: 'mock_series_scale',
      target_duration_seconds: 28800,
    }))
    expect(mocks.runRealWorkerStep).not.toHaveBeenCalled()
    expect(mocks.syncImageStage).not.toHaveBeenCalled()
    expect(mocks.startVideoStage).not.toHaveBeenCalled()
    expect(mocks.syncVideoStage).not.toHaveBeenCalled()
    expect(mocks.startComposeStage).not.toHaveBeenCalled()
    expect(mocks.syncComposeStage).not.toHaveBeenCalled()
    expect(mocks.getVideoProductionRun).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('mock_series_scale')

    wrapper.unmount()
  })

  it('submits real provider durations above 90 seconds for segmented long-video production', async () => {
    const wrapper = await mountPage()

    await wrapper.find('[data-test="target-duration-seconds"]').setValue(120)
    await submitPrompt(wrapper)

    expect(mocks.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      run_type: 'real_short_e2e',
      target_duration_seconds: 120,
    }))

    wrapper.unmount()
  })

  it('clamps real short duration below 60 seconds when submitting', async () => {
    const wrapper = await mountPage()

    await wrapper.find('[data-test="target-duration-seconds"]').setValue(30)
    await submitPrompt(wrapper)

    expect(mocks.createOneSentenceVideo).toHaveBeenCalledWith(expect.objectContaining({
      run_type: 'real_short_e2e',
      target_duration_seconds: 60,
    }))

    wrapper.unmount()
  })

  it('renders expert trace decisions returned by one sentence production', async () => {
    const wrapper = await mountPage()

    await submitPrompt(wrapper)

    expect(wrapper.text()).toContain('style_lock')
    expect(wrapper.text()).toContain('storyboard')
    expect(wrapper.text()).toContain('visual_storyteller')
    expect(wrapper.text()).toContain('完成')

    wrapper.unmount()
  })

  it('renders structured repair actions from production errors', async () => {
    mocks.createOneSentenceVideo.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            message: '风格审查阻断',
            repair_action: '重新生成锁定参考图',
            repair_route: '/series/series-1',
            affected_ids: ['shot-001'],
          },
        },
      },
    })
    const wrapper = await mountPage()

    await submitPrompt(wrapper)

    expect(wrapper.text()).toContain('风格审查阻断')
    expect(wrapper.text()).toContain('重新生成锁定参考图')
    expect(wrapper.text()).toContain('/series/series-1')
    expect(wrapper.text()).toContain('shot-001')

    wrapper.unmount()
  })
})
