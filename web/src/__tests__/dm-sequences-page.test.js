import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  listDMSequences: vi.fn(),
  createDMSequence: vi.fn(),
  updateDMSequence: vi.fn(),
  deleteDMSequence: vi.fn(),
  getDMSequence: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  fetch: vi.fn(),
}))

vi.mock('../api/dmSequences.js', () => ({
  listDMSequences: mocks.listDMSequences,
  createDMSequence: mocks.createDMSequence,
  updateDMSequence: mocks.updateDMSequence,
  deleteDMSequence: mocks.deleteDMSequence,
  getDMSequence: mocks.getDMSequence,
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}))

function streamResponse(text) {
  const encoded = new TextEncoder().encode(text)
  let read = false
  return {
    ok: true,
    body: {
      getReader() {
        return {
          read() {
            if (read) return Promise.resolve({ done: true })
            read = true
            return Promise.resolve({ done: false, value: encoded })
          },
        }
      },
    },
  }
}

function jsonResponse(data) {
  return {
    ok: true,
    json() {
      return Promise.resolve(data)
    },
  }
}

async function mountPage() {
  const DMSequenceManagePage = (await import('../views/DMSequenceManagePage.vue')).default
  const wrapper = mount(DMSequenceManagePage)
  await flushPromises()
  return wrapper
}

describe('DMSequenceManagePage AI generation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [] } })
    vi.stubGlobal('fetch', mocks.fetch)
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps generation errors visible after the stream ends', async () => {
    mocks.fetch.mockResolvedValue(streamResponse(
      'data: {"type":"status","text":"AI 正在生成..."}\n\n' +
      'data: {"type":"error","message":"JSON 解析失败，请重试"}\n\n'
    ))
    const wrapper = await mountPage()
    wrapper.vm.openCreate()
    wrapper.vm.aiDescription = '帮我生成三段自然话术'
    wrapper.vm.aiLinkUrl = 'https://t.cn/test'

    await wrapper.vm.generateSequence()
    await flushPromises()

    expect(wrapper.vm.generating).toBe(false)
    expect(wrapper.text()).toContain('错误: JSON 解析失败，请重试')
  })
})

describe('DMSequenceManagePage variant editing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [] } })
    mocks.updateDMSequence.mockResolvedValue({ data: { ok: true } })
    vi.stubGlobal('fetch', mocks.fetch)
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('saves current messages and clears variants after deleting the last variant', async () => {
    const sequence = {
      id: 'seq-1',
      name: '测试序列',
      industry: 'general',
      messages: [
        { order: 1, content: '原始消息', delay_ms: 2000 },
      ],
      variants: [
        [{ order: 1, content: '变体消息', delay_ms: 1800 }],
      ],
    }
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [sequence] } })
    const wrapper = await mountPage()

    wrapper.vm.openEdit(sequence)
    wrapper.vm.form.messages[0].content = '修改后的消息'
    wrapper.vm.deleteVariant(0)
    await wrapper.vm.handleSave()
    await flushPromises()

    expect(mocks.updateDMSequence).toHaveBeenCalledWith('seq-1', {
      name: '测试序列',
      industry: 'general',
      messages: [{ order: 1, content: '修改后的消息', delay_ms: 2000 }],
      variants: [],
    })
  })

  it('clears variants generated during the edit session after deleting them before save', async () => {
    const sequence = {
      id: 'seq-2',
      name: 'Generated Variant Sequence',
      industry: 'general',
      messages: [
        { order: 1, content: 'base message', delay_ms: 2000 },
      ],
      variants: null,
    }
    const generatedVariants = [
      [{ order: 1, content: 'generated variant', delay_ms: 1800 }],
    ]
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [sequence] } })
    mocks.fetch.mockResolvedValue(jsonResponse({
      ok: true,
      variants_count: 1,
      total_variants: 1,
      variants: generatedVariants,
    }))
    const wrapper = await mountPage()

    wrapper.vm.openEdit(sequence)
    wrapper.vm.variantCount = 1
    await wrapper.vm.generateVariants()
    await flushPromises()
    wrapper.vm.deleteVariant(0)
    await wrapper.vm.handleSave()
    await flushPromises()

    expect(mocks.updateDMSequence).toHaveBeenCalledWith('seq-2', {
      name: 'Generated Variant Sequence',
      industry: 'general',
      messages: [{ order: 1, content: 'base message', delay_ms: 2000 }],
      variants: [],
    })
  })

  it('keeps editing the same logical variant after deleting an earlier variant', async () => {
    const sequence = {
      id: 'seq-3',
      name: 'Editing Index Sequence',
      industry: 'general',
      messages: [
        { order: 1, content: 'base message', delay_ms: 2000 },
      ],
      variants: [
        [{ order: 1, content: 'variant 1', delay_ms: 1800 }],
        [{ order: 1, content: 'variant 2', delay_ms: 1900 }],
        [{ order: 1, content: 'variant 3', delay_ms: 2000 }],
      ],
    }
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [sequence] } })
    const wrapper = await mountPage()

    wrapper.vm.openEdit(sequence)
    wrapper.vm.startEditVariant(2)
    wrapper.vm.deleteVariant(0)

    expect(wrapper.vm.editingVariantIdx).toBe(1)
  })
})
