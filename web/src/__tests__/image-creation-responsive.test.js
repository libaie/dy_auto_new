import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  uploadImageSource: vi.fn(),
  createImageTask: vi.fn(),
  getImageTask: vi.fn(),
  listImageAssets: vi.fn(() => Promise.resolve({ data: { assets: [] } })),
  syncImageTask: vi.fn(),
  reviewImageAsset: vi.fn(),
  editImageAsset: vi.fn(),
}))

vi.mock('../api/imageCreation.js', () => mocks)

describe('ImageCreationPage responsive shell', () => {
  it('keeps mode tabs, reference board, and task panel in the same page shell', async () => {
    const Page = (await import('../views/ImageCreationPage.vue')).default
    const wrapper = mount(Page)
    await flushPromises()
    const shell = wrapper.get('[data-testid="image-workbench-shell"]')

    expect(shell.find('[data-testid="image-mode-tabs"]').exists()).toBe(true)
    expect(shell.find('[data-testid="image-reference-board"]').exists()).toBe(true)
    expect(shell.find('[data-testid="image-task-panel"]').exists()).toBe(true)
  })
})
