import { describe, it, expect, vi, beforeEach, beforeAll, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  updateScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  deleteScene: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  aiRewriteScene: vi.fn(() => Promise.resolve({ data: { ok: true, candidate: { mood: 'mysterious', ignored_field: '不要保存' } } })),
  generateSceneReferences: vi.fn(() => Promise.resolve({ data: { ok: true, generated: { reference_wideshot_url: 'https://cdn.test/wide.png' } } })),
}))

vi.mock('../api/scenes.js', () => ({
  listScenes: vi.fn(() => Promise.resolve({ data: { ok: true, scenes: [{
    id: 'scene-1',
    name: '办公室',
    scene_type: 'indoor',
    location_desc: '玻璃办公室',
    lighting: 'day',
    mood: 'tense',
    reference_wideshot_url: '',
    reference_midshot_url: '',
    reference_aerial_url: '',
    meta_json: {
      reference_generation: {
        reference_midshot_url: {
          status: 'failed',
          source: 'style_lock',
          error: 'provider timeout',
        },
      },
    },
  }] } })),
  createScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoGenerateScenes: vi.fn(),
  updateScene: mocks.updateScene,
  deleteScene: mocks.deleteScene,
  aiRewriteScene: mocks.aiRewriteScene,
  generateSceneReferences: mocks.generateSceneReferences,
}))

vi.mock('../api/referenceData.js', () => ({
  listItems: vi.fn((type) => {
    const items = {
      scene_type: [{ value: 'indoor', label: '室内' }],
      scene_lighting: [{ value: 'day', label: '日间' }],
      scene_mood: [{ value: 'tense', label: '紧张' }],
      series_genre: [{ value: 'drama', label: '剧情' }],
    }
    return Promise.resolve({ data: { ok: true, items: items[type] || [] } })
  }),
}))

function installResizeObserver() {
  if (!global.ResizeObserver) {
    global.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
}

describe('ScenesPage management', () => {
  beforeAll(() => {
    installResizeObserver()
  })

  beforeEach(() => {
    mocks.updateScene.mockClear()
    mocks.deleteScene.mockClear()
    mocks.aiRewriteScene.mockClear()
    mocks.generateSceneReferences.mockClear()
    mocks.updateScene.mockResolvedValue({ data: { ok: true } })
    mocks.deleteScene.mockResolvedValue({ data: { ok: true, action: 'archived' } })
    mocks.aiRewriteScene.mockResolvedValue({ data: { ok: true, candidate: { mood: 'mysterious', ignored_field: '不要保存' } } })
    mocks.generateSceneReferences.mockResolvedValue({ data: { ok: true, generated: { reference_wideshot_url: 'https://cdn.test/wide.png' } } })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('opens detail drawer and saves edits', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    expect(document.body.textContent).toContain('场景详情')

    const nameInput = document.querySelector('[data-test="scene-name-input"]')
    nameInput.value = '办公室新版'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    document.querySelector('[data-test="save-scene"]').click()
    await flushPromises()

    expect(mocks.updateScene).toHaveBeenCalledWith('scene-1', expect.objectContaining({ name: '办公室新版' }))
    wrapper.unmount()
  })

  it('regenerates one scene reference slot', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    document.querySelector('[data-test="regenerate-reference_wideshot_url"]').click()
    await flushPromises()

    expect(mocks.generateSceneReferences).toHaveBeenCalledWith('scene-1', { slot: 'reference_wideshot_url' })
    wrapper.unmount()
  })

  it('shows style lock reference progress in the scene drawer', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    expect(document.querySelector('[data-test="progress-reference_midshot_url"]').textContent).toContain('生成失败')
    expect(document.body.textContent).toContain('provider timeout')
    wrapper.unmount()
  })

  it('applies partial AI rewrite candidate over the current draft and ignores unsupported fields', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    document.querySelector('[data-test="request-scene-rewrite"]').click()
    await flushPromises()
    wrapper.findComponent({ name: 'AiRewriteConfirmDialog' }).vm.$emit('confirm', {
      mood: 'mysterious',
      ignored_field: '不要保存',
    })
    await flushPromises()

    expect(mocks.updateScene).toHaveBeenCalledWith('scene-1', {
      name: '办公室',
      scene_type: 'indoor',
      location_desc: '玻璃办公室',
      lighting: 'day',
      mood: 'mysterious',
    })
    wrapper.unmount()
  })

  it('shows drawer-level errors for failed save and failed reference generation', async () => {
    mocks.updateScene.mockRejectedValueOnce(new Error('保存接口失败'))
    mocks.generateSceneReferences.mockRejectedValueOnce(new Error('参考图接口失败'))
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    document.querySelector('[data-test="save-scene"]').click()
    await flushPromises()
    expect(document.querySelector('[data-test="scene-drawer-error"]').textContent).toContain('保存接口失败')

    document.querySelector('[data-test="regenerate-reference_wideshot_url"]').click()
    await flushPromises()
    expect(document.querySelector('[data-test="scene-drawer-error"]').textContent).toContain('参考图接口失败')
    wrapper.unmount()
  })

  it('closes the drawer after successful delete or archive', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    document.querySelector('[data-test="delete-scene"]').click()
    await flushPromises()
    wrapper.findComponent({ name: 'DangerConfirmDialog' }).vm.$emit('confirm')
    await flushPromises()

    expect(mocks.deleteScene).toHaveBeenCalledWith('scene-1')
    expect(document.querySelector('[data-test="scene-name-input"]')).toBeNull()
    wrapper.unmount()
  })
})
