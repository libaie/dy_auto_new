import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  uploadImageSource: vi.fn(),
  createImageTask: vi.fn(),
  getImageTask: vi.fn(),
  listImageAssets: vi.fn(),
  listModels: vi.fn(),
  syncImageTask: vi.fn(),
  dispatchQueuedImageTask: vi.fn(),
  reviewImageAsset: vi.fn(),
  editImageAsset: vi.fn(),
  listImageProductionStrategies: vi.fn(),
  previewImageSelection: vi.fn(),
  promoteImageAssetToVideo: vi.fn(),
  previewImageAbTest: vi.fn(),
  createImageAbTest: vi.fn(),
  getImageAbTest: vi.fn(),
  refreshImageAbTest: vi.fn(),
  getImageAbWinnerRecommendation: vi.fn(),
  chooseImageAbWinner: vi.fn(),
  chooseImageAbNoWinner: vi.fn(),
}))

vi.mock('../api/imageCreation.js', () => ({
  uploadImageSource: mocks.uploadImageSource,
  createImageTask: mocks.createImageTask,
  getImageTask: mocks.getImageTask,
  listImageAssets: mocks.listImageAssets,
  syncImageTask: mocks.syncImageTask,
  dispatchQueuedImageTask: mocks.dispatchQueuedImageTask,
  reviewImageAsset: mocks.reviewImageAsset,
  editImageAsset: mocks.editImageAsset,
}))

vi.mock('../api/aiConfig.js', () => ({
  listModels: mocks.listModels,
}))

vi.mock('../api/imageProduction.js', () => ({
  listImageProductionStrategies: mocks.listImageProductionStrategies,
  previewImageSelection: mocks.previewImageSelection,
  promoteImageAssetToVideo: mocks.promoteImageAssetToVideo,
  previewImageAbTest: mocks.previewImageAbTest,
  createImageAbTest: mocks.createImageAbTest,
  getImageAbTest: mocks.getImageAbTest,
  refreshImageAbTest: mocks.refreshImageAbTest,
  getImageAbWinnerRecommendation: mocks.getImageAbWinnerRecommendation,
  chooseImageAbWinner: mocks.chooseImageAbWinner,
  chooseImageAbNoWinner: mocks.chooseImageAbNoWinner,
}))

async function mountPage() {
  const Page = (await import('../views/ImageCreationPage.vue')).default
  const wrapper = mount(Page)
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

const mountedWrappers = []

describe('ImageCreationPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.uploadImageSource.mockResolvedValue({ data: { url: 'https://img.example/uploaded.png' } })
    mocks.createImageTask.mockResolvedValue({
      data: {
        task: { id: 'task-1', status: 'queued' },
        assets: [{
          id: 'asset-1',
          image_url: 'https://img.example/a.png',
          status: 'review_pending',
          version: 1,
          allowed_actions: ['approve', 'reject', 'repaint'],
          review_gate: { status: 'manual_review_pending' },
        }],
      },
    })
    mocks.getImageTask.mockResolvedValue({ data: { task: { id: 'task-1', status: 'queued' }, assets: [] } })
    mocks.listModels.mockResolvedValue({
      data: {
        ok: true,
        models: [{
          id: 'model-seedream',
          name: 'Seedream 5.0 Lite',
          model_type: 'image',
          provider: 'seedance',
          model_name: 'doubao-seedream-5.0-lite',
          enabled: true,
          config_json: {
            provider_options_schema: {
              sequential_image_generation: { type: 'select', options: ['disabled', 'auto'] },
              max_images: { type: 'number', min: 1, max: 15 },
              trace_id: { type: 'text' },
              stream: { type: 'boolean' },
              optimize_prompt_mode: { type: 'select', options: ['standard', 'fast'] },
              web_search: { type: 'boolean' },
            },
          },
        }],
      },
    })
    mocks.listImageAssets.mockResolvedValue({
      data: {
        assets: [{ id: 'approved-1', url: 'https://img.example/approved.png', status: 'approved', prompt: '已批准角色图' }],
      },
    })
    mocks.syncImageTask.mockResolvedValue({
      data: {
        task: { id: 'task-1', status: 'completed' },
        assets: [{
          id: 'asset-1',
          image_url: 'https://img.example/a.png',
          status: 'review_pending',
          version: 1,
          allowed_actions: ['approve', 'reject', 'repaint'],
          review_gate: { status: 'manual_review_pending' },
        }],
      },
    })
    mocks.reviewImageAsset.mockResolvedValue({
      data: { asset: { id: 'asset-1', image_url: 'https://img.example/a.png', status: 'approved' } },
    })
    mocks.editImageAsset.mockResolvedValue({
      data: { task: { id: 'task-edit-1', status: 'queued' } },
    })
    mocks.dispatchQueuedImageTask.mockResolvedValue({
      data: { task: { id: 'queued-task', status: 'running', pixelle_task_id: 'pixelle-1' }, assets: [] },
    })
    mocks.promoteImageAssetToVideo.mockResolvedValue({ data: { ok: true } })
    mocks.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [{
          id: 'strategy-1',
          name: '默认分镜首帧',
          destination_role: 'storyboard_frame',
          supported_modes: ['text_to_image'],
          version: 2,
          status: 'active',
        }],
      },
    })
    mocks.previewImageSelection.mockResolvedValue({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
        cost_estimate: { amount: 1, currency: 'CNY' },
        selection_preview_id: 'preview-1',
        request_hash: 'hash-1',
      },
    })
    mocks.getImageAbWinnerRecommendation.mockResolvedValue({
      data: {
        ok: true,
        recommendation: {
          recommended_attempt_id: 'attempt-approved',
          reason: 'approved asset ready',
        },
      },
    })
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount()
    }
    vi.useRealTimers()
  })

  it('renders Chinese mode controls and disables submit without prompt', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('图像创作')
    expect(wrapper.text()).toContain('文生图')
    expect(wrapper.text()).toContain('以图改图')
    expect(wrapper.text()).toContain('多图参考')
    expect(wrapper.text()).toContain('文生组图')
    expect(wrapper.text()).toContain('一图组图')
    expect(wrapper.text()).toContain('多参考组图')
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
    expect(mocks.listModels).toHaveBeenCalledWith({ model_type: 'image', enabled: true })
    expect(mocks.listImageAssets).toHaveBeenCalledWith({ status: 'approved', page_size: 30 })
    expect(mocks.listImageProductionStrategies).toHaveBeenCalledWith({ status: 'active' })
  })

  it('previews the selected image strategy and submits preview snapshot fields', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="destination-role"]').setValue('storyboard_frame')
    await wrapper.get('[data-testid="image-prompt"]').setValue('生成统一风格的分镜首帧')
    await wrapper.get('[data-testid="strategy-select"]').setValue('strategy-1')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()

    expect(mocks.previewImageSelection).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'text_to_image',
      destination_role: 'storyboard_frame',
      strategy_id: 'strategy-1',
      strategy_version: 2,
      model_id: null,
      count: 1,
      provider_options: {},
      output_format: null,
    }))
    expect(wrapper.get('[data-testid="image-trust-rail"]').text()).toContain('Seedream 5.0 Lite')

    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      strategy_id: 'strategy-1',
      strategy_version: 2,
      selection_preview_id: 'preview-1',
      selection_preview_request_hash: 'hash-1',
    }))
  })

  it('requires explicit high-cost confirmation before submit', async () => {
    mocks.previewImageSelection.mockResolvedValueOnce({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
        cost_estimate: { amount: 4, currency: 'CNY', requires_confirmation: true, confirmation_threshold: 3 },
        time_estimate: { estimated_seconds: 20 },
        capacity: { status: 'available', queue_depth: 0, estimated_wait_seconds: 0 },
        review_gate: { manual_required: true, status: 'manual_review_pending' },
        selection_preview_id: 'preview-high-cost',
        request_hash: 'hash-high-cost',
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()

    const rail = wrapper.get('[data-testid="image-trust-rail"]')
    expect(rail.text()).toContain('提交前检查')
    expect(rail.text()).toContain('生产路径')
    expect(rail.text()).toContain('审查门禁')
    expect(rail.text()).toContain('4 CNY')
    expect(rail.text()).toContain('预计 20 秒')
    expect(rail.text()).toContain('需要人工确认成本')
    expect(wrapper.get('[data-testid="image-submit-confirmation"]').text()).toContain('当前预计成本较高')
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    expect(mocks.createImageTask).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="confirm-image-cost"]').trigger('click')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      cost_confirmation: true,
    }))
  })

  it('omits stale image inputs after switching back to text generation', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-image_to_image"]').trigger('click')
    await wrapper.get('[data-testid="source-url"]').setValue('https://img.example/stale-source.png')
    await wrapper.get('[data-testid="mode-multi_reference_to_image"]').trigger('click')
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/stale-a.png\nhttps://img.example/stale-b.png')
    await wrapper.get('[data-testid="mode-text_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('Plain text image after mode switch')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const payload = mocks.createImageTask.mock.calls[0][0]
    expect(payload).toEqual(expect.objectContaining({
      mode: 'text_to_image',
      prompt: 'Plain text image after mode switch',
    }))
    expect(payload).not.toHaveProperty('source')
    expect(payload).not.toHaveProperty('reference_images')
  })

  it('omits stale image inputs from A/B preview after switching back to text generation', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-text-only-hash',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-image_to_image"]').trigger('click')
    await wrapper.get('[data-testid="source-url"]').setValue('https://img.example/stale-source.png')
    await wrapper.get('[data-testid="mode-multi_reference_to_image"]').trigger('click')
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/stale-a.png\nhttps://img.example/stale-b.png')
    await wrapper.get('[data-testid="mode-text_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('A/B text image after mode switch')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()

    const payload = mocks.previewImageAbTest.mock.calls[0][0]
    expect(payload).toEqual(expect.objectContaining({
      mode: 'text_to_image',
      prompt: 'A/B text image after mode switch',
      strategy_ids: ['strategy-a', 'strategy-b'],
    }))
    expect(payload).not.toHaveProperty('source')
    expect(payload).not.toHaveProperty('reference_images')
  })

  it('previews and creates A/B image comparison with explicit cost confirmation', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-1',
        strategy_count: 2,
        total_cost_estimate: { amount: 3, currency: 'CNY', requires_confirmation: true, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-1', status: 'running', attempts: [] } },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('A/B frame prompt')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="ab-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ab-strategy-selector"]').exists()).toBe(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('3 CNY')
    expect(wrapper.get('[data-testid="ab-create-button"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="ab-cost-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()

    const previewPayload = mocks.previewImageAbTest.mock.calls[0][0]
    expect(previewPayload).toEqual(expect.objectContaining({
      prompt: 'A/B frame prompt',
      strategy_ids: ['strategy-a', 'strategy-b'],
    }))
    expect(previewPayload).not.toHaveProperty('strategy_id')
    expect(mocks.createImageAbTest).toHaveBeenCalledWith(expect.objectContaining({
      preview_request_hash: 'ab-hash-1',
      cost_confirmation: true,
      strategy_ids: ['strategy-a', 'strategy-b'],
    }))
    expect(wrapper.get('[data-testid="ab-create-button"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageAbTest).toHaveBeenCalledTimes(1)
  })

  it('reuses the same A/B create idempotency key when retrying the same preview after failure', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-retry-hash',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({
        data: { ok: true, ab_group: { id: 'ab-group-retry', status: 'running', attempts: [] } },
      })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Retry A/B frame prompt')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageAbTest).toHaveBeenCalledTimes(2)
    expect(mocks.createImageAbTest.mock.calls[1][0].idempotency_key).toBe(
      mocks.createImageAbTest.mock.calls[0][0].idempotency_key,
    )
  })

  it('blocks A/B create when preview exceeds configured cost cap', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-expensive',
        strategy_count: 2,
        total_cost_estimate: {
          amount: 9,
          currency: 'CNY',
          requires_confirmation: true,
          ab_max_group_cost: 5,
          cost_limit_exceeded: true,
        },
        previews: [],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Expensive A/B frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已超出A/B成本上限')
    expect(wrapper.get('[data-testid="ab-create-button"]').attributes('disabled')).toBeDefined()
    expect(mocks.createImageAbTest).not.toHaveBeenCalled()
  })

  it('refreshes A/B comparison and only enables winner action for approved attempts', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-2',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-2', status: 'running', attempts: [] } },
    })
    mocks.refreshImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-group-2',
          status: 'completed',
          attempts: [
            { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
            { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
          ],
        },
      },
    })
    mocks.chooseImageAbWinner.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-2', status: 'winner_selected', winner_attempt_id: 'attempt-approved', attempts: [] } },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Winner A/B frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="ab-no-winner-button"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ab-attempt-list"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ab-attempt-attempt-approved"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ab-attempt-attempt-pending"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-pending"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-pending"]').attributes('aria-label')).toContain('需先通过审查')

    await wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').trigger('click')
    await flushPromises()

    expect(mocks.refreshImageAbTest).toHaveBeenCalledWith('ab-group-2')
    expect(mocks.chooseImageAbWinner).toHaveBeenCalledWith('ab-group-2', 'attempt-approved', expect.objectContaining({
      reason: 'manual_selection',
    }))
  })

  it('ignores stale A/B refresh responses after A/B state resets', async () => {
    let resolveRefresh
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-stale-refresh',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-stale-refresh', status: 'running', attempts: [] } },
    })
    mocks.refreshImageAbTest.mockReturnValueOnce(new Promise(resolve => {
      resolveRefresh = resolve
    }))
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Stale refresh frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('ab-group-stale-refresh')

    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('Different prompt resets A/B state')
    await flushPromises()

    resolveRefresh({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-group-stale-refresh',
          status: 'completed',
          attempts: [
            { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
          ],
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('ab-group-stale-refresh')
    expect(wrapper.find('[data-testid="ab-attempt-list"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="ab-choose-winner-attempt-approved"]').exists()).toBe(false)
  })

  it('shows A/B winner recommendation without replacing manual winner selection', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-recommendation',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-recommendation', status: 'running', attempts: [] } },
    })
    mocks.refreshImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-group-recommendation',
          status: 'completed',
          attempts: [
            { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
            { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
          ],
        },
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Recommended A/B frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-load-recommendation"]').trigger('click')
    await flushPromises()

    expect(mocks.getImageAbWinnerRecommendation).toHaveBeenCalledWith('ab-group-recommendation')
    expect(wrapper.get('[data-testid="ab-winner-recommendation"]').attributes('role')).toBe('status')
    expect(wrapper.get('[data-testid="ab-winner-recommendation"]').attributes('aria-live')).toBe('polite')
    expect(wrapper.get('[data-testid="ab-winner-recommendation"]').text()).toContain('attempt-approved')
    expect(wrapper.get('[data-testid="ab-winner-recommendation"]').text()).toContain('approved asset ready')
    expect(wrapper.get('[data-testid="ab-winner-recommendation"]').text()).toContain('仍需人工确认')
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').attributes('disabled')).toBeUndefined()
  })

  it('ignores stale A/B winner recommendation responses after the group changes', async () => {
    let resolveRecommendation
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-stale-recommendation',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-old', status: 'completed', attempts: [] } },
    })
    mocks.getImageAbWinnerRecommendation.mockReturnValueOnce(new Promise(resolve => {
      resolveRecommendation = resolve
    }))
    mocks.refreshImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-new', status: 'completed', attempts: [] } },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Stale recommendation frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-load-recommendation"]').trigger('click')
    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    await flushPromises()

    resolveRecommendation({
      data: {
        ok: true,
        recommendation: {
          recommended_attempt_id: 'attempt-from-old-group',
          reason: 'late response',
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('ab-group-new')
    expect(wrapper.find('[data-testid="ab-winner-recommendation"]').exists()).toBe(false)
  })

  it('clears stale A/B winner recommendation as soon as refresh starts', async () => {
    let rejectRefresh
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-clear-recommendation',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-clear', status: 'completed', attempts: [] } },
    })
    mocks.refreshImageAbTest.mockReturnValueOnce(new Promise((resolve, reject) => {
      rejectRefresh = reject
    }))
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('Clear stale recommendation frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-load-recommendation"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ab-winner-recommendation"]').exists()).toBe(true)

    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    expect(wrapper.find('[data-testid="ab-winner-recommendation"]').exists()).toBe(false)

    rejectRefresh(new Error('refresh failed'))
    await flushPromises()
    expect(wrapper.find('[data-testid="ab-winner-recommendation"]').exists()).toBe(false)
  })

  it('marks an A/B comparison as no winner and disables terminal outcome actions', async () => {
    mocks.listImageProductionStrategies.mockResolvedValueOnce({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-hash-no-winner',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: { ok: true, ab_group: { id: 'ab-group-no-winner', status: 'running', attempts: [] } },
    })
    mocks.refreshImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-group-no-winner',
          status: 'completed',
          attempts: [
            { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
            { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
          ],
        },
      },
    })
    mocks.chooseImageAbNoWinner.mockResolvedValueOnce({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-group-no-winner',
          status: 'no_winner',
          attempts: [
            { id: 'attempt-approved', status: 'completed', approved_asset_ready: true, approved_asset_ids: ['asset-1'] },
            { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
          ],
        },
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('No winner A/B frame')
    await wrapper.get('[data-testid="ab-mode-toggle"]').trigger('click')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-refresh-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="ab-no-winner-button"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="ab-no-winner-button"]').trigger('click')
    await flushPromises()

    expect(mocks.chooseImageAbNoWinner).toHaveBeenCalledWith('ab-group-no-winner', {
      reason: 'manual_no_winner',
    })
    expect(wrapper.get('[data-testid="ab-no-winner-button"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="ab-choose-winner-attempt-approved"]').trigger('click')
    await flushPromises()
    expect(mocks.chooseImageAbWinner).not.toHaveBeenCalled()
  })

  it('shows queued capacity state from selection preview in the trust rail', async () => {
    mocks.previewImageSelection.mockResolvedValueOnce({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
        cost_estimate: { amount: 1, currency: 'CNY', requires_confirmation: false },
        time_estimate: { estimated_seconds: 10 },
        capacity: {
          status: 'queued',
          queue_depth: 3,
          estimated_wait_seconds: 90,
          admission_action: 'queue',
        },
        review_gate: { manual_required: false, status: 'not_required' },
        selection_preview_id: 'preview-queue',
        request_hash: 'hash-queue',
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('排队图像')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()

    const rail = wrapper.get('[data-testid="image-trust-rail"]')
    expect(rail.text()).toContain('将进入队列')
    expect(rail.text()).toContain('前方 3 个任务')
    expect(rail.text()).toContain('预计等待 90 秒')
  })

  it('changing prompt after high-cost confirmation resets submit disabled', async () => {
    mocks.previewImageSelection.mockResolvedValueOnce({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
        cost_estimate: { amount: 4, currency: 'CNY', requires_confirmation: true, confirmation_threshold: 3 },
        time_estimate: { estimated_seconds: 20 },
        capacity: { status: 'available' },
        review_gate: { manual_required: true, status: 'manual_review_pending' },
        selection_preview_id: 'preview-high-cost',
        request_hash: 'hash-high-cost',
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="confirm-image-cost"]').trigger('click')
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeUndefined()

    await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像已修改')
    await flushPromises()

    expect(wrapper.find('[data-testid="confirm-image-cost"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).not.toHaveBeenCalled()
  })

  it('does not reuse stale high-cost confirmation after request changes', async () => {
    mocks.previewImageSelection.mockResolvedValueOnce({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
        cost_estimate: { amount: 4, currency: 'CNY', requires_confirmation: true, confirmation_threshold: 3 },
        time_estimate: { estimated_seconds: 20 },
        capacity: { status: 'available' },
        review_gate: { manual_required: true, status: 'manual_review_pending' },
        selection_preview_id: 'preview-high-cost',
        request_hash: 'hash-high-cost',
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="confirm-image-cost"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('高成本图像已修改')
    await flushPromises()

    expect(wrapper.find('[data-testid="confirm-image-cost"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).not.toHaveBeenCalledWith(expect.objectContaining({
      cost_confirmation: true,
    }))
  })

  it('shows rejected candidates, blocks submit, and confirms a fallback model', async () => {
    mocks.listModels.mockResolvedValueOnce({
      data: {
        ok: true,
        models: [
          {
            id: 'model-primary',
            name: 'Primary Image Model',
            model_type: 'image',
            provider: 'primary-provider',
            model_name: 'primary-image',
            enabled: true,
            config_json: { provider_options_schema: {} },
          },
          {
            id: 'model-fallback',
            name: 'Fallback Image Model',
            model_type: 'image',
            provider: 'fallback-provider',
            model_name: 'fallback-image',
            enabled: true,
            config_json: { provider_options_schema: {} },
          },
        ],
      },
    })
    mocks.previewImageSelection
      .mockResolvedValueOnce({
        data: {
          ok: false,
          preview_blocked: true,
          confirmation_required: true,
          error_code: 'IMAGE_FALLBACK_REQUIRES_CONFIRMATION',
          selected_model: null,
          selection_explanation: {
            selected_reason: '',
            rejected_candidates: [{
              model_id: 'model-primary',
              name: 'Primary Image Model',
              reason: 'quota_exhausted',
              detail: 'primary quota is exhausted',
              rescue_action: 'confirm fallback model',
            }],
          },
          fallback_candidates: [{
            model_id: 'model-fallback',
            name: 'Fallback Image Model',
            reason: 'compatible fallback',
          }],
          rescue_actions: [{
            type: 'confirm_fallback_model',
            model_id: 'model-fallback',
            label: 'Confirm fallback model',
          }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          selected_model: { model_id: 'model-fallback', name: 'Fallback Image Model' },
          selection_explanation: { selected_reason: 'requested fallback model', rejected_candidates: [] },
          cost_estimate: { amount: 2, currency: 'CNY' },
          selection_preview_id: 'preview-fallback',
          request_hash: 'hash-fallback',
        },
      })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成统一风格分镜首帧')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()

    const trustRail = wrapper.get('[data-testid="image-trust-rail"]')
    expect(trustRail.text()).toContain('需确认 fallback')
    expect(trustRail.text()).toContain('自动策略')
    expect(trustRail.text()).toContain('Fallback Image Model')
    expect(trustRail.text()).toContain('使用 fallback 模型')
    expect(trustRail.text()).not.toContain('Confirm fallback model')
    const diagnostics = trustRail.findAll('details')[0]
    expect(diagnostics.text()).toContain('Primary Image Model')
    expect(diagnostics.text()).toContain('当前模型不可用')
    expect(diagnostics.text()).toContain('该模型当前无法满足请求')
    expect(diagnostics.text()).not.toContain('quota_exhausted')
    expect(diagnostics.text()).not.toContain('primary quota is exhausted')
    expect(diagnostics.text()).not.toContain('confirm fallback model')
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="image-create-disabled-reason"]').text()).toBe('当前预览需要先确认 fallback 模型后才能创建任务。')

    await wrapper.get('[data-testid="confirm-fallback-model-model-fallback"]').trigger('click')
    await flushPromises()

    expect(mocks.previewImageSelection.mock.calls.at(-1)[0]).toEqual(expect.objectContaining({
      model_id: 'model-fallback',
    }))
    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeUndefined()
  })

  it('renders the production timeline returned by the task payload', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: {
          id: 'task-1',
          status: 'queued',
          timeline: [
            { key: 'preview', label: 'Selection preview', status: 'completed' },
            { key: 'snapshot', label: 'Task snapshot', status: 'completed' },
            { key: 'queue', label: 'Queue', status: 'queued' },
            { key: 'generation', label: 'Generation', status: 'mystery' },
            { key: 'approval', label: 'Approval gate', status: 'completed' },
          ],
        },
        assets: [],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成统一风格分镜首帧')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const timeline = wrapper.get('[data-testid="image-production-timeline"]')
    expect(wrapper.text()).toContain('排队中')
    expect(wrapper.text()).not.toContain('queued')
    expect(timeline.text()).toContain('选择预览')
    expect(timeline.text()).toContain('任务快照')
    expect(timeline.text()).toContain('进入队列')
    expect(timeline.text()).toContain('图像生成')
    expect(timeline.text()).toContain('人工确认')
    expect(timeline.text()).toContain('排队中')
    expect(wrapper.get('[data-testid="image-production-timeline-step-generation"]').text()).toContain('未知')
    expect(wrapper.get('[data-testid="image-production-timeline-step-generation"]').text()).not.toContain('待处理')
    expect(timeline.text()).not.toContain('Selection preview')
    expect(timeline.text()).not.toContain('Approval gate')
    expect(wrapper.get('[data-testid="image-production-timeline-step-queue"]').attributes('aria-current')).toBe('step')
  })

  it('surfaces failed task fallback rescue actions without raw backend labels', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: {
          id: 'task-failed',
          status: 'failed',
          timeline: [
            { key: 'generation', label: 'Generation', status: 'failed' },
          ],
          fallback_trace: {
            message: 'provider unavailable',
            rescue_actions: [{
              type: 'retry_with_fallback_model',
              model_id: 'model-fallback',
              label: 'Retry with fallback model',
            }],
          },
        },
        assets: [],
      },
    })
    mocks.previewImageSelection.mockResolvedValueOnce({
      data: {
        selected_model: { model_id: 'model-fallback', name: 'Fallback Image Model' },
        selection_explanation: { selected_reason: 'manual fallback', rejected_candidates: [] },
        cost_estimate: { amount: 1, currency: 'CNY' },
        selection_preview_id: 'retry-preview',
        request_hash: 'retry-hash',
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('失败后使用 fallback 重试')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const rescuePanel = wrapper.get('[data-testid="image-task-rescue-actions"]')
    expect(rescuePanel.text()).toContain('可执行修复')
    expect(rescuePanel.text()).toContain('使用 fallback 模型重试')
    expect(rescuePanel.text()).not.toContain('Retry with fallback model')

    await wrapper.get('[data-testid="retry-fallback-model-model-fallback"]').trigger('click')
    await flushPromises()

    expect(mocks.previewImageSelection).toHaveBeenCalledWith(expect.objectContaining({
      model_id: 'model-fallback',
    }))
  })

  it('loads the persisted failed task when create submission fails after snapshot', async () => {
    mocks.createImageTask.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            message: 'Pixelle image submission failed after the task snapshot was saved.',
            affected_ids: ['task-failed'],
          },
        },
      },
    })
    mocks.getImageTask.mockResolvedValueOnce({
      data: {
        task: {
          id: 'task-failed',
          status: 'failed',
          timeline: [
            { key: 'generation', label: 'Generation', status: 'failed' },
          ],
          fallback_trace: {
            message: 'provider unavailable',
            rescue_actions: [{
              type: 'retry_with_fallback_model',
              model_id: 'model-fallback',
              label: 'Retry with fallback model',
            }],
          },
        },
        assets: [],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('提交失败后展示失败任务')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.getImageTask).toHaveBeenCalledWith('task-failed')
    expect(wrapper.text()).toContain('Pixelle image submission failed after the task snapshot was saved.')
    expect(wrapper.get('[data-testid="task-results-live"]').text()).toContain('task-failed')
    expect(wrapper.get('[data-testid="image-task-rescue-actions"]').text()).toContain('使用 fallback 模型重试')
  })

  it('keeps watermark in the selection preview provider options before submitting', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成带水印的统一风格分镜首帧')
    await wrapper.get('[data-testid="strategy-select"]').setValue('strategy-1')
    await wrapper.get('[data-testid="image-watermark"]').setValue(true)
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.previewImageSelection).toHaveBeenCalledWith(expect.objectContaining({
      provider_options: { watermark: true },
    }))
    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      watermark: true,
      selection_preview_id: 'preview-1',
      selection_preview_request_hash: 'hash-1',
    }))
  })

  it('clears an existing selection preview when watermark changes', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成统一风格分镜首帧')
    await wrapper.get('[data-testid="strategy-select"]').setValue('strategy-1')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="image-watermark"]').setValue(true)
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const payload = mocks.createImageTask.mock.calls[0][0]
    expect(payload).toEqual(expect.objectContaining({ watermark: true }))
    expect(payload).not.toHaveProperty('selection_preview_id')
    expect(payload).not.toHaveProperty('selection_preview_request_hash')
  })

  it('ignores a stale selection preview response after the form changes', async () => {
    let resolvePreview
    mocks.previewImageSelection.mockImplementationOnce(() => new Promise(resolve => {
      resolvePreview = resolve
    }))
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成统一风格分镜首帧')
    await wrapper.get('[data-testid="selection-preview-button"]').trigger('click')
    await wrapper.get('[data-testid="image-watermark"]').setValue(true)

    resolvePreview({
      data: {
        selected_model: { model_id: 'model-seedream', name: 'Seedream 5.0 Lite' },
        selection_explanation: { selected_reason: 'stale preview', rejected_candidates: [] },
        selection_preview_id: 'stale-preview',
        request_hash: 'stale-hash',
      },
    })
    await flushPromises()
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const payload = mocks.createImageTask.mock.calls[0][0]
    expect(payload).not.toHaveProperty('selection_preview_id')
    expect(payload).not.toHaveProperty('selection_preview_request_hash')
  })

  it('submits selected model, common parameters, and dynamic provider options', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一组统一风格海报')
    await wrapper.get('[data-testid="image-model-select"]').setValue('model-seedream')
    await wrapper.get('[data-testid="image-size"]').setValue('3K')
    await wrapper.get('[data-testid="image-output-format"]').setValue('png')
    await wrapper.get('[data-testid="image-response-format"]').setValue('url')
    await wrapper.get('[data-testid="image-watermark"]').setValue(true)
    await wrapper.get('[data-testid="provider-option-sequential_image_generation"]').setValue('auto')
    await wrapper.get('[data-testid="provider-option-max_images"]').setValue(5)
    await wrapper.get('[data-testid="provider-option-trace_id"]').setValue('00123')
    await wrapper.get('[data-testid="provider-option-stream"]').setValue(true)
    await wrapper.get('[data-testid="provider-option-optimize_prompt_mode"]').setValue('fast')
    await wrapper.get('[data-testid="provider-option-web_search"]').setValue(true)
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      model_id: 'model-seedream',
      size: '3K',
      output_format: 'png',
      response_format: 'url',
      watermark: true,
      provider_options: {
        sequential_image_generation: 'auto',
        max_images: 5,
        trace_id: '00123',
        stream: true,
        optimize_prompt_mode: 'fast',
        web_search: true,
      },
    }))
  })

  it('text_to_image submit calls createImageTask with expected payload', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一张赛博朋克城市海报')
    await wrapper.get('[data-testid="destination-role"]').setValue('storyboard_frame')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'text_to_image',
      prompt: '生成一张赛博朋克城市海报',
      count: 1,
      destination_role: 'storyboard_frame',
      cost_confirmation: false,
      idempotency_key: expect.any(String),
    }))
    expect(mocks.createImageTask.mock.calls[0][0]).not.toHaveProperty('model_id')
  })

  it('uploads a source image and fills the source URL', async () => {
    const wrapper = await mountPage()
    const input = wrapper.get('[data-testid="source-file"]')
    const file = new File(['image'], 'source.png', { type: 'image/png' })

    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    await flushPromises()

    expect(mocks.uploadImageSource).toHaveBeenCalled()
    expect(wrapper.get('[data-testid="source-url"]').element.value).toBe('https://img.example/uploaded.png')
  })

  it('shows approved assets and can use one as the source image', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('已批准角色图')
    await wrapper.get('[data-testid="use-approved-asset-approved-1"]').trigger('click')

    expect(wrapper.get('[data-testid="source-url"]').element.value).toBe('https://img.example/approved.png')
  })

  it('syncs the current task and updates assets', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一张赛博朋克城市海报')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="sync-image-task"]').trigger('click')
    await flushPromises()

    expect(mocks.syncImageTask).toHaveBeenCalledWith('task-1')
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).not.toContain('completed')
    expect(wrapper.text()).toContain('review_pending')
  })

  it('automatically polls an active task and renders each completed image asset', async () => {
    vi.useFakeTimers()
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: { id: 'task-live', status: 'running', pixelle_task_id: 'pixelle-live' },
        assets: [],
      },
    })
    mocks.syncImageTask.mockResolvedValueOnce({
      data: {
        task: { id: 'task-live', status: 'running', pixelle_task_id: 'pixelle-live' },
        assets: [{
          id: 'asset-live-1',
          image_url: 'https://img.example/live-1.png',
          status: 'review_pending',
          version: 1,
          prompt: '第一张实时回显图',
          allowed_actions: ['approve'],
          review_gate: { status: 'manual_review_pending' },
        }],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('自动回显图像任务')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="task-results-live"]').text()).not.toContain('第一张实时回显图')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(mocks.syncImageTask).toHaveBeenCalledWith('task-live')
    expect(wrapper.get('[data-testid="task-results-live"]').text()).toContain('第一张实时回显图')
    expect(wrapper.find('img[src="https://img.example/live-1.png"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows queued task status and manually dispatches queued tasks', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: {
          id: 'queued-task',
          status: 'queued',
          queue_job_id: 'queue-1',
          pixelle_task_id: null,
          capacity: { status: 'queued', queue_depth: 2, estimated_wait_seconds: 60 },
        },
        assets: [],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('排队任务')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="image-queue-status"]').text()).toContain('前方 2 个任务')
    expect(wrapper.get('[data-testid="image-queue-status"]').text()).toContain('尚未提交到 Pixelle')

    await wrapper.get('[data-testid="dispatch-queued-image-task"]').trigger('click')
    await flushPromises()

    expect(mocks.dispatchQueuedImageTask).toHaveBeenCalledWith('queued-task')
    expect(wrapper.find('[data-testid="image-queue-status"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="task-results-live"]').text()).toContain('pixelle-1')
  })

  it('uses asset allowed_actions and promotes approved assets with explicit video target', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: { id: 'task-1', status: 'completed' },
        assets: [
          {
            id: 'asset-approved',
            url: 'https://img.example/a.png',
            status: 'approved',
            version: 1,
            allowed_actions: ['promote_to_video_asset', 'copy_as_new_task'],
            review_gate: { status: 'approved' },
            destination_context: { video_run_id: 'run-1', frame_id: 'frame-1', episode_id: 'episode-1' },
          },
          {
            id: 'asset-pending',
            url: 'https://img.example/b.png',
            status: 'review_pending',
            version: 1,
            allowed_actions: ['approve', 'reject', 'repaint'],
            review_gate: { status: 'manual_review_pending' },
          },
        ],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('带视频目标的资产')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="review-filter-all"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="promote-asset-asset-approved"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="copy-asset-asset-approved"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="approve-asset-asset-approved"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="promote-asset-asset-pending"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="approve-asset-asset-pending"]').exists()).toBe(true)

    await wrapper.get('[data-testid="promote-asset-asset-approved"]').trigger('click')
    await flushPromises()

    expect(mocks.promoteImageAssetToVideo).toHaveBeenCalledWith('asset-approved', {
      run_id: 'run-1',
      frame_id: 'frame-1',
      episode_id: 'episode-1',
      asset_version: 1,
    })
  })

  it('does not show promote action for approved assets without an explicit video target', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: { id: 'task-1', status: 'completed' },
        assets: [
          {
            id: 'asset-approved-no-run',
            url: 'https://img.example/a.png',
            status: 'approved',
            version: 1,
            allowed_actions: ['promote_to_video_asset', 'copy_as_new_task'],
            review_gate: { status: 'approved' },
            destination_context: { slot_key: 'frame-1' },
          },
          {
            id: 'asset-approved-no-frame',
            url: 'https://img.example/b.png',
            status: 'approved',
            version: 1,
            allowed_actions: ['promote_to_video_asset', 'copy_as_new_task'],
            review_gate: { status: 'approved' },
            destination_context: { video_run_id: 'run-1', slot_key: 'frame-1' },
          },
        ],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('无视频目标资产')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="review-filter-approved"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="promote-asset-asset-approved-no-run"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="promote-asset-asset-approved-no-frame"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="task-results-live"]').text()).toContain('审查状态：已通过')
  })

  it('shows review backlog counts and filtered empty state', async () => {
    mocks.createImageTask.mockResolvedValueOnce({
      data: {
        task: { id: 'task-1', status: 'completed' },
        assets: [{
          id: 'asset-pending',
          url: 'https://img.example/b.png',
          status: 'review_pending',
          version: 1,
          allowed_actions: ['approve', 'reject', 'repaint'],
          review_gate: { status: 'manual_review_pending' },
        }],
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('待审资产')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="review-filter-needs_review"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="review-filter-needs_review"]').text()).toContain('1')
    expect(wrapper.get('[data-testid="review-filter-approved"]').text()).toContain('0')
    expect(wrapper.get('[data-testid="review-filter-blocked"]').text()).toContain('0')
    expect(wrapper.get('[data-testid="review-filter-all"]').text()).toContain('1')

    await wrapper.get('[data-testid="review-filter-approved"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="review-filter-approved"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="image-review-empty-state"]').text()).toContain('当前没有已通过资产')
  })

  it('repaints a pending asset without silently confirming cost', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一张赛博朋克城市海报')
    await wrapper.get('[data-testid="image-model-select"]').setValue('model-seedream')
    await wrapper.get('[data-testid="image-size"]').setValue('3K')
    await wrapper.get('[data-testid="image-output-format"]').setValue('png')
    await wrapper.get('[data-testid="provider-option-max_images"]').setValue(2)
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="edit-asset-asset-1"]').trigger('click')
    await flushPromises()

    expect(mocks.editImageAsset).toHaveBeenCalledWith('asset-1', expect.objectContaining({
      prompt: '生成一张赛博朋克城市海报',
      count: 1,
      action: 'repaint',
      asset_version: 1,
      model_id: 'model-seedream',
      size: '3K',
      output_format: 'png',
      provider_options: { max_images: 2 },
      cost_confirmation: false,
      idempotency_key: expect.any(String),
    }))
    expect(wrapper.text()).toContain('task-edit-1')
  })

  it('copies an approved asset as a new image task when allowed by the backend', async () => {
    mocks.reviewImageAsset.mockResolvedValueOnce({
      data: {
        asset: {
          id: 'asset-1',
          image_url: 'https://img.example/a.png',
          status: 'approved',
          version: 1,
          allowed_actions: ['copy_as_new_task'],
          review_gate: { status: 'approved' },
        },
      },
    })
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一张赛博朋克城市海报')
    await wrapper.get('[data-testid="image-model-select"]').setValue('model-seedream')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="approve-asset-asset-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="review-filter-approved"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="copy-asset-asset-1"]').trigger('click')
    await flushPromises()

    expect(mocks.reviewImageAsset).toHaveBeenCalledWith('asset-1', { action: 'approve', asset_version: 1 })
    expect(mocks.editImageAsset).toHaveBeenCalledWith('asset-1', expect.objectContaining({
      prompt: '生成一张赛博朋克城市海报',
      count: 1,
      action: 'copy_as_new_task',
      asset_version: 1,
      model_id: 'model-seedream',
      cost_confirmation: false,
      idempotency_key: expect.any(String),
    }))
    expect(wrapper.text()).toContain('task-edit-1')
  })

  it('uses only backend-supported destination roles', async () => {
    const wrapper = await mountPage()
    const values = wrapper
      .findAll('[data-testid="destination-role"] option')
      .map(option => option.attributes('value'))

    expect(values).toEqual([
      '',
      'character_anchor',
      'scene_reference',
      'style_reference',
      'storyboard_frame',
      'image_to_video_input',
    ])
    expect(wrapper.get('[data-testid="destination-role"]').element.value).toBe('image_to_video_input')
  })

  it('blocks count greater than one for non-set modes', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一张赛博朋克城市海报')
    await wrapper.get('[data-testid="image-count"]').setValue(2)

    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('单张模式的生成数量只能为 1')
    expect(mocks.createImageTask).not.toHaveBeenCalled()
  })

  it('image_to_image submit includes source.url', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-image_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('保持构图，改成水彩风格')
    await wrapper.get('[data-testid="source-url"]').setValue('https://img.example/source.png')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'image_to_image',
      source: { url: 'https://img.example/source.png' },
    }))
  })

  it('multi_reference_to_image submits with two references and no source', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-multi_reference_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('根据参考图生成统一角色海报')
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/a.png\nhttps://img.example/b.png')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    const payload = mocks.createImageTask.mock.calls[0][0]
    expect(payload).toEqual(expect.objectContaining({
      mode: 'multi_reference_to_image',
      reference_images: [
        { url: 'https://img.example/a.png' },
        { url: 'https://img.example/b.png' },
      ],
    }))
    expect(payload).not.toHaveProperty('source')
  })

  it('keeps one reference image invalid for multi_reference_to_image', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-multi_reference_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('融合参考图，生成统一角色海报')
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/a.png')

    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('请至少填写两张参考图 URL')
    expect(mocks.createImageTask).not.toHaveBeenCalled()
  })

  it('allows group mode to submit count greater than one with two references', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-multi_reference_to_image_set"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一组统一风格角色图')
    await wrapper.get('[data-testid="image-count"]').setValue(3)
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/a.png\nhttps://img.example/b.png')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'multi_reference_to_image_set',
      count: 3,
      reference_images: [
        { url: 'https://img.example/a.png' },
        { url: 'https://img.example/b.png' },
      ],
    }))
  })

  it('allows text_to_image_set to submit multiple prompt-only outputs', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-text_to_image_set"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('生成一组统一风格海报')
    await wrapper.get('[data-testid="image-count"]').setValue(3)
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'text_to_image_set',
      count: 3,
    }))
  })

  it('can use approved assets as reference images', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-multi_reference_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('根据参考图生成统一角色海报')
    await wrapper.get('[data-testid="toggle-reference-asset-approved-1"]').trigger('click')
    await wrapper.get('[data-testid="reference-urls"]').setValue('https://img.example/b.png')
    await wrapper.get('[data-testid="image-create-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
      mode: 'multi_reference_to_image',
      reference_images: [
        { url: 'https://img.example/b.png' },
        { asset_id: 'approved-1', url: 'https://img.example/approved.png' },
      ],
    }))
  })

  it('keeps image_to_image disabled until a source image is present', async () => {
    const wrapper = await mountPage()

    await wrapper.get('[data-testid="mode-image_to_image"]').trigger('click')
    await wrapper.get('[data-testid="image-prompt"]').setValue('改成电影感')

    expect(wrapper.get('[data-testid="image-create-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('请填写源图 URL 或上传源图')
    expect(mocks.createImageTask).not.toHaveBeenCalled()
  })
})
