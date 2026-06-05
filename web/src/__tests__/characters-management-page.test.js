import { describe, it, expect, vi, beforeEach, beforeAll, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  updateCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  deleteCharacter: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  aiRewriteCharacter: vi.fn(() => Promise.resolve({ data: { ok: true, candidate: { personality: '坚定', ignored_field: '不要保存' } } })),
  generateCharacterReferences: vi.fn(() => Promise.resolve({ data: { ok: true, generated: { avatar_front_url: 'https://cdn.test/front.png' } } })),
}))

vi.mock('../api/characters.js', () => ({
  listCharacters: vi.fn(() => Promise.resolve({ data: { ok: true, characters: [{
    id: 'char-1',
    name: '林岚',
    role_type: 'protagonist',
    gender: 'female',
    personality: '冷静',
    appearance_desc: '短发',
    outfit_desc: '白色外套',
    avatar_front_url: '',
    avatar_side_url: '',
    avatar_threequarter_url: '',
    avatar_fullbody_url: '',
    meta_json: {
      reference_generation: {
        avatar_front_url: {
          status: 'generating',
          source: 'style_lock',
        },
      },
    },
  }] } })),
  createCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoGenerateCharacters: vi.fn(),
  updateCharacter: mocks.updateCharacter,
  deleteCharacter: mocks.deleteCharacter,
  aiRewriteCharacter: mocks.aiRewriteCharacter,
  generateCharacterReferences: mocks.generateCharacterReferences,
}))

vi.mock('../api/referenceData.js', () => ({
  listItems: vi.fn((type) => {
    const items = {
      character_role: [{ value: 'protagonist', label: '主角' }],
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

describe('CharactersPage management', () => {
  beforeAll(() => {
    installResizeObserver()
  })

  beforeEach(() => {
    mocks.updateCharacter.mockClear()
    mocks.deleteCharacter.mockClear()
    mocks.aiRewriteCharacter.mockClear()
    mocks.generateCharacterReferences.mockClear()
    mocks.updateCharacter.mockResolvedValue({ data: { ok: true } })
    mocks.deleteCharacter.mockResolvedValue({ data: { ok: true, action: 'archived' } })
    mocks.aiRewriteCharacter.mockResolvedValue({ data: { ok: true, candidate: { personality: '坚定', ignored_field: '不要保存' } } })
    mocks.generateCharacterReferences.mockResolvedValue({ data: { ok: true, generated: { avatar_front_url: 'https://cdn.test/front.png' } } })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('opens detail drawer and saves edits', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    expect(document.body.textContent).toContain('角色详情')

    const nameInput = document.querySelector('[data-test="character-name-input"]')
    nameInput.value = '林岚新版'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    document.querySelector('[data-test="save-character"]').click()
    await flushPromises()

    expect(mocks.updateCharacter).toHaveBeenCalledWith('char-1', expect.objectContaining({ name: '林岚新版' }))
    wrapper.unmount()
  })

  it('regenerates one reference image slot', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    document.querySelector('[data-test="regenerate-avatar_front_url"]').click()
    await flushPromises()

    expect(mocks.generateCharacterReferences).toHaveBeenCalledWith('char-1', { slot: 'avatar_front_url' })
    wrapper.unmount()
  })

  it('shows style lock reference progress in the character drawer', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    expect(document.querySelector('[data-test="progress-avatar_front_url"]').textContent).toContain('风格锁定生成中')
    wrapper.unmount()
  })

  it('applies partial AI rewrite candidate over the current draft and ignores unsupported fields', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    document.querySelector('[data-test="request-character-rewrite"]').click()
    await flushPromises()
    wrapper.findComponent({ name: 'AiRewriteConfirmDialog' }).vm.$emit('confirm', {
      personality: '坚定',
      ignored_field: '不要保存',
    })
    await flushPromises()

    expect(mocks.updateCharacter).toHaveBeenCalledWith('char-1', {
      name: '林岚',
      role_type: 'protagonist',
      gender: 'female',
      personality: '坚定',
      appearance_desc: '短发',
      outfit_desc: '白色外套',
    })
    wrapper.unmount()
  })

  it('shows drawer-level errors for failed save and failed reference generation', async () => {
    mocks.updateCharacter.mockRejectedValueOnce(new Error('保存接口失败'))
    mocks.generateCharacterReferences.mockRejectedValueOnce(new Error('参考图接口失败'))
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    document.querySelector('[data-test="save-character"]').click()
    await flushPromises()
    expect(document.querySelector('[data-test="character-drawer-error"]').textContent).toContain('保存接口失败')

    document.querySelector('[data-test="regenerate-avatar_front_url"]').click()
    await flushPromises()
    expect(document.querySelector('[data-test="character-drawer-error"]').textContent).toContain('参考图接口失败')
    wrapper.unmount()
  })

  it('closes the drawer after successful delete or archive', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    document.querySelector('[data-test="delete-character"]').click()
    await flushPromises()
    wrapper.findComponent({ name: 'DangerConfirmDialog' }).vm.$emit('confirm')
    await flushPromises()

    expect(mocks.deleteCharacter).toHaveBeenCalledWith('char-1')
    expect(document.querySelector('[data-test="character-name-input"]')).toBeNull()
    wrapper.unmount()
  })
})
