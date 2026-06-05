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

async function mountTaskCreateDialog() {
  const TaskCreateDialog = (await import('../components/business/TaskCreateDialog.vue')).default
  return mount(TaskCreateDialog, {
    props: {
      open: true,
      accounts: [{ id: 'acct-1', nickname: 'Account 1' }],
      groups: [{ id: 'group-1', name: 'Group 1', member_count: 1 }],
      devices: [],
      templates: [],
      promptTemplates: [],
    },
    global: { stubs },
  })
}

async function mountKeywordSearchDialog() {
  const KeywordSearchDialog = (await import('../components/business/KeywordSearchDialog.vue')).default
  return mount(KeywordSearchDialog, {
    props: {
      open: true,
      accounts: [{ id: 'acct-1', nickname: 'Account 1' }],
      groups: [{ id: 'group-1', name: 'Group 1', member_count: 1 }],
      devices: [],
      templates: [],
      promptTemplates: [],
    },
    global: { stubs },
  })
}

describe('search_dm count validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.batchCreateTasks.mockResolvedValue({ data: { created: 1 } })
    mocks.createTask.mockResolvedValue({ data: { ok: true } })
    mocks.listDMSequences.mockResolvedValue({ data: { sequences: [] } })
  })

  it('blocks task create dialog from sending search_dm with count -1', async () => {
    const wrapper = await mountTaskCreateDialog()

    wrapper.vm.selectionMode = 'group'
    wrapper.vm.selectedGroupIds = ['group-1']
    wrapper.vm.form.type = 'search_dm'
    wrapper.vm.form.keyword = 'test'
    wrapper.vm.form.count = -1

    await wrapper.vm.handleCreate()
    await flushPromises()

    expect(mocks.batchCreateTasks).not.toHaveBeenCalled()
    expect(wrapper.vm.createError).toBeTruthy()
  })

  it('blocks keyword search dialog from sending search_dm with count -1', async () => {
    const wrapper = await mountKeywordSearchDialog()

    wrapper.vm.keywordList = ['test']
    wrapper.vm.keywordActionType = 'search_dm'
    wrapper.vm.keywordSelectionMode = 'single'
    wrapper.vm.keywordSingleAccountId = 'acct-1'
    wrapper.vm.keywordProcessingCount = -1

    await wrapper.vm.handleBatchCreateKeywordTasks()
    await flushPromises()

    expect(mocks.batchCreateTasks).not.toHaveBeenCalled()
    expect(wrapper.vm.keywordError).toBeTruthy()
  })
})
