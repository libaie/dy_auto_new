import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  listTemplates: vi.fn(),
  updateTemplate: vi.fn(),
  createTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
  toggleTemplate: vi.fn(),
  streamTemplateRewrite: vi.fn(),
  streamTemplateGeneration: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  useWebSocket: vi.fn(),
}))

vi.mock('../api/promptTemplates.js', () => ({
  listTemplates: mocks.listTemplates,
  updateTemplate: mocks.updateTemplate,
  createTemplate: mocks.createTemplate,
  deleteTemplate: mocks.deleteTemplate,
  toggleTemplate: mocks.toggleTemplate,
  streamTemplateRewrite: mocks.streamTemplateRewrite,
  streamTemplateGeneration: mocks.streamTemplateGeneration,
}))

vi.mock('@headlessui/vue', () => ({
  Dialog: { template: '<div><slot /></div>' },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h3><slot /></h3>' },
  TransitionRoot: { props: ['show'], template: '<div v-if="show"><slot /></div>' },
  TransitionChild: { template: '<div><slot /></div>' },
  Switch: { props: ['modelValue'], emits: ['update:modelValue'], template: '<button @click="$emit(`update:modelValue`, !modelValue)"><slot /></button>' },
  SwitchGroup: { template: '<div><slot /></div>' },
  SwitchLabel: { template: '<span><slot /></span>' },
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => ({
    success: mocks.toastSuccess,
    error: mocks.toastError,
  }),
}))

vi.mock('../composables/useWebSocket.js', () => ({
  useWebSocket: mocks.useWebSocket,
}))

const template = {
  name: 'health-default',
  industry: 'health',
  description: 'Default health template',
  content: { identity: { role: 'old' }, disabledWords: '' },
  version: 1,
  enabled: true,
  updated_at: '2026-05-01T00:00:00Z',
}

async function mountPage() {
  const PromptTemplatesPage = (await import('../views/PromptTemplatesPage.vue')).default
  const wrapper = mount(PromptTemplatesPage, {
    global: {
      stubs: {
        Teleport: true,
        TransitionRoot: { template: '<div><slot /></div>' },
        TransitionChild: { template: '<div><slot /></div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function openEdit(wrapper) {
  wrapper.vm.openEdit(template)
  await nextTick()
}

async function openCreate(wrapper) {
  wrapper.vm.openCreate()
  await nextTick()
}

function editor(wrapper) {
  return wrapper.find('[data-testid="template-content-json"]')
}

describe('PromptTemplatesPage rewrite UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    })
    localStorage.clear()
    mocks.listTemplates.mockResolvedValue({ data: { templates: [template] } })
    mocks.updateTemplate.mockResolvedValue({ data: { ok: true } })
    mocks.createTemplate.mockResolvedValue({ data: { ok: true } })
    mocks.deleteTemplate.mockResolvedValue({ data: { ok: true } })
    mocks.toggleTemplate.mockResolvedValue({ data: { ok: true } })
    mocks.streamTemplateGeneration.mockResolvedValue()
    mocks.streamTemplateRewrite.mockResolvedValue()
  })

  it('shows rewrite card in edit mode and hides it in create mode', async () => {
    const wrapper = await mountPage()

    await openEdit(wrapper)
    expect(wrapper.find('[data-testid="template-rewrite-card"]').exists()).toBe(true)

    await openCreate(wrapper)
    expect(wrapper.find('[data-testid="template-rewrite-card"]').exists()).toBe(false)
  })

  it('blocks rewrite for invalid current JSON and shows a toast', async () => {
    const wrapper = await mountPage()
    await openEdit(wrapper)
    await editor(wrapper).setValue('{bad json')
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    await wrapper.find('[data-testid="template-rewrite-button"]').trigger('click')
    await flushPromises()

    expect(mocks.streamTemplateRewrite).not.toHaveBeenCalled()
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining('JSON'))
  })

  it('successful rewrite replaces editor content without saving and enables restore', async () => {
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'token', text: '{"identity":' })
      await onEvent({ type: 'token', text: '{"role":"new"}}' })
      await onEvent({ type: 'done', content: { identity: { role: 'new' } } })
    })
    const wrapper = await mountPage()
    await openEdit(wrapper)
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    await wrapper.find('[data-testid="template-rewrite-button"]').trigger('click')
    await flushPromises()

    expect(mocks.streamTemplateRewrite).toHaveBeenCalledWith({
      industry: 'health',
      instruction: 'make it warmer',
      content: { identity: { role: 'old' }, disabledWords: '' },
    }, expect.objectContaining({ onEvent: expect.any(Function) }))
    expect(mocks.updateTemplate).not.toHaveBeenCalled()
    expect(JSON.parse(editor(wrapper).element.value)).toEqual({ identity: { role: 'new' } })
    expect(wrapper.find('[data-testid="template-rewrite-restore"]').exists()).toBe(true)
  })

  it('failed rewrite restores previous editor content and shows a toast', async () => {
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'token', text: '{"identity":{"role":"partial"}' })
      throw new Error('rewrite failed')
    })
    const wrapper = await mountPage()
    await openEdit(wrapper)
    const previous = editor(wrapper).element.value
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    await wrapper.find('[data-testid="template-rewrite-button"]').trigger('click')
    await flushPromises()

    expect(editor(wrapper).element.value).toBe(previous)
    expect(wrapper.find('[data-testid="template-rewrite-restore"]').exists()).toBe(false)
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining('rewrite failed'))
  })

  it('restore action returns previous content after success and clears restore flag', async () => {
    mocks.streamTemplateRewrite.mockImplementation(async (_payload, { onEvent }) => {
      await onEvent({ type: 'done', content: { identity: { role: 'new' } } })
    })
    const wrapper = await mountPage()
    await openEdit(wrapper)
    const previous = editor(wrapper).element.value
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    await wrapper.find('[data-testid="template-rewrite-button"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="template-rewrite-restore"]').trigger('click')
    await nextTick()

    expect(editor(wrapper).element.value).toBe(previous)
    expect(wrapper.find('[data-testid="template-rewrite-restore"]').exists()).toBe(false)
    expect(mocks.toastSuccess).toHaveBeenCalledWith(expect.stringContaining('恢复'))
  })

  it('while rewriting keeps dialog open and blocks save', async () => {
    let resolveRewrite
    mocks.streamTemplateRewrite.mockReturnValue(new Promise((resolve) => {
      resolveRewrite = resolve
    }))
    const wrapper = await mountPage()
    await openEdit(wrapper)
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    wrapper.vm.handleRewrite()
    await nextTick()

    expect(wrapper.vm.rewriting).toBe(true)
    wrapper.vm.closeDialog()
    await wrapper.vm.handleSave()
    await nextTick()

    expect(wrapper.vm.dialogOpen).toBe(true)
    expect(mocks.updateTemplate).not.toHaveBeenCalled()

    resolveRewrite()
    await flushPromises()
  })

  it('disables the JSON editor while rewrite is running', async () => {
    let resolveRewrite
    mocks.streamTemplateRewrite.mockReturnValue(new Promise((resolve) => {
      resolveRewrite = resolve
    }))
    const wrapper = await mountPage()
    await openEdit(wrapper)
    await wrapper.find('[data-testid="template-rewrite-instruction"]').setValue('make it warmer')

    wrapper.vm.handleRewrite()
    await nextTick()

    expect(editor(wrapper).element.disabled).toBe(true)

    resolveRewrite()
    await flushPromises()
  })

  it('disables generate input and ignores concurrent Enter while generation is running', async () => {
    let resolveGenerate
    mocks.streamTemplateGeneration.mockReturnValue(new Promise((resolve) => {
      resolveGenerate = resolve
    }))
    const wrapper = await mountPage()
    await openCreate(wrapper)
    const generateInput = wrapper.find('[data-testid="template-generate-input"]')
    expect(generateInput.exists()).toBe(true)
    await generateInput.setValue('build a health template')

    wrapper.vm.handleGenerate()
    await nextTick()

    expect(generateInput.element.disabled).toBe(true)

    await generateInput.trigger('keydown.enter')
    expect(mocks.streamTemplateGeneration).toHaveBeenCalledTimes(1)

    resolveGenerate()
    await flushPromises()
  })
})
