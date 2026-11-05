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
const filterPrivate = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')
const sortBy = ref('')
const sortOrder = ref('desc')

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
    const params = buildDataParams({ includePagination: true })

    let resp
    if (activeTab.value === 'comments') {
      resp = await listComments(params)
    } else if (activeTab.value === 'users') {
      resp = await listUsers(params)
    } else {
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

function buildDataParams({ includePagination = false } = {}) {
  const params = {}
  if (includePagination) {
    params.skip = (page.value - 1) * pageSize
    params.limit = pageSize
  }
  if (filterTaskId.value) params.task_id = filterTaskId.value
  if (searchQuery.value) params.search = searchQuery.value

  if (activeTab.value === 'comments') {
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterAccountId.value) params.account_id = filterAccountId.value
  } else if (activeTab.value === 'users') {
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterAccountId.value) params.account_id = filterAccountId.value
    if (filterPrivate.value) params.is_private = filterPrivate.value
    if (filterDateFrom.value) params.date_from = filterDateFrom.value
    if (filterDateTo.value) params.date_to = filterDateTo.value
    if (sortBy.value) { params.sort_by = sortBy.value; params.sort_order = sortOrder.value }
  } else if (activeTab.value === 'conversations') {
    if (filterAccountId.value) params.account_id = filterAccountId.value
    if (filterStage.value) params.stage = filterStage.value
    if (filterStatus.value) params.status = filterStatus.value
  }
  return params
}

const exporting = ref(false)
async function doExport(all) {
  exporting.value = true
  try {
    const params = buildDataParams({ includePagination: !all })

    const token = localStorage.getItem('token') || ''
    const resp = await fetch(`/api/data/export/${activeTab.value}?${new URLSearchParams(params)}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || '导出失败')
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const suffix = all ? 'all' : `page${page.value}`
    a.href = url
    a.download = `${activeTab.value}_${suffix}_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success(all ? '全部导出完成' : '本页导出完成')
  } catch (e) {
    toast.error('导出失败: ' + (e.message || '未知错误'))
  } finally { exporting.value = false }
}

const avatarGradients = [
  'linear-gradient(135deg, #6366f1, #a855f7)',
  'linear-gradient(135deg, #06b6d4, #3b82f6)',
  'linear-gradient(135deg, #f59e0b, #ef4444)',
  'linear-gradient(135deg, #10b981, #06b6d4)',
  'linear-gradient(135deg, #ec4899, #f97316)',
  'linear-gradient(135deg, #8b5cf6, #3b82f6)',
  'linear-gradient(135deg, #14b8a6, #84cc16)',
  'linear-gradient(135deg, #f43f5e, #a855f7)',
]
function avatarGradient(name) {
  if (!name) return avatarGradients[0]
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return avatarGradients[Math.abs(hash) % avatarGradients.length]
}

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
        class="relative px-4 py-2.5 text-sm font-medium transition-colors duration-200 cursor-pointer"
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

      <input v-if="activeTab === 'comments' || activeTab === 'users'" v-model="filterKeyword" @keyup.enter="handleSearch" placeholder="行业/关键词" class="w-32 rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />

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

      <div class="ml-auto flex gap-1.5">
        <button @click="doExport(false)" :disabled="exporting"
          class="px-3 py-1.5 text-sm rounded-lg border transition cursor-pointer"
          :class="exporting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-sky-500/10 hover:border-sky-500/30'"
          style="border-color: var(--border-default); color: var(--text-secondary);">
          {{ exporting ? '...' : '导出本页' }}
        </button>
        <button @click="doExport(true)" :disabled="exporting"
          class="px-3 py-1.5 text-sm rounded-lg border transition cursor-pointer"
          :class="exporting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-sky-500/10 hover:border-sky-500/30'"
          style="border-color: var(--border-default); color: var(--accent-400);">
          {{ exporting ? '...' : '导出全部' }}
        </button>
      </div>
    </div>

    <!-- Comments Tab -->
    <div v-if="activeTab === 'comments'">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无评论数据</p>
      </div>
      <div v-else class="card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr>
                <th class="px-4 py-3 text-left">昵称</th>
                <th class="px-4 py-3 text-left w-[18%]">评论内容</th>
                <th class="px-4 py-3 text-left w-[18%]">AI回复</th>
                <th class="px-4 py-3 text-left">关键词</th>
                <th class="px-4 py-3 text-right w-14">点赞</th>
                <th class="px-4 py-3 text-left">IP属地</th>
                <th class="px-4 py-3 text-left">意向省份</th>
                <th class="px-4 py-3 text-left">意向城市</th>
                <th class="px-4 py-3 text-left">意向景点</th>
                <th class="px-4 py-3 text-center w-14">作者</th>
                <th class="px-4 py-3 text-center w-16">来源</th>
                <th class="px-4 py-3 text-right w-24">评论时间</th>
                <th class="px-4 py-3 text-right w-24">采集时间</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-subtle);">
              <tr v-for="item in items" :key="item.id" class="group transition-colors duration-150" style="background: transparent;">
                <td class="px-4 py-3">
                  <span class="text-slate-200 font-medium">{{ item.nickname }}</span>
                </td>
                <td class="px-4 py-3">
                  <span class="text-slate-400 line-clamp-2 text-xs leading-relaxed" :title="item.content">{{ item.content }}</span>
                </td>
                <td class="px-4 py-3">
                  <span v-if="item.ai_reply" class="text-emerald-400/80 line-clamp-2 text-xs leading-relaxed" :title="item.ai_reply">{{ item.ai_reply }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3">
                  <span v-if="item.keyword" class="inline-block text-[11px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400/80">{{ item.keyword }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-right font-mono text-xs tabular-nums" :class="item.like_count > 0 ? 'text-amber-400/80' : 'text-slate-600'">{{ item.like_count || '0' }}</td>
                <td class="px-4 py-3 text-xs text-slate-500">{{ item.location || '-' }}</td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_province" class="text-amber-300/80">{{ item.intended_province }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_city" class="text-purple-300/80">{{ item.intended_city }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_attraction" class="text-cyan-300/80">{{ item.intended_attraction }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span v-if="item.is_author" class="inline-block text-[10px] px-1.5 py-0.5 rounded font-medium" style="background: rgba(245,158,11,0.15); color: #fbbf24;">作者</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="inline-block text-[10px] px-1.5 py-0.5 rounded font-medium" :class="item.data_source_type === 1 ? 'bg-rose-500/15 text-rose-400' : 'bg-slate-500/10 text-slate-500'">{{ item.data_source_type === 1 ? '带货' : '普通' }}</span>
                </td>
                <td class="px-4 py-3 text-right text-xs text-slate-500 tabular-nums whitespace-nowrap">{{ item.time_str ? formatDate(item.time_str) : '-' }}</td>
                <td class="px-4 py-3 text-right text-xs text-slate-500 tabular-nums whitespace-nowrap">{{ formatDate(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'">
      <!-- User-specific filters -->
      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <select v-model="filterPrivate" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">全部账号</option>
          <option value="no">公开账号</option>
          <option value="yes">私密账号</option>
        </select>
        <input type="date" v-model="filterDateFrom" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm w-36" title="采集开始日期" />
        <span class="text-slate-500 text-xs">至</span>
        <input type="date" v-model="filterDateTo" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm w-36" title="采集结束日期" />
        <select v-model="sortBy" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">默认排序</option>
          <option value="fans_count">粉丝数</option>
          <option value="likes_count">获赞数</option>
          <option value="follow_count">关注数</option>
          <option value="works_count">作品数</option>
          <option value="created_at">采集时间</option>
        </select>
        <button
          v-if="sortBy"
          @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'; fetchData()"
          class="rounded-lg border px-2.5 py-1.5 text-sm transition cursor-pointer"
          style="border-color: var(--border-default); color: var(--text-secondary);"
          :class="sortOrder === 'asc' ? 'bg-sky-500/10 border-sky-500/30 text-sky-300' : 'hover:bg-white/5'"
          :title="sortOrder === 'desc' ? '降序' : '升序'"
        >
          <svg class="w-3.5 h-3.5 inline transition-transform duration-200" :class="sortOrder === 'asc' ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>
          {{ sortOrder === 'desc' ? '降序' : '升序' }}
        </button>
      </div>

      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无用户数据</p>
      </div>
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div v-for="user in items" :key="user.id"
             class="group cursor-default transition-all duration-300 rounded-2xl overflow-hidden"
             style="background: linear-gradient(145deg, rgba(15,23,42,0.9), rgba(30,41,59,0.6)); border: 1px solid rgba(148,163,184,0.06);">
          <!-- Top accent bar -->
          <div class="h-1 w-full" :style="{ background: avatarGradient(user.nickname) }"></div>

          <!-- Header: Avatar + Identity -->
          <div class="flex items-start gap-3 px-4 pt-4 pb-3">
            <div class="relative shrink-0">
              <img v-if="user.avatar_url" :src="user.avatar_url" class="w-12 h-12 rounded-full object-cover ring-2 ring-white/10" :alt="user.nickname" />
              <div v-else class="w-12 h-12 rounded-full flex items-center justify-center text-base font-bold text-white shadow-lg"
                   :style="{ backgroundImage: avatarGradient(user.nickname) }">
                {{ (user.nickname || '?')[0] }}
              </div>
              <span v-if="user.is_private === '是'" class="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-rose-500 flex items-center justify-center ring-2 ring-slate-900" title="私密账号">
                <svg class="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5 mb-0.5">
                <p class="text-sm font-semibold text-white truncate">{{ user.nickname || '未知' }}</p>
                <span class="text-[9px] px-1.5 py-0.5 rounded-full font-medium shrink-0 tracking-wide"
                      :class="user.data_source_type === 1 ? 'bg-pink-500/15 text-pink-400 border border-pink-500/20' : 'bg-slate-500/10 text-slate-400 border border-slate-500/10'">
                  {{ user.data_source_type === 1 ? '带货' : '普通' }}
                </span>
              </div>
              <p class="text-[11px] text-slate-500 font-mono truncate">抖音号 {{ user.douyin_id || '-' }}</p>
            </div>
          </div>

          <!-- Stats grid -->
          <div class="grid grid-cols-4 gap-px mx-4 mb-3 rounded-xl overflow-hidden" style="background: rgba(255,255,255,0.03);">
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums" style="background: linear-gradient(135deg, #818cf8, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{{ user.fans_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">粉丝</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums" style="background: linear-gradient(135deg, #fbbf24, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{{ user.likes_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">获赞</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums text-slate-300">{{ user.follow_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">关注</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums text-slate-300">{{ user.works_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">作品</p>
            </div>
          </div>

          <!-- Destination -->
          <div v-if="user.intended_province || user.intended_city || user.intended_attraction"
               class="mx-4 mb-3 px-3 py-2 rounded-xl flex items-center gap-2 text-xs"
               style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.1);">
            <svg class="w-3.5 h-3.5 text-purple-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            <span class="text-slate-400 truncate">{{ [user.intended_province, user.intended_city, user.intended_attraction].filter(Boolean).join(' · ') }}</span>
          </div>

          <!-- Footer: Meta -->
          <div class="flex items-center gap-2 text-[11px] text-slate-500 px-4 py-2.5 border-t" style="border-color: rgba(255,255,255,0.04);">
            <span v-if="user.gender || user.age" class="inline-flex items-center gap-1">
              <svg class="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
              <template v-if="user.gender">{{ user.gender }} </template><template v-if="user.age">{{ user.age }}</template>
            </span>
            <span class="opacity-30" v-if="(user.gender || user.age) && user.ip_location">|</span>
            <span v-if="user.ip_location" class="inline-flex items-center gap-1 truncate">
              <svg class="w-3 h-3 opacity-50 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              {{ user.ip_location }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Conversations Tab -->
    <div v-if="activeTab === 'conversations'">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无私信数据</p>
      </div>
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
          <p v-if="conv.status === 'pending_confirmation'" class="mb-2 text-xs text-amber-400">发送待确认，已暂停自动重发</p>
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
