import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  listSelectors: vi.fn(),
  createSelector: vi.fn(),
  updateSelector: vi.fn(),
  deleteSelector: vi.fn(),
  toggleSelector: vi.fn(),
  generateRegex: vi.fn(),
  generateCleanPrompt: vi.fn(),
  toastError: vi.fn(),
  useWebSocket: vi.fn(),
}))

vi.mock('../api/selectors.js', () => ({
  listSelectors: mocks.listSelectors,
  createSelector: mocks.createSelector,
  updateSelector: mocks.updateSelector,
  deleteSelector: mocks.deleteSelector,
  toggleSelector: mocks.toggleSelector,
  generateRegex: mocks.generateRegex,
  generateCleanPrompt: mocks.generateCleanPrompt,
}))

vi.mock('@headlessui/vue', () => ({
  Dialog: { template: '<div><slot /></div>' },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h3><slot /></h3>' },
  TransitionRoot: { props: ['show'], template: '<div v-if="show"><slot /></div>' },
  TransitionChild: { template: '<div><slot /></div>' },
  Switch: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<button @click="$emit(`update:modelValue`, !modelValue)"><slot /></button>',
  },
  SwitchGroup: { template: '<div><slot /></div>' },
  SwitchLabel: { template: '<span><slot /></span>' },
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => ({ error: mocks.toastError }),
}))

vi.mock('../composables/useWebSocket.js', () => ({
  useWebSocket: mocks.useWebSocket,
}))

const selectorRows = [
  {
    action_name: 'is_search_view',
    description: '搜索页指纹',
    category: 'search',
    purpose: 'page_detect',
    strategy_logic: 'and',
    platform_version: 'default',
    resolution_profile: 'default',
    version: 3,
    enabled: true,
    strategies: [{ type: 'text', value: '搜索', priority: 1 }],
  },
  {
    action_name: 'is_user_view',
    description: '用户主页页指纹',
    category: 'profile',
    purpose: 'page_detect',
    strategy_logic: 'and',
    platform_version: 'default',
    resolution_profile: 'default',
    version: 3,
    enabled: true,
    strategies: [{ type: 'text', value: '粉丝', priority: 1 }],
  },
  {
    action_name: 'is_follow',
    description: '已关注状态指纹',
    category: 'profile',
    purpose: 'locate',
    platform_version: 'default',
    resolution_profile: 'default',
    version: 3,
    enabled: true,
    strategies: [{ type: 'text', value: '已关注', priority: 1 }],
  },
  {
    action_name: 'dm_entry_btn',
    description: '进入私信会话按钮',
    category: 'dm',
    purpose: 'locate',
    platform_version: 'default',
    resolution_profile: 'default',
    version: 3,
    enabled: true,
    strategies: [{ type: 'text', value: '私信', priority: 1 }],
  },
]

async function mountPage() {
  const SelectorsPage = (await import('../views/SelectorsPage.vue')).default
  const wrapper = mount(SelectorsPage, {
    global: {
      stubs: {
        ConfirmDialog: true,
        EmptyState: true,
        LoadingSpinner: true,
        StrategyCard: true,
        Teleport: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function clickTab(wrapper, label) {
  const tab = wrapper.findAll('button').find(button => button.text().includes(label))
  expect(tab).toBeTruthy()
  await tab.trigger('click')
  await nextTick()
}

describe('SelectorsPage filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listSelectors.mockResolvedValue({ data: { selectors: selectorRows, total: selectorRows.length, version: 3 } })
  })

  it('shows page-detect selectors in the page-detect tab by purpose', async () => {
    const wrapper = await mountPage()

    await clickTab(wrapper, '页面检测')

    expect(wrapper.text()).toContain('is_search_view')
    expect(wrapper.text()).toContain('is_user_view')
    expect(wrapper.text()).not.toContain('dm_entry_btn')
    expect(wrapper.text()).not.toContain('is_follow')
  })

  it('offers a profile tab for profile selectors', async () => {
    const wrapper = await mountPage()

    await clickTab(wrapper, '主页相关')

    expect(wrapper.text()).toContain('is_user_view')
    expect(wrapper.text()).toContain('is_follow')
    expect(wrapper.text()).not.toContain('dm_entry_btn')
  })
})
