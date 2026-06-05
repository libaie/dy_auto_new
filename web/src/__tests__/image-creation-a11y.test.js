import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  uploadImageSource: vi.fn(),
  createImageTask: vi.fn(),
  getImageTask: vi.fn(),
  listImageAssets: vi.fn(() => Promise.resolve({ data: { assets: [] } })),
  syncImageTask: vi.fn(),
  reviewImageAsset: vi.fn(),
  editImageAsset: vi.fn(),
  listModels: vi.fn(),
  listImageProductionStrategies: vi.fn(),
  previewImageSelection: vi.fn(),
  promoteImageAssetToVideo: vi.fn(),
  previewImageAbTest: vi.fn(),
  createImageAbTest: vi.fn(),
  getImageAbTest: vi.fn(),
  refreshImageAbTest: vi.fn(),
  chooseImageAbWinner: vi.fn(),
  chooseImageAbNoWinner: vi.fn(),
}))

vi.mock('../api/imageCreation.js', () => ({
  uploadImageSource: mocks.uploadImageSource,
  createImageTask: mocks.createImageTask,
  getImageTask: mocks.getImageTask,
  listImageAssets: mocks.listImageAssets,
  syncImageTask: mocks.syncImageTask,
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
  chooseImageAbWinner: mocks.chooseImageAbWinner,
  chooseImageAbNoWinner: mocks.chooseImageAbNoWinner,
}))

describe('ImageCreationPage accessibility', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.listImageAssets.mockResolvedValue({ data: { assets: [] } })
    mocks.listModels.mockResolvedValue({ data: { ok: true, models: [] } })
    mocks.listImageProductionStrategies.mockResolvedValue({
      data: {
        strategies: [
          { id: 'strategy-a', name: 'Strategy A', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
          { id: 'strategy-b', name: 'Strategy B', destination_role: 'storyboard_frame', supported_modes: ['text_to_image'], version: 1, status: 'active' },
        ],
      },
    })
  })

  it('keeps a polite task live region and Chinese labels for primary inputs', async () => {
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()

    expect(wrapper.get('[data-testid="task-results-live"]').attributes('aria-live')).toBe('polite')
    expect(wrapper.get('label[for="image-prompt"]').text()).toContain('提示词')
    expect(wrapper.get('label[for="destination-role"]').text()).toContain('目标用途')
    expect(wrapper.get('label[for="image-count"]').text()).toContain('生成数量')
  })

  it('exposes accessible A/B controls and disabled winner reason', async () => {
    mocks.previewImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        request_hash: 'ab-a11y-hash',
        strategy_count: 2,
        total_cost_estimate: { amount: 2, currency: 'CNY', requires_confirmation: false, cost_limit_exceeded: false },
        previews: [],
      },
    })
    mocks.createImageAbTest.mockResolvedValueOnce({
      data: {
        ok: true,
        ab_group: {
          id: 'ab-a11y-group',
          status: 'completed',
          attempts: [
            { id: 'attempt-pending', status: 'completed', approved_asset_ready: false, approved_asset_ids: [] },
          ],
        },
      },
    })
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()

    const toggle = wrapper.get('[data-testid="ab-mode-toggle"]')
    expect(toggle.attributes('aria-pressed')).toBe('false')
    await toggle.trigger('click')
    expect(wrapper.get('[data-testid="ab-mode-toggle"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="ab-status-live"]').attributes('aria-live')).toBe('polite')

    await wrapper.get('[data-testid="image-prompt"]').setValue('A/B accessibility prompt')
    await wrapper.get('[data-testid="ab-strategy-option-strategy-a"]').setValue(true)
    await wrapper.get('[data-testid="ab-strategy-option-strategy-b"]').setValue(true)
    await wrapper.get('[data-testid="ab-preview-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="ab-create-button"]').trigger('click')
    await flushPromises()

    const panelClass = wrapper.get('[data-testid="ab-panel"]').attributes('class') || ''
    expect(panelClass).toContain('grid')
    expect(panelClass).toContain('gap-4')
    expect(panelClass).toContain('lg:grid-cols-[minmax(0,1fr)_240px]')

    const attemptListClass = wrapper.get('[data-testid="ab-attempt-list"]').attributes('class') || ''
    expect(attemptListClass).toContain('grid')
    expect(attemptListClass).toContain('gap-3')
    expect(attemptListClass).toContain('md:grid-cols-2')
    expect(attemptListClass).toContain('xl:grid-cols-4')

    const attemptClass = wrapper.get('[data-testid="ab-attempt-attempt-pending"]').attributes('class') || ''
    expect(attemptClass).toContain('p-3')
    expect(attemptClass).toContain('text-sm')

    const disabledWinner = wrapper.get('[data-testid="ab-choose-winner-attempt-pending"]')
    expect(disabledWinner.attributes('disabled')).toBeDefined()
    expect(disabledWinner.attributes('aria-label')).toContain('需先通过审查')
    expect(wrapper.text()).toContain('需先通过审查')
  })
})
