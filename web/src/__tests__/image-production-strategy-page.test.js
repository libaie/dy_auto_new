import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Page from '../views/ImageProductionStrategiesPage.vue'
import * as api from '../api/imageProduction.js'
import * as aiConfigApi from '../api/aiConfig.js'

const mocks = vi.hoisted(() => ({
  listImageProductionStrategies: vi.fn(),
  archiveImageProductionStrategy: vi.fn(),
  updateImageProductionStrategy: vi.fn(),
  refreshImageProductionMetrics: vi.fn(),
  getImageProductionStrategyRecommendations: vi.fn(),
  listModels: vi.fn(),
}))

vi.mock('../api/imageProduction.js', () => ({
  listImageProductionStrategies: mocks.listImageProductionStrategies,
  archiveImageProductionStrategy: mocks.archiveImageProductionStrategy,
  updateImageProductionStrategy: mocks.updateImageProductionStrategy,
  refreshImageProductionMetrics: mocks.refreshImageProductionMetrics,
  getImageProductionStrategyRecommendations: mocks.getImageProductionStrategyRecommendations,
}))

vi.mock('../api/aiConfig.js', () => ({
  listModels: mocks.listModels,
}))

describe('ImageProductionStrategiesPage', () => {
  function editableStrategy() {
    return {
      id: 'strategy-1',
      slug: 'image-to-video-input',
      name: '默认图生视频输入图',
      description: '用于图生视频',
      destination_role: 'image_to_video_input',
      supported_modes: ['image_to_video'],
      status: 'active',
      version: 2,
      default_model_id: null,
      fallback_model_ids: ['model-fallback-old'],
      common_parameters: { size: '1024x1024' },
      provider_options: { priority: 'balanced' },
      review_policy_version_id: 'review-policy-v1',
      cost_policy_version_id: 'cost-policy-v1',
      capacity_policy_version_id: 'capacity-policy-v1',
      ab_test_policy_version_id: 'ab-test-policy-v1',
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

  beforeEach(() => {
    vi.clearAllMocks()
    api.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [{
          id: 'strategy-1',
          name: '默认图生视频输入图',
          destination_role: 'image_to_video_input',
          status: 'active',
          version: 1,
          default_model_id: null,
          fallback_model_ids: [],
        }],
      },
    })
    api.archiveImageProductionStrategy.mockResolvedValue({ data: { ok: true } })
    api.updateImageProductionStrategy.mockResolvedValue({ data: { ok: true } })
    api.refreshImageProductionMetrics.mockResolvedValue({
      data: { ok: true, refreshed: { refreshed_count: 1, keys: [] } },
    })
    api.getImageProductionStrategyRecommendations.mockResolvedValue({
      data: {
        ok: true,
        recommendation: {
          strategy_id: 'strategy-1',
          strategy_version: 1,
          quality_score: 86,
          confidence: 'high',
          status: 'recommended',
          metrics: { attempt_count: 12, low_sample: false },
          recommendations: [{ code: 'KEEP_STRATEGY', message: '绛栫暐琛ㄧ幇绋冲畾', severity: 'success' }],
          automatic_mutation_allowed: false,
        },
      },
    })
    aiConfigApi.listModels.mockResolvedValue({ data: { models: [] } })
  })

  it('renders strategy table and archive action', async () => {
    const wrapper = mount(Page)
    await flushPromises()

    expect(api.listImageProductionStrategies).toHaveBeenCalledWith({ include_metrics: true })
    expect(wrapper.text()).toContain('图像策略中心')
    expect(wrapper.text()).toContain('默认图生视频输入图')

    await wrapper.get('[data-testid="archive-strategy-strategy-1"]').trigger('click')
    await flushPromises()

    expect(api.archiveImageProductionStrategy).toHaveBeenCalledWith('strategy-1')
    expect(api.listImageProductionStrategies).toHaveBeenCalledTimes(2)
  })

  it('edits default and fallback model configuration with current strategy version', async () => {
    api.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [editableStrategy()],
      },
    })
    aiConfigApi.listModels.mockResolvedValue({
      data: {
        models: [
          { id: 'model-primary', name: 'Primary Image', provider: 'openai', model_name: 'gpt-image-1' },
          { id: 'model-fallback-new', name: 'Fallback Image', provider: 'openai', model_name: 'gpt-image-1' },
        ],
      },
    })

    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.get('[data-testid="edit-strategy-strategy-1"]').trigger('click')
    await wrapper.get('[data-testid="strategy-default-model"]').setValue('model-primary')
    await wrapper.get('[data-testid="strategy-fallback-models"]').setValue(['model-fallback-new'])
    await wrapper.get('[data-testid="save-strategy-editor"]').trigger('click')
    await flushPromises()

    expect(api.updateImageProductionStrategy).toHaveBeenCalledWith('strategy-1', expect.any(Object))
    const payload = api.updateImageProductionStrategy.mock.calls[0][1]
    expect(payload).toEqual({
      slug: 'image-to-video-input',
      name: '默认图生视频输入图',
      description: '用于图生视频',
      destination_role: 'image_to_video_input',
      supported_modes: ['image_to_video'],
      default_model_id: 'model-primary',
      fallback_model_ids: ['model-fallback-new'],
      common_parameters: { size: '1024x1024' },
      provider_options: { priority: 'balanced' },
      review_policy_version_id: 'review-policy-v1',
      cost_policy_version_id: 'cost-policy-v1',
      capacity_policy_version_id: 'capacity-policy-v1',
      ab_test_policy_version_id: 'ab-test-policy-v1',
      version: 2,
    })
    expect(payload).not.toHaveProperty('status')
  })

  it('keeps editor open and skips reload when saving model configuration fails', async () => {
    api.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [editableStrategy()],
      },
    })
    api.updateImageProductionStrategy.mockRejectedValue({
      response: {
        data: {
          detail: {
            user_message: '保存模型配置失败',
          },
        },
      },
    })

    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.get('[data-testid="edit-strategy-strategy-1"]').trigger('click')
    await wrapper.get('[data-testid="save-strategy-editor"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-editor-error"]').text()).toContain('保存模型配置失败')
    expect(wrapper.find('[data-testid="strategy-default-model"]').exists()).toBe(true)
    expect(api.listImageProductionStrategies).toHaveBeenCalledTimes(1)
  })

  it('shows strategy metrics and low sample warning', async () => {
    api.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [{
          id: 'strategy-1',
          name: '绛栫暐 A',
          destination_role: 'image_to_video_input',
          status: 'active',
          version: 1,
          default_model_id: null,
          fallback_model_ids: [],
          metrics: {
            attempt_count: 3,
            success_rate: 0.67,
            average_cost_amount: 1.2,
            currency: 'CNY',
            average_latency_seconds: 8,
            low_sample: true,
          },
        }],
      },
    })

    const wrapper = mount(Page)
    await flushPromises()

    expect(wrapper.text()).toContain('67%')
    expect(wrapper.text()).toContain('1.2 CNY')
    expect(wrapper.text()).toContain('8s')
    expect(wrapper.text()).toContain('样本不足')
  })
  it('refreshes metrics from the strategy center without changing strategy config', async () => {
    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.get('[data-testid="refresh-image-metrics"]').trigger('click')
    await flushPromises()

    expect(api.refreshImageProductionMetrics).toHaveBeenCalledWith({})
    expect(api.listImageProductionStrategies).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="image-metrics-message"]').text()).toContain('已刷新 1 组指标')
  })

  it('loads and displays recommendation for one strategy', async () => {
    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.get('[data-testid="show-strategy-recommendation-strategy-1"]').trigger('click')
    await flushPromises()

    expect(api.getImageProductionStrategyRecommendations).toHaveBeenCalledWith('strategy-1')
    const panel = wrapper.get('[data-testid="strategy-recommendation-panel"]')
    const liveRegion = panel.get('[role="status"]')
    expect(liveRegion.attributes('aria-live')).toBe('polite')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('质量评分 86')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('绛栫暐琛ㄧ幇绋冲畾')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('策略变更仍需人工确认')
  })

  it('ignores stale recommendation responses when a newer strategy was requested', async () => {
    api.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [
          {
            id: 'strategy-a',
            name: 'Strategy A',
            destination_role: 'image_to_video_input',
            status: 'active',
            version: 1,
            default_model_id: null,
            fallback_model_ids: [],
          },
          {
            id: 'strategy-b',
            name: 'Strategy B',
            destination_role: 'image_to_video_input',
            status: 'active',
            version: 1,
            default_model_id: null,
            fallback_model_ids: [],
          },
        ],
      },
    })
    const firstRequest = deferred()
    const secondRequest = deferred()
    api.getImageProductionStrategyRecommendations
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)

    const wrapper = mount(Page)
    await flushPromises()

    await wrapper.get('[data-testid="show-strategy-recommendation-strategy-a"]').trigger('click')
    await wrapper.get('[data-testid="show-strategy-recommendation-strategy-b"]').trigger('click')

    secondRequest.resolve({
      data: {
        recommendation: {
          strategy_id: 'strategy-b',
          strategy_version: 1,
          quality_score: 92,
          status: 'recommended',
          recommendations: [{ code: 'LATEST', message: 'LATEST_RECOMMENDATION' }],
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('strategy-b')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('LATEST_RECOMMENDATION')

    firstRequest.resolve({
      data: {
        recommendation: {
          strategy_id: 'strategy-a',
          strategy_version: 1,
          quality_score: 10,
          status: 'cautious',
          recommendations: [{ code: 'STALE', message: 'STALE_RECOMMENDATION' }],
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('strategy-b')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).toContain('LATEST_RECOMMENDATION')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).not.toContain('strategy-a')
    expect(wrapper.get('[data-testid="strategy-recommendation-panel"]').text()).not.toContain('STALE_RECOMMENDATION')
  })
})
