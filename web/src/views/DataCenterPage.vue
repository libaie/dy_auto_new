<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listComments, listUsers, listConversations } from '../api/data.js'
import { listAccounts } from '../api/accounts.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { formatDate } from '../utils/format.js'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const tabs = [
  { key: 'comments', label: '评论采集' },
  { key: 'users', label: '用户资料' },
  { key: 'conversations', label: '私信会话' },
]
const activeTab = ref('comments')
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

// Filters
const searchQuery = ref('')
const filterKeyword = ref('')
const filterAccountId = ref('')
const filterStage = ref('')
const filterStatus = ref('')
const filterTaskId = ref('')

// Ref data
const accounts = ref([])
const newDataBadge = ref({ comments: 0, users: 0, conversations: 0 })

// URL sync
watch(() => route.query.tab, (val) => {
  if (val && tabs.some(t => t.key === val)) activeTab.value = val
})
watch(() => route.query.task_id, (val) => {
  filterTaskId.value = val || ''
  if (val) fetchData()
})

function switchTab(key) {
  activeTab.value = key
  page.value = 1
  newDataBadge.value[key] = 0
  router.replace({ query: { tab: key, ...(filterTaskId.value ? { task_id: filterTaskId.value } : {}) } })
  fetchData()
}

function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
const VALID_WS_TYPES = ['comments', 'users', 'conversations']
const { connect: wsConnect } = useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'data_changed' && VALID_WS_TYPES.includes(msg.type)) {
      newDataBadge.value[msg.type] = (newDataBadge.value[msg.type] || 0) + 1
    }
  },
})

async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize, limit: pageSize }
    if (searchQuery.value) params.search = searchQuery.value
    if (filterTaskId.value) params.task_id = filterTaskId.value

    let resp
    if (activeTab.value === 'comments') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
      resp = await listComments(params)
    } else if (activeTab.value === 'users') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      resp = await listUsers(params)
    } else {
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterStage.value) params.stage = filterStage.value
      if (filterStatus.value) params.status = filterStatus.value
      resp = await listConversations(params)
    }
    items.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch {
    toast.error('加载数据失败')
    items.value = []
    total.value = 0
  } finally { loading.value = false }
}

function handlePageChange(p) { page.value = p; fetchData() }
function handleSearch() { page.value = 1; fetchData() }

const stageBadgeClass = (s) => ({
  qualifying: 'bg-blue-500/20 text-blue-300',
  nurturing: 'bg-emerald-500/20 text-emerald-300',
  converting: 'bg-amber-500/20 text-amber-300',
  follow_up: 'bg-purple-500/20 text-purple-300',
}[s] || 'bg-slate-500/20 text-slate-300')

const stageLabel = (s) => ({
  qualifying: '触达', nurturing: '培育', converting: '转化', follow_up: '跟进',
}[s] || s)

// Init
onMounted(async () => {
  wsConnect()
  try {
    const res = await listAccounts({ limit: 100 })
    accounts.value = res.data.accounts || []
  } catch { accounts.value = [] }
  if (route.query.tab) activeTab.value = route.query.tab
  if (route.query.task_id) filterTaskId.value = route.query.task_id
  fetchData()
})
</script>

<template>
  <div>
    <h1 class="text-xl font-bold text-white mb-5">数据中心</h1>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b" style="border-color: var(--border-subtle);">
      <button
        v-for="tab in tabs" :key="tab.key"
        @click="switchTab(tab.key)"
        class="relative px-4 py-2.5 text-sm font-medium transition-colors duration-200"
        :class="activeTab === tab.key ? 'text-sky-300' : 'text-slate-400 hover:text-slate-200'"
      >
        {{ tab.label }}
        <span v-if="newDataBadge[tab.key]" class="ml-1.5 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-sky-500 text-white">{{ newDataBadge[tab.key] > 99 ? '99+' : newDataBadge[tab.key] }}</span>
        <div v-if="activeTab === tab.key" class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full" style="background: linear-gradient(90deg, var(--accent-500), var(--accent-400));"></div>
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <input v-model="searchQuery" @keyup.enter="handleSearch" placeholder="搜索..." class="w-40 rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />

      <input v-if="activeTab === 'comments'" v-model="filterKeyword" @keyup.enter="handleSearch" placeholder="关键词" class="w-28 rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />

      <select v-model="filterAccountId" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
        <option value="">全部账号</option>
        <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname || a.douyin_id || a.id }}</option>
      </select>

      <select v-if="activeTab === 'conversations'" v-model="filterStage" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
        <option value="">全部阶段</option>
        <option value="qualifying">触达</option>
        <option value="nurturing">培育</option>
        <option value="converting">转化</option>
        <option value="follow_up">跟进</option>
      </select>

      <span v-if="filterTaskId" class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-sky-500/20 text-sky-300">
        任务: {{ filterTaskId.slice(0, 8) }}...
        <button @click="filterTaskId = ''; router.replace({ query: { tab: activeTab } }); fetchData()" class="hover:text-sky-100">&times;</button>
      </span>
    </div>

    <!-- Comments Tab -->
    <div v-if="activeTab === 'comments'">
      <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="items.length === 0" class="text-center py-12 text-slate-500">暂无评论数据</div>
      <div v-else class="card overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-slate-400 border-b" style="border-color: var(--border-subtle);">
              <th class="px-4 py-3 font-medium">昵称</th>
              <th class="px-4 py-3 font-medium">内容</th>
              <th class="px-4 py-3 font-medium">AI回复</th>
              <th class="px-4 py-3 font-medium">关键词</th>
              <th class="px-4 py-3 font-medium w-16">点赞</th>
              <th class="px-4 py-3 font-medium">IP属地</th>
              <th class="px-4 py-3 font-medium">作者</th>
              <th class="px-4 py-3 font-medium w-36">时间</th>
            </tr>
          </thead>
          <tbody class="divide-y" style="border-color: var(--border-subtle);">
            <tr v-for="item in items" :key="item.id" class="hover:bg-white/5 transition-colors">
              <td class="px-4 py-3 text-slate-200 font-medium">{{ item.nickname }}</td>
              <td class="px-4 py-3 text-slate-400 max-w-[200px] truncate" :title="item.content">{{ item.content }}</td>
              <td class="px-4 py-3 text-emerald-400 max-w-[200px] truncate" :title="item.ai_reply">{{ item.ai_reply || '-' }}</td>
              <td class="px-4 py-3 text-slate-500">{{ item.keyword || '-' }}</td>
              <td class="px-4 py-3 text-slate-400 font-mono text-xs">{{ item.like_count || '0' }}</td>
              <td class="px-4 py-3 text-slate-500 text-xs">{{ item.location || '-' }}</td>
              <td class="px-4 py-3"><span v-if="item.is_author" class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">作者</span></td>
              <td class="px-4 py-3 text-slate-500 text-xs">{{ formatDate(item.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'">
      <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="items.length === 0" class="text-center py-12 text-slate-500">暂无用户数据</div>
      <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div v-for="user in items" :key="user.id" class="card p-4 hover:border-sky-500/30 transition-colors cursor-default">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white" style="background: linear-gradient(135deg, #6366f1, #a855f7);">
              {{ (user.nickname || '?')[0] }}
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-slate-200 truncate">{{ user.nickname || '-' }}</p>
              <p class="text-xs text-slate-500 font-mono">{{ user.douyin_id || '-' }}</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div><span class="text-slate-500">获赞</span><p class="text-slate-300 font-mono">{{ user.likes_count || '-' }}</p></div>
            <div><span class="text-slate-500">关注</span><p class="text-slate-300 font-mono">{{ user.follow_count || '-' }}</p></div>
            <div><span class="text-slate-500">粉丝</span><p class="text-slate-300 font-mono">{{ user.fans_count || '-' }}</p></div>
            <div><span class="text-slate-500">作品</span><p class="text-slate-300 font-mono">{{ user.works_count || '-' }}</p></div>
          </div>
          <div class="flex items-center justify-between mt-3 pt-3 border-t text-xs" style="border-color: var(--border-subtle);">
            <span class="text-slate-500">{{ user.gender || '-' }} {{ user.age || '' }}</span>
            <span class="text-slate-500">{{ user.ip_location || '-' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Conversations Tab -->
    <div v-if="activeTab === 'conversations'">
      <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="items.length === 0" class="text-center py-12 text-slate-500">暂无私信数据</div>
      <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="conv in items" :key="conv.id" class="card p-4 hover:border-sky-500/30 transition-colors cursor-default">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0" style="background: linear-gradient(135deg, #06b6d4, #3b82f6);">
                {{ (conv.recipient_nickname || '?')[0] }}
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-slate-200 truncate">{{ conv.recipient_nickname }}</p>
                <p class="text-[11px] text-slate-500 font-mono truncate">{{ conv.recipient_douyin_id || '-' }}</p>
              </div>
            </div>
            <span class="px-2 py-0.5 text-[10px] rounded-full font-medium shrink-0" :class="stageBadgeClass(conv.current_stage)">
              {{ stageLabel(conv.current_stage) }}
            </span>
          </div>
          <p class="text-xs text-slate-400 line-clamp-2 mb-3 min-h-[2rem]">{{ conv.last_dm_content || '暂无消息' }}</p>
          <div class="flex items-center justify-between text-[11px] text-slate-500 pt-3 border-t" style="border-color: var(--border-subtle);">
            <span>共 {{ conv.total_dm_count || 0 }} 条</span>
            <span>{{ conv.last_dm_at ? formatDate(conv.last_dm_at) : '-' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex items-center justify-between mt-6">
      <span class="text-sm text-slate-500">共 {{ total }} 条</span>
      <div class="flex gap-2">
        <button :disabled="page <= 1" @click="handlePageChange(page - 1)" class="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-30" style="border-color: var(--border-default); color: var(--text-secondary);">上一页</button>
        <span class="px-3 py-1.5 text-sm font-mono" style="color: var(--accent-400);">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button :disabled="page >= Math.ceil(total / pageSize)" @click="handlePageChange(page + 1)" class="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-30" style="border-color: var(--border-default); color: var(--text-secondary);">下一页</button>
      </div>
    </div>
  </div>
</template>
