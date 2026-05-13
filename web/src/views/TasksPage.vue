<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ChannelDetail from '../components/ChannelDetail.vue'
import TaskCreateDialog from '../components/business/TaskCreateDialog.vue'
import KeywordSearchDialog from '../components/business/KeywordSearchDialog.vue'
import ChannelList from '../components/business/ChannelList.vue'
import { listTasks, cancelTask, deleteTask, batchDeleteTasks } from '../api/tasks.js'
import { listChannels } from '../api/channels.js'
import { listAccounts } from '../api/accounts.js'
import { listGroups } from '../api/accountGroups.js'
import { listDevices } from '../api/devices.js'
import { listTemplates } from '../api/content.js'
import { listTemplates as listPromptTemplates } from '../api/promptTemplates.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { TASK_TYPE_LABEL_MAP, TASK_TYPE_OPTIONS, STATUS_FILTER_OPTIONS, TASK_TABLE_COLUMNS } from '../constants/tasks.js'
import { CHANNEL_TASK_TYPE_LABEL, CHANNEL_STATUS_LABEL, CHANNEL_STATUS_CLASS } from '../constants/channels.js'

const toast = useToastStore()

// --- Task state ---
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')
const searchQuery = ref('')
const typeFilter = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')
const selectedTaskIds = ref([])
const batchDeleting = ref(false)
const pageError = ref(null)
const taskProgress = reactive({})

// --- Ref data ---
const accounts = ref([])
const groups = ref([])
const devices = ref([])
const templates = ref([])
const promptTemplates = ref([])

// --- Channel state ---
const channels = ref([])
const channelsLoading = ref(false)
const detailChannel = ref(null)
const channelsExpanded = ref(false)

// --- Dialogs ---
const showCreateDialog = ref(false)
const showKeywordDialog = ref(false)
const showCancelDialog = ref(false)
const cancellingTask = ref(null)
const cancelling = ref(false)

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'task_updated' || msg.event === 'tasks_changed') fetchTasks(true)
    else if (msg.event === 'task_progress') taskProgress[msg.task_id] = { step: msg.step, detail: msg.detail, progress: msg.progress }
  },
})

// --- Tasks ---
async function fetchTasks(silent) {
  if (!silent) loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const params = { skip, limit: pageSize, sort_by: sortBy.value, sort_order: sortOrder.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (typeFilter.value) params.type = typeFilter.value
    if (searchQuery.value) params.search = searchQuery.value
    const res = await listTasks(params)
    tasks.value = res.data.tasks || []
    total.value = res.data.total || 0
    if (!silent) selectedTaskIds.value = []
    const currentIds = {}
    for (const t of tasks.value) currentIds[t.id] = true
    for (const key in taskProgress) { if (!currentIds[key]) delete taskProgress[key] }
  } catch (e) {
    if (!silent) toast.error('加载任务列表失败')
    tasks.value = []; total.value = 0
  } finally { loading.value = false }
}

async function handleDeleteTask(row) {
  try { await deleteTask(row.id); toast.success('已删除'); fetchTasks() } catch { toast.error('删除失败') }
}
async function handleBatchDelete() {
  if (!selectedTaskIds.value.length) { toast.error('请先选择任务'); return }
  batchDeleting.value = true
  try { const res = await batchDeleteTasks(selectedTaskIds.value); toast.success(`已删除 ${res.data.deleted} 个任务`); fetchTasks() }
  catch { toast.error('批量删除失败') }
  finally { batchDeleting.value = false }
}
function handleSort(col) {
  if (sortBy.value === col) sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  else { sortBy.value = col; sortOrder.value = 'desc' }
  fetchTasks()
}
function toggleSelectAll() {
  if (selectedTaskIds.value.length === tasks.value.length) selectedTaskIds.value = []
  else selectedTaskIds.value = tasks.value.map(t => t.id)
}
function handlePageChange(p) { page.value = p; fetchTasks() }
function openCancelDialog(task) { cancellingTask.value = task; showCancelDialog.value = true }
async function handleCancel() {
  if (!cancellingTask.value) return
  cancelling.value = true
  try { await cancelTask(cancellingTask.value.id); showCancelDialog.value = false; cancellingTask.value = null; fetchTasks() }
  catch (e) { pageError.value = e.response?.data?.detail || '取消失败，请重试' }
  finally { cancelling.value = false }
}

// --- Channels ---
async function fetchChannels() {
  channelsLoading.value = true
  try { const resp = await listChannels(); channels.value = resp.data.channels || [] }
  catch {}
  finally { channelsLoading.value = false }
}
const activeChannelCount = () => channels.value.filter(c => c.status === 'active').length
const pausedChannelCount = () => channels.value.filter(c => c.status === 'paused').length

// --- Ref data ---
async function loadRefData() {
  try {
    const [acctRes, grpRes, devRes, tplRes, ptRes] = await Promise.all([
      listAccounts({ limit: 100 }), listGroups({ limit: 100 }), listDevices({ limit: 100 }),
      listTemplates({ limit: 100 }), listPromptTemplates(false),
    ])
    accounts.value = acctRes.data.accounts || []
    groups.value = grpRes.data.groups || grpRes.data || []
    devices.value = devRes.data.devices || []
    templates.value = tplRes.data.templates || []
    promptTemplates.value = (ptRes.data.templates || []).filter(t => t.enabled)
  } catch {}
}

function onCreated() {
  showCreateDialog.value = false; showKeywordDialog.value = false
  page.value = 1; fetchTasks(); fetchChannels()
}
function onChannelRefresh() { fetchChannels(); fetchTasks(true) }

watch(statusFilter, () => { page.value = 1; fetchTasks() })
onMounted(() => { fetchTasks(); fetchChannels(); loadRefData() })
</script>

<template>
  <div>
    <!-- Page error -->
    <div v-if="pageError" class="mb-4 card border-red-500/30 text-red-400 px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- ====== 通道区 ====== -->
    <div class="mb-5">
      <div
        class="flex items-center justify-between px-4 py-2.5 rounded-xl cursor-pointer select-none transition-all duration-200"
        :class="channelsExpanded ? 'card' : 'card hover:border-accent'"
        style="border-color: var(--border-default);"
        @click="channelsExpanded = !channelsExpanded"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <div class="flex items-center gap-2 shrink-0">
            <svg class="w-4 h-4" :class="channelsExpanded ? 'text-sky-400' : 'text-slate-500'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-sm font-semibold text-slate-300">通道</span>
            <span class="text-xs font-mono text-slate-500">({{ channels.length }})</span>
          </div>

          <!-- 摘要：每个通道 pill + hover 详情浮层 -->
          <div v-if="!channelsExpanded && channels.length > 0" class="hidden md:flex items-center gap-2 min-w-0 flex-1 overflow-visible">
            <template v-for="ch in channels.slice(0, 4)" :key="ch.id">
              <div class="relative group shrink-0">
                <!-- Pill -->
                <div class="flex items-center gap-2 px-2.5 py-1 rounded-lg cursor-default transition-colors duration-150" style="background: var(--bg-surface); border: 1px solid var(--border-subtle);"
                  :class="{
                    'hover:border-emerald-500/30': ch.status === 'active',
                    'hover:border-amber-500/30': ch.status === 'paused',
                    'hover:border-blue-500/30': ch.status === 'completed',
                  }">
                  <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="{
                    'bg-emerald-400': ch.status === 'active',
                    'bg-amber-400': ch.status === 'paused',
                    'bg-blue-400': ch.status === 'completed',
                    'bg-slate-500': ch.status === 'cancelled',
                  }"></span>
                  <span class="text-xs font-medium text-slate-300 truncate max-w-[70px]">{{ ch.group_name || '-' }}</span>
                  <span class="text-[10px] font-mono tabular-nums" style="color: var(--accent-400);">{{ ch.completed }}/{{ ch.total }}</span>
                </div>

                <!-- Hover 详情浮层 -->
                <div class="absolute top-full mt-2 left-0 z-50 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 pointer-events-none" style="min-width: 220px;">
                  <div class="card p-4 space-y-2.5" style="box-shadow: var(--shadow-xl); border-color: var(--border-strong);">
                    <!-- 头部 -->
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-semibold text-white truncate max-w-[120px]">{{ ch.group_name || '未命名' }}</span>
                      <span :class="CHANNEL_STATUS_CLASS[ch.status] || 'bg-slate-600/50 text-slate-400'" class="px-2 py-0.5 text-[10px] rounded-full font-medium">
                        {{ CHANNEL_STATUS_LABEL[ch.status] || ch.status }}
                      </span>
                    </div>
                    <!-- 分隔线 -->
                    <div style="border-top: 1px solid var(--border-subtle);"></div>
                    <!-- 任务信息 -->
                    <div class="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span class="text-slate-500">任务类型</span>
                        <p class="text-slate-200 font-medium">{{ CHANNEL_TASK_TYPE_LABEL[ch.task_type] || ch.task_type }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">账号模式</span>
                        <p class="text-slate-200 font-medium">{{ ch.account_mode === 'single_account' ? '单账号' : '轮转' }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">已分发</span>
                        <p class="text-slate-200 font-mono font-semibold tabular-nums">{{ ch.assigned || 0 }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">待处理</span>
                        <p class="text-amber-300 font-mono font-semibold tabular-nums">{{ ch.pending || 0 }}</p>
                      </div>
                    </div>
                    <!-- 进度条 -->
                    <div>
                      <div class="flex justify-between text-[10px] mb-1">
                        <span class="text-slate-500">完成进度</span>
                        <span class="font-mono tabular-nums" style="color: var(--accent-400);">{{ ch.total ? Math.round(ch.completed / ch.total * 100) : 0 }}%</span>
                      </div>
                      <div class="w-full h-1.5 rounded-full bg-white/5">
                        <div class="h-full rounded-full transition-all duration-500" :style="{ width: ch.total ? (ch.completed / ch.total * 100) + '%' : '0%', background: ch.status === 'active' ? 'linear-gradient(90deg, #34d399, #22d3ee)' : 'linear-gradient(90deg, #fbbf24, #f59e0b)' }"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <span v-if="channels.length > 4" class="text-xs text-slate-600 shrink-0">+{{ channels.length - 4 }}</span>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <span v-if="activeChannelCount()" class="hidden sm:flex items-center gap-1 text-xs"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span class="text-emerald-400 font-semibold">{{ activeChannelCount() }}</span></span>
          <span v-if="pausedChannelCount()" class="hidden sm:flex items-center gap-1 text-xs"><span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span><span class="text-amber-400 font-semibold">{{ pausedChannelCount() }}</span></span>
          <svg class="w-4 h-4 text-slate-500 transition-transform duration-200" :class="channelsExpanded ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      <!-- 展开的通道卡片网格 -->
      <div v-if="channelsExpanded" class="mt-3 animate-in">
        <ChannelList
          :channels="channels"
          :loading="channelsLoading"
          @refresh="onChannelRefresh"
          @detail="detailChannel = $event"
        />
      </div>
    </div>

    <!-- ====== 任务区 ====== -->
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-bold text-white">任务列表</h1>
      <div class="flex items-center gap-2 flex-wrap">
        <input v-model="searchQuery" @keyup.enter="page=1;fetchTasks()" placeholder="搜索..." class="w-36 rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
        <select v-model="typeFilter" @change="page=1;fetchTasks()" class="rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">全部类型</option>
          <option v-for="opt in TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="statusFilter" class="rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option v-for="opt in STATUS_FILTER_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <button v-if="selectedTaskIds.length" class="btn-danger text-xs" @click="handleBatchDelete" :disabled="batchDeleting">
          {{ batchDeleting ? '...' : `删除(${selectedTaskIds.length})` }}
        </button>
        <button class="btn-ghost text-xs" style="border-color: var(--border-accent); color: var(--accent-400);" @click="showKeywordDialog = true">
          <svg class="-ml-0.5 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          AI 关键词搜索
        </button>
        <button class="btn-primary text-xs" @click="showCreateDialog = true">
          <svg class="-ml-0.5 w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          创建任务
        </button>
      </div>
    </div>

    <!-- Task Table -->
    <DataTable :columns="TASK_TABLE_COLUMNS" :data="tasks" :loading="loading" :total="total" :page="page" :page-size="pageSize" @page-change="handlePageChange">
      <template #header-select>
        <input type="checkbox" :checked="tasks.length > 0 && selectedTaskIds.length === tasks.length" @change="toggleSelectAll" class="rounded" />
      </template>
      <template #cell-select="{ row }">
        <input type="checkbox" :value="row.id" v-model="selectedTaskIds" class="rounded" />
      </template>
      <template #cell-type="{ value }">{{ TASK_TYPE_LABEL_MAP[value] || value }}</template>
      <template #cell-keyword="{ row }">
        <span class="text-sm" style="color: var(--text-secondary);">{{ row.params?.keyword || row.params?.keywords?.[0] || '-' }}</span>
      </template>
      <template #cell-account_id="{ value }">
        <span style="color: var(--text-secondary);">{{ accounts.find(a => a.id === value)?.nickname || value }}</span>
      </template>
      <template #cell-device_id="{ value }">
        <span v-if="value" style="color: var(--text-secondary);">{{ devices.find(d => d.id === value)?.name || value }}</span>
        <span v-else class="text-slate-500">自动分配</span>
      </template>
      <template #cell-progress="{ row }">
        <!-- 已完成任务：显示结果统计 -->
        <div v-if="row.status === 'completed' && row.result?.result" class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs min-w-[180px]">
          <span class="font-mono tabular-nums" style="color: var(--accent-400);">{{ row.result.result.success_count || 0 }}</span>
          <span class="text-slate-500">回复</span>
          <span v-if="row.result.result.skipped" class="font-mono tabular-nums text-slate-400">{{ row.result.result.skipped }}</span>
          <span v-if="row.result.result.skipped" class="text-slate-600">跳过</span>
          <span v-if="row.result.result.follow_count" class="font-mono tabular-nums text-amber-400">{{ row.result.result.follow_count }}</span>
          <span v-if="row.result.result.follow_count" class="text-slate-600">关注</span>
          <span v-if="row.result.result.dm_count" class="font-mono tabular-nums text-emerald-400">{{ row.result.result.dm_count }}</span>
          <span v-if="row.result.result.dm_count" class="text-slate-600">私信</span>
        </div>
        <!-- 运行中任务：显示进度 -->
        <div v-else-if="taskProgress[row.id]" class="flex flex-col gap-0.5 min-w-[140px]">
          <span class="text-xs" style="color: var(--accent-400);">{{ taskProgress[row.id].step }}</span>
          <span class="text-[11px] text-slate-500">{{ taskProgress[row.id].detail }}</span>
        </div>
        <!-- 失败任务：显示失败原因 -->
        <div v-else-if="row.status === 'failed' && row.result" class="flex flex-col gap-0.5 min-w-[140px]">
          <span class="text-xs text-red-400">{{ row.result.error || '执行失败' }}</span>
          <span v-if="row.result.result" class="text-[11px] text-slate-500">
            {{ row.result.result.success_count || 0 }} 回复 · {{ row.result.result.skipped || 0 }} 跳过
          </span>
        </div>
        <span v-else class="text-xs text-slate-500">-</span>
      </template>
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #cell-created_at="{ value }">{{ formatDate(value) }}</template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button v-if="row.status === 'pending' || row.status === 'running'" class="btn-danger text-xs" @click="openCancelDialog(row)">取消</button>
          <button v-if="row.status === 'failed' || row.status === 'cancelled'" class="px-3 py-1 text-xs font-medium text-orange-400 hover:text-orange-300 hover:bg-orange-400/10 rounded-lg transition-colors" @click="handleDeleteTask(row)">删除</button>
        </div>
      </template>
    </DataTable>

    <!-- Dialogs -->
    <TaskCreateDialog :open="showCreateDialog" :accounts="accounts" :groups="groups" :devices="devices" :templates="templates" :prompt-templates="promptTemplates" @close="showCreateDialog = false" @created="onCreated" />
    <KeywordSearchDialog :open="showKeywordDialog" :accounts="accounts" :groups="groups" :devices="devices" :templates="templates" :prompt-templates="promptTemplates" @close="showKeywordDialog = false" @created="onCreated" />
    <ConfirmDialog :open="showCancelDialog" title="取消任务" message="确定要取消该任务吗？" confirm-text="取消任务" :danger="true" @confirm="handleCancel" @cancel="showCancelDialog = false" />
    <ChannelDetail v-if="detailChannel" :channel="detailChannel" @close="detailChannel = null" @refresh="onChannelRefresh" />
  </div>
</template>
