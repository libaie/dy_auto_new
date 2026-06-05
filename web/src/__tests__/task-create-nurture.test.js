import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  createTask: vi.fn(),
  batchCreateTasks: vi.fn(),
  generateKeywords: vi.fn(),
  listDMSequences: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('../api/tasks.js', () => ({
  createTask: mocks.createTask,
  batchCreateTasks: mocks.batchCreateTasks,
}))

vi.mock('../api/content.js', () => ({
  generateKeywords: mocks.generateKeywords,
}))

vi.mock('../api/dmSequences.js', () => ({
  listDMSequences: mocks.listDMSequences,
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => ({
    success: mocks.toastSuccess,
    error: mocks.toastError,
  }),
}))

const stubs = {
  TransitionRoot: { template: '<div><slot /></div>' },
  TransitionChild: { template: '<div><slot /></div>' },
  Dialog: { template: '<div><slot /></div>' },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h2><slot /></h2>' },
  TipIcon: { template: '<span />' },
}

async function mountDialog() {
  const TaskCreateDialog = (await import('../components/business/TaskCreateDialog.vue')).default
  return mount(TaskCreateDialog, {
    props: {
      open: true,
      accounts: [{ id: 'acct-1', nickname: 'Account 1' }],
      groups: [{ id: 'group-1', name: 'Group 1', member_count: 1 }],
      devices: [],
      templates: [],
      promptTemplates: [{ id: 'prompt-1', name: 'Prompt 1' }],
    },
    global: { stubs },
  })
}

describe('task create nurture payload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createTask.mockResolvedValue({ data: { ok: true } })
    mocks.batchCreateTasks.mockResolvedValue({ data: { created: 1 } })
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [] } })
  })

  it('includes prompt template and edited keyword matrix for advanced nurture tasks', async () => {
    const wrapper = await mountDialog()

    wrapper.vm.selectionMode = 'single'
    wrapper.vm.form.type = 'nurture'
    wrapper.vm.form.account_id = 'acct-1'
    wrapper.vm.nurtureMode = 'advanced'
    wrapper.vm.subTasks = [{ type: 'like', count: 1, content_template_id: '' }]
    wrapper.vm.selectedPromptTemplateId = 'prompt-1'
    wrapper.vm.nurtureKeywords = 'seed-a'
    wrapper.vm.nurtureKeywordMatrix = ['expanded-a']
    wrapper.vm.nurtureKeywordExpandCount = 13

    await wrapper.vm.handleCreate()
    await flushPromises()

    expect(mocks.createTask).toHaveBeenCalledTimes(1)
    const payload = mocks.createTask.mock.calls[0][0]
    expect(payload.params.prompt_template_id).toBe('prompt-1')
    expect(payload.params.keywords).toEqual(['seed-a'])
    expect(payload.params.keyword_matrix).toEqual(['seed-a', 'expanded-a'])
    expect(payload.params.expand_count).toBe(13)
  })

  it('leaves keyword matrix unset when only seed keywords are entered', async () => {
    const wrapper = await mountDialog()

    wrapper.vm.selectionMode = 'single'
    wrapper.vm.form.type = 'nurture'
    wrapper.vm.form.account_id = 'acct-1'
    wrapper.vm.nurtureMode = 'advanced'
    wrapper.vm.subTasks = [{ type: 'like', count: 1, content_template_id: '' }]
    wrapper.vm.nurtureKeywords = 'seed-a'
    wrapper.vm.nurtureKeywordMatrix = []

    await wrapper.vm.handleCreate()
    await flushPromises()

    const payload = mocks.createTask.mock.calls[0][0]
    expect(payload.params.keywords).toEqual(['seed-a'])
    expect(payload.params.keyword_matrix).toBeUndefined()
  })
})
