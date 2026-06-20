import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const originalCreateObjectURL = URL.createObjectURL
const originalRevokeObjectURL = URL.revokeObjectURL

const mocks = vi.hoisted(() => ({
  listComments: vi.fn(),
  listUsers: vi.fn(),
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  listAccounts: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  wsConnect: vi.fn(),
  routerReplace: vi.fn(),
  route: { query: {} },
  fetch: vi.fn(),
}))

vi.mock('../api/data.js', () => ({
  listComments: mocks.listComments,
  listUsers: mocks.listUsers,
  listConversations: mocks.listConversations,
  getConversation: mocks.getConversation,
}))

vi.mock('../api/accounts.js', () => ({
  listAccounts: mocks.listAccounts,
}))

vi.mock('../stores/toast.js', () => ({
  useToastStore: () => ({
    success: mocks.toastSuccess,
    error: mocks.toastError,
  }),
}))

vi.mock('../composables/useWebSocket.js', () => ({
  useWebSocket: () => ({ connect: mocks.wsConnect }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ replace: mocks.routerReplace }),
}))

async function mountPage() {
  const DataCenterPage = (await import('../views/DataCenterPage.vue')).default
  const wrapper = mount(DataCenterPage)
  await flushPromises()
  mocks.fetch.mockClear()
  return wrapper
}

function latestExportUrl() {
  const rawUrl = mocks.fetch.mock.calls.at(-1)[0]
  return new URL(rawUrl, 'http://localhost')
}

describe('DataCenterPage export filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
    mocks.listComments.mockResolvedValue({ data: { items: [], total: 0 } })
    mocks.listUsers.mockResolvedValue({ data: { items: [], total: 0 } })
    mocks.listConversations.mockResolvedValue({ data: { items: [], total: 0 } })
    mocks.getConversation.mockResolvedValue({ data: { conversation: null, messages: [], history_incomplete: false } })
    mocks.listAccounts.mockResolvedValue({ data: { accounts: [] } })
    mocks.fetch.mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['xlsx'])),
    })
    vi.stubGlobal('fetch', mocks.fetch)
    URL.createObjectURL = vi.fn(() => 'blob:test')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('includes the current conversation filters in export requests', async () => {
    const wrapper = await mountPage()

    wrapper.vm.activeTab = 'conversations'
    wrapper.vm.searchQuery = '张三'
    wrapper.vm.filterTaskId = 'task-1'
    wrapper.vm.filterAccountId = 'acc-1'
    wrapper.vm.filterStage = 'nurturing'
    wrapper.vm.filterStatus = 'paused'
    await nextTick()

    await wrapper.vm.doExport(true)

    const url = latestExportUrl()
    expect(url.pathname).toBe('/api/data/export/conversations')
    expect(url.searchParams.get('search')).toBe('张三')
    expect(url.searchParams.get('task_id')).toBe('task-1')
    expect(url.searchParams.get('account_id')).toBe('acc-1')
    expect(url.searchParams.get('stage')).toBe('nurturing')
    expect(url.searchParams.get('status')).toBe('paused')
    expect(url.searchParams.has('skip')).toBe(false)
    expect(url.searchParams.has('limit')).toBe(false)
  })

  it('includes user filters and pagination when exporting the current page', async () => {
    const wrapper = await mountPage()

    wrapper.vm.activeTab = 'users'
    wrapper.vm.page = 3
    wrapper.vm.searchQuery = '杭州'
    wrapper.vm.filterTaskId = 'task-2'
    wrapper.vm.filterKeyword = '旅游'
    wrapper.vm.filterAccountId = 'acc-2'
    wrapper.vm.filterPrivate = 'yes'
    wrapper.vm.filterDateFrom = '2026-05-01'
    wrapper.vm.filterDateTo = '2026-05-28'
    wrapper.vm.sortBy = 'fans_count'
    wrapper.vm.sortOrder = 'asc'
    await nextTick()

    await wrapper.vm.doExport(false)

    const url = latestExportUrl()
    expect(url.pathname).toBe('/api/data/export/users')
    expect(url.searchParams.get('search')).toBe('杭州')
    expect(url.searchParams.get('task_id')).toBe('task-2')
    expect(url.searchParams.get('keyword')).toBe('旅游')
    expect(url.searchParams.get('account_id')).toBe('acc-2')
    expect(url.searchParams.get('is_private')).toBe('yes')
    expect(url.searchParams.get('date_from')).toBe('2026-05-01')
    expect(url.searchParams.get('date_to')).toBe('2026-05-28')
    expect(url.searchParams.get('sort_by')).toBe('fans_count')
    expect(url.searchParams.get('sort_order')).toBe('asc')
    expect(url.searchParams.get('skip')).toBe('40')
    expect(url.searchParams.get('limit')).toBe('20')
  })

  it('renders source comment content on user cards', async () => {
    const wrapper = await mountPage()

    wrapper.vm.activeTab = 'users'
    wrapper.vm.items = [{
      id: 'user-entry-comment',
      nickname: '评论入口用户',
      douyin_id: 'entry-comment-user',
      source_comment_content: '刚从西湖回来，想找本地向导',
    }]
    await nextTick()

    expect(wrapper.text()).toContain('入口评论')
    expect(wrapper.text()).toContain('刚从西湖回来，想找本地向导')
  })
  it('opens a conversation detail drawer with ordered messages', async () => {
    mocks.route.query = { tab: 'conversations' }
    mocks.listConversations.mockResolvedValue({
      data: {
        items: [{
          id: 'conv-1',
          recipient_nickname: '张三',
          recipient_douyin_id: 'douyin-zhang',
          current_stage: 'nurturing',
          total_dm_count: 2,
          last_dm_content: '第二条',
          last_dm_at: '2026-06-20T10:00:00',
        }],
        total: 1,
      },
    })
    mocks.getConversation.mockResolvedValue({
      data: {
        conversation: {
          id: 'conv-1',
          recipient_nickname: '张三',
          recipient_douyin_id: 'douyin-zhang',
          current_stage: 'nurturing',
          total_dm_count: 2,
          last_dm_content: '第二条',
          last_dm_at: '2026-06-20T10:00:00',
        },
        history_incomplete: false,
        messages: [
          { id: 'm1', message_order: 1, content: '第一条', status: 'sent', dm_sequence_id: 'seq-1', sent_at: '2026-06-20T09:59:00' },
          { id: 'm2', message_order: 2, content: '第二条', status: 'failed', error_message: '发送失败', sent_at: null },
        ],
      },
    })

    const wrapper = await mountPage()
    await wrapper.get('[data-testid="conversation-card"]').trigger('click')
    await flushPromises()

    expect(mocks.getConversation).toHaveBeenCalledWith('conv-1')
    expect(wrapper.text()).toContain('消息流水')
    expect(wrapper.text()).toContain('第一条')
    expect(wrapper.text()).toContain('第二条')
    expect(wrapper.text()).toContain('失败')
    expect(wrapper.text()).toContain('seq-1')
  })

  it('keeps the conversation list visible when detail loading fails', async () => {
    mocks.route.query = { tab: 'conversations' }
    mocks.listConversations.mockResolvedValue({
      data: { items: [{ id: 'conv-error', recipient_nickname: '李四', recipient_douyin_id: 'douyin-li', current_stage: 'qualifying', total_dm_count: 1, last_dm_content: '旧摘要' }], total: 1 },
    })
    mocks.getConversation.mockRejectedValue(new Error('network'))

    const wrapper = await mountPage()
    await wrapper.get('[data-testid="conversation-card"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('李四')
    expect(wrapper.text()).toContain('旧摘要')
    expect(wrapper.text()).toContain('详情加载失败')
  })
})
