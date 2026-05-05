<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { listTasks, createTask, batchCreateTasks, cancelTask } from '../api/tasks.js'
import { listChannels, updateChannel, deleteChannel as deleteChannelApi } from '../api/channels.js'
import { listAccounts } from '../api/accounts.js'
import { listGroups } from '../api/accountGroups.js'
import { listDevices } from '../api/devices.js'
import { listTemplates, generateKeywords } from '../api/content.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'
import ChannelDetail from '../components/ChannelDetail.vue'

// --- Task type label map ---
const typeLabelMap = {
  nurture: '养号',
  search_comment: '搜索评论',
  search_like: '搜索点赞',
  search_dm: '搜索私信',
  reply_comment: '评论回复',
}

const taskTypeOptions = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
]

const statusFilterOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

// --- Data state ---
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')

// --- Accounts for create form ---
const accounts = ref([])

// --- Groups for batch create ---
const groups = ref([])
const selectionMode = ref('single') // 'single' | 'group'
const selectedGroupIds = ref([])

// --- Devices for create form ---
const devices = ref([])

// --- Templates for create form ---
const templates = ref([])
const selectedTemplateId = ref('')

// --- Create dialog state ---
const showCreateDialog = ref(false)
const creating = ref(false)
const createError = ref(null)

const defaultForm = {
  type: 'nurture',
  account_id: '',
  device_id: '',
  keyword: '',
  content: '',
  count: 5,
  video_count: 3,
  sort_by: '',
  max_age_days: 5,
  duration: 30,
}
const form = reactive({ ...defaultForm })

// --- Nurture V2 state ---
const nurtureMode = ref('simple') // 'simple' or 'advanced'
const subTasks = ref([{ type: 'browse', count: 10, content_template_id: '' }])
const completionMode = ref('all')
const maxDuration = ref(60)
const nurtureKeywords = ref('')
const nurtureKeywordMatrix = ref([])
const nurtureKeywordGenerating = ref(false)

const subTaskTypeOptions = [
  { value: 'browse', label: '浏览' },
  { value: 'watch', label: '观看' },
  { value: 'like', label: '点赞' },
  { value: 'comment', label: '评论' },
  { value: 'follow', label: '关注' },
]

function addSubTask() {
  subTasks.value.push({ type: 'browse', count: 5, content_template_id: '' })
}

function removeSubTask(index) {
  if (subTasks.value.length <= 1) return // Keep at least one subtask
  subTasks.value.splice(index, 1)
}

// --- Keyword search dialog state ---
const showKeywordDialog = ref(false)
const keywordSeed = ref('')
const keywordList = ref([])
const keywordGenerating = ref(false)
const keywordError = ref(null)
const keywordActionType = ref('search_comment')
const keywordSelectionMode = ref('single')
const keywordSelectedGroupIds = ref([])
const keywordSingleAccountId = ref('')
const keywordDeviceId = ref('')
const keywordSortBy = ref('')
const keywordTemplateId = ref('')
const keywordContent = ref('')
const keywordMaxAgeDays = ref(5)
const keywordGenerateCount = ref(10)
const keywordProcessingCount = ref(5)
const keywordExpandCount = ref(8)

// --- Cancel confirmation state ---
const showCancelDialog = ref(false)
const cancellingTask = ref(null)
const cancelling = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Tab switching ---
const activeTab = ref('tasks') // 'tasks' | 'channels'

// --- Channel state ---
const channels = ref([])
const channelsLoading = ref(false)
const detailChannel = ref(null)

const channelTaskTypeLabel = (type) => ({
  search_comment: '评论搜索',
  search_like: '点赞搜索',
  search_dm: '私信搜索',
  reply_comment: '回复评论',
  nurture: '养号',
}[type] || type)

const channelStatusLabel = (s) => ({
  active: '运行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
}[s] || s)

const channelStatusClass = (s) => ({
  active: 'bg-green-500/20 text-green-400',
  paused: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-blue-500/20 text-blue-400',
  cancelled: 'bg-slate-600/50 text-slate-400',
}[s] || 'bg-slate-600/50 text-slate-400')

const toast = useToastStore()

// --- Table columns ---
const columns = [
  { key: 'type', label: '任务类型' },
  { key: 'account_id', label: '账号ID' },
  { key: 'device_id', label: '执行设备' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch tasks ---
async function fetchTasks() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const params = { skip, limit: pageSize }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await listTasks(params)
    tasks.value = res.data.tasks || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载任务列表失败')
    tasks.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// --- Fetch channels ---
async function fetchChannels() {
  channelsLoading.value = true
  try {
    const resp = await listChannels()
    channels.value = resp.data.channels || []
  } catch (e) {
    console.error('Failed to fetch channels:', e)
  } finally {
    channelsLoading.value = false
  }
}

async function pauseChannel(ch) {
  await updateChannel(ch.id, { status: 'paused' })
  await fetchChannels()
}

async function resumeChannel(ch) {
  await updateChannel(ch.id, { status: 'active' })
  await fetchChannels()
}

async function cancelChannel(ch) {
  if (!confirm('确定取消此通道？')) return
  await updateChannel(ch.id, { status: 'cancelled' })
  await fetchChannels()
}

async function deleteChannel(ch) {
  if (!confirm('确定删除此通道？')) return
  await deleteChannelApi(ch.id)
  await fetchChannels()
}

function openChannelDetail(ch) {
  detailChannel.value = ch
}

// --- Fetch accounts for create form ---
async function fetchAccounts() {
  try {
    const res = await listAccounts({ limit: 100 })
    accounts.value = res.data.accounts || []
  } catch (e) {
    toast.error('加载账号列表失败')
    accounts.value = []
  }
}

// --- Fetch groups for batch create ---
async function fetchGroups() {
  try {
    const res = await listGroups({ limit: 100 })
    groups.value = res.data.groups || res.data || []
  } catch { /* ignore */ }
}

// --- Fetch devices for create form ---
async function fetchDevices() {
  try {
    const res = await listDevices({ limit: 100 })
    devices.value = res.data.devices || []
  } catch (e) {
    toast.error('加载设备列表失败')
    devices.value = []
  }
}

// --- Filtered devices: show devices bound to selected account, plus unbound devices ---
const filteredDevices = computed(() => {
  if (!form.account_id) return devices.value
  return devices.value.filter(
    d => !d.bound_account_id || d.bound_account_id === form.account_id
  )
})

// --- Fetch templates for create form ---
async function fetchTemplates() {
  try {
    const res = await listTemplates({ limit: 100 })
    templates.value = res.data.templates || []
  } catch (e) {
    toast.error('加载模板列表失败')
    templates.value = []
  }
}

// --- Filtered templates (exclude for nurture tasks) ---
const filteredTemplates = computed(() => {
  if (form.type === 'nurture') return []
  return templates.value
})

// --- Watch status filter: reset page and re-fetch ---
watch(statusFilter, () => {
  page.value = 1
  fetchTasks()
})

// --- Watch task type: reset template when switching to nurture ---
watch(() => form.type, (newType) => {
  if (newType === 'nurture') {
    selectedTemplateId.value = ''
  }
})

// --- Page change ---
function handlePageChange(p) {
  page.value = p
  fetchTasks()
}

// --- Open create dialog ---
function openCreateDialog() {
  Object.assign(form, defaultForm)
  selectedTemplateId.value = ''
  selectionMode.value = 'single'
  selectedGroupIds.value = []
  createError.value = null
  nurtureKeywords.value = ''
  nurtureKeywordMatrix.value = []
  showCreateDialog.value = true
}

// --- Computed: is search-type task ---
const isSearchType = computed(() => ['search_comment', 'search_like', 'search_dm', 'reply_comment'].includes(form.type))

// --- Watch account change: reset device when account changes ---
watch(() => form.account_id, () => {
  form.device_id = ''
})

// --- Build params from form ---
function buildParams() {
  if (form.type === 'nurture') {
    if (nurtureMode.value === 'advanced') {
      if (subTasks.value.length === 0) {
        throw new Error('高级模式下至少需要一个子任务')
      }
      const params = {
        sub_tasks: subTasks.value.map(st => ({
          type: st.type,
          count: st.count,
          ...(st.type === 'comment' && st.content_template_id ? { content_template_id: st.content_template_id } : {}),
        })),
        completion_mode: completionMode.value,
        duration: maxDuration.value,
      }
      // Include keywords if provided
      const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
      if (seeds.length > 0) {
        params.keywords = seeds
      }
      return params
    }
    return {
      duration: form.duration,
    }
  }

  const params = {
    keyword: form.keyword,
    count: form.count,
  }

  if (form.sort_by) {
    params.sort_by = form.sort_by
  }

  // Content tasks
  if (['search_comment', 'search_dm', 'reply_comment'].includes(form.type)) {
    if (form.content) {
      params.content = form.content
    }
    if (selectedTemplateId.value) {
      params.content_template_id = selectedTemplateId.value
    }
  }

  // Reply comment specific
  if (form.type === 'reply_comment') {
    params.video_count = form.video_count
    params.max_age_days = form.max_age_days
  }

  return params
}

// --- Handle create ---
async function handleCreate() {
  if (!form.type) {
    createError.value = '请选择任务类型'
    return
  }
  if (selectionMode.value === 'single' && !form.account_id) {
    createError.value = '请选择账号'
    return
  }
  if (selectionMode.value === 'group' && selectedGroupIds.value.length === 0) {
    createError.value = '请至少选择一个分组'
    return
  }
  if (isSearchType.value && !form.keyword) {
    createError.value = '请输入搜索关键词'
    return
  }

  creating.value = true
  createError.value = null

  try {
    const params = buildParams()

    if (selectionMode.value === 'group') {
      // Batch create via groups
      const payload = {
        type: form.type,
        group_ids: selectedGroupIds.value,
        params,
      }
      if (form.device_id) {
        payload.device_id = form.device_id
      }
      const res = await batchCreateTasks(payload)
      const count = res.data?.created || 0
      toast.success(`批量创建成功：${count} 个任务`)
    } else {
      // Single account create
      const payload = {
        type: form.type,
        account_id: form.account_id,
        params,
      }
      if (form.device_id) {
        payload.device_id = form.device_id
      }
      await createTask(payload)
    }

    showCreateDialog.value = false
    page.value = 1
    fetchTasks()
  } catch (e) {
    createError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

// --- Cancel task ---
function openCancelDialog(task) {
  cancellingTask.value = task
  showCancelDialog.value = true
}

async function handleCancel() {
  if (!cancellingTask.value) return
  cancelling.value = true
  try {
    await cancelTask(cancellingTask.value.id)
    showCancelDialog.value = false
    cancellingTask.value = null
    fetchTasks()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '取消失败，请重试'
  } finally {
    cancelling.value = false
  }
}

// --- Nurture keyword expansion ---
async function expandNurtureKeywords() {
  const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
  if (seeds.length === 0) return
  nurtureKeywordGenerating.value = true
  try {
    const allExpanded = []
    for (const seed of seeds) {
      const res = await generateKeywords(seed, 8)
      allExpanded.push(...(res.data.keywords || []))
    }
    // Deduplicate
    nurtureKeywordMatrix.value = [...new Set(allExpanded)]
    toast.success(`已扩展 ${nurtureKeywordMatrix.value.length} 个关键词`)
  } catch (e) {
    toast.error('关键词扩展失败，请重试')
  } finally {
    nurtureKeywordGenerating.value = false
  }
}

// --- Keyword search ---
function openKeywordDialog() {
  keywordSeed.value = ''
  keywordList.value = []
  keywordError.value = null
  keywordActionType.value = 'search_comment'
  keywordSelectionMode.value = 'single'
  keywordSelectedGroupIds.value = []
  keywordSingleAccountId.value = ''
  keywordDeviceId.value = ''
  keywordSortBy.value = ''
  keywordTemplateId.value = ''
  keywordContent.value = ''
  keywordMaxAgeDays.value = 5
  keywordGenerateCount.value = 10
  keywordProcessingCount.value = 5
  showKeywordDialog.value = true
}

async function handleGenerateKeywords() {
  if (!keywordSeed.value.trim()) {
    keywordError.value = '请输入种子关键词'
    return
  }
  keywordGenerating.value = true
  keywordError.value = null
  try {
    const res = await generateKeywords(keywordSeed.value.trim(), keywordGenerateCount.value)
    const expanded = res.data.keywords || []
    // 种子词排在第一位，AI 扩展词追加，去重
    const seen = new Set([keywordSeed.value.trim()])
    const merged = [keywordSeed.value.trim()]
    for (const kw of expanded) {
      if (!seen.has(kw)) {
        seen.add(kw)
        merged.push(kw)
      }
    }
    keywordList.value = merged
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '生成失败，请重试'
  } finally {
    keywordGenerating.value = false
  }
}

function removeKeyword(idx) {
  keywordList.value.splice(idx, 1)
}

async function expandCreateKeyword() {
  var seed = form.keyword.trim()
  if (!seed) return
  keywordGenerating.value = true
  try {
    // 处理逗号分隔的多个种子词
    var seeds = seed.split(/[,，]/).map(function (s) { return s.trim() }).filter(Boolean)
    var allExpanded = []
    for (var i = 0; i < seeds.length; i++) {
      var res = await generateKeywords(seeds[i], keywordExpandCount.value)
      allExpanded.push.apply(allExpanded, res.data.keywords || [])
    }
    // 种子词排前面，AI 扩展词去重追加
    var seen = {}
    var merged = []
    for (var s = 0; s < seeds.length; s++) {
      if (!seen[seeds[s]]) { seen[seeds[s]] = true; merged.push(seeds[s]) }
    }
    for (var j = 0; j < allExpanded.length; j++) {
      if (!seen[allExpanded[j]]) { seen[allExpanded[j]] = true; merged.push(allExpanded[j]) }
    }
    form.keyword = merged.join('，')
  } catch (e) {
    toast.error('关键词扩展失败')
  } finally {
    keywordGenerating.value = false
  }
}

function buildKeywordParams(kw) {
  const params = { keyword: kw, count: keywordProcessingCount.value }
  if (keywordSortBy.value) params.sort_by = keywordSortBy.value
  if (keywordMaxAgeDays.value) params.max_age_days = keywordMaxAgeDays.value
  if (keywordTemplateId.value) {
    params.content_template_id = keywordTemplateId.value
  } else if (keywordContent.value) {
    params.content = keywordContent.value
  }
  return params
}

async function handleBatchCreateKeywordTasks() {
  if (keywordList.value.length === 0) {
    keywordError.value = '请先生成关键词'
    return
  }
  if (keywordSelectionMode.value === 'single' && !keywordSingleAccountId.value) {
    keywordError.value = '请选择账号'
    return
  }
  if (keywordSelectionMode.value === 'group' && keywordSelectedGroupIds.value.length === 0) {
    keywordError.value = '请至少选择一个分组'
    return
  }

  creating.value = true
  keywordError.value = null

  try {
    if (keywordSelectionMode.value === 'group') {
      var kwList = keywordList.value.map(function (k) { return typeof k === 'string' ? k.trim() : k }).filter(Boolean)
      const params = {
        keyword: kwList[0] || '',
        keywords: kwList,
        count: keywordProcessingCount.value,
      }
      if (keywordSortBy.value) params.sort_by = keywordSortBy.value
      if (keywordMaxAgeDays.value) params.max_age_days = keywordMaxAgeDays.value
      if (keywordTemplateId.value) {
        params.content_template_id = keywordTemplateId.value
      } else if (keywordContent.value) {
        params.content = keywordContent.value
      }
      const resp = await batchCreateTasks({
        type: keywordActionType.value,
        group_ids: keywordSelectedGroupIds.value,
        params: params,
        ...(keywordDeviceId.value ? { device_id: keywordDeviceId.value } : {}),
      })
      const created = resp.data?.created || 0
      const mode = resp.data?.mode || ''
      toast.success(mode === 'channel'
        ? ('通道已创建，' + created + ' 个关键词任务将自动分发')
        : ('成功创建 ' + created + ' 个任务'))
    } else {
      var successCount = 0
      for (var i = 0; i < keywordList.value.length; i++) {
        var kw = typeof keywordList.value[i] === 'string' ? keywordList.value[i].trim() : keywordList.value[i]
        if (!kw) continue
        var params = { keyword: kw, count: keywordProcessingCount.value }
        if (keywordSortBy.value) params.sort_by = keywordSortBy.value
        if (keywordMaxAgeDays.value) params.max_age_days = keywordMaxAgeDays.value
        if (keywordTemplateId.value) {
          params.content_template_id = keywordTemplateId.value
        } else if (keywordContent.value) {
          params.content = keywordContent.value
        }
        await createTask({
          type: keywordActionType.value,
          account_id: keywordSingleAccountId.value,
          params: params,
          ...(keywordDeviceId.value ? { device_id: keywordDeviceId.value } : {}),
        })
        successCount++
      }
      toast.success('成功创建 ' + successCount + ' 个任务')
    }
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '创建失败'
  }

  creating.value = false
  showKeywordDialog.value = false
  page.value = 1
  fetchTasks()
}
// --- Init ---
onMounted(() => {
  fetchTasks()
  fetchChannels()
  fetchAccounts()
  fetchGroups()
  fetchDevices()
  fetchTemplates()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Tab bar -->
    <div class="flex items-center gap-1 mb-6 bg-slate-800/50 rounded-xl p-1 w-fit">
      <button
        @click="activeTab = 'tasks'"
        class="px-4 py-2 text-sm font-medium rounded-lg transition-all"
        :class="activeTab === 'tasks' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'"
      >任务管理</button>
      <button
        @click="activeTab = 'channels'; fetchChannels()"
        class="px-4 py-2 text-sm font-medium rounded-lg transition-all"
        :class="activeTab === 'channels' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-white'"
      >任务通道</button>
    </div>

    <!-- ==================== 任务管理 Tab ==================== -->
    <div v-if="activeTab === 'tasks'">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">任务管理</h1>
      <div class="flex items-center gap-3">
        <!-- Status filter -->
        <select
          v-model="statusFilter"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
        >
          <option
            v-for="opt in statusFilterOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
        <!-- Keyword search button -->
        <button
          class="inline-flex items-center px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-xl hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-lg shadow-emerald-500/25"
          @click="openKeywordDialog"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          关键词搜索
        </button>
        <!-- Create single task -->
        <button
          class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
          @click="openCreateDialog"
        >
          <svg class="-ml-1 mr-2 h-5 w-5 relative z-10" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/>
          </svg>
          <span class="relative z-10">创建任务</span>
        </button>
      </div>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="tasks"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <!-- Type column -->
      <template #cell-type="{ value }">
        {{ typeLabelMap[value] || value }}
      </template>

      <!-- Account column -->
      <template #cell-account_id="{ value }">
        <span class="text-slate-300">
          {{ accounts.find(a => a.id === value)?.nickname || value }}
        </span>
      </template>

      <!-- Device column -->
      <template #cell-device_id="{ value }">
        <span v-if="value" class="text-slate-300">
          {{ devices.find(d => d.id === value)?.name || value }}
        </span>
        <span v-else class="text-slate-500">自动分配</span>
      </template>

      <!-- Status column -->
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <!-- Created at column -->
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            v-if="row.status === 'pending' || row.status === 'running'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
            @click="openCancelDialog(row)"
          >
            取消
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create Task Dialog -->
    <TransitionRoot :show="showCreateDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showCreateDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="glass-card w-full max-w-lg p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  创建任务
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="createError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ createError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                  <!-- Task Type -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">
                      任务类型 <TipIcon text="选择要执行的任务类型。养号=模拟真实用户行为提升权重；搜索评论/点赞/私信=按关键词搜索视频后自动操作；评论回复=回复已有评论引流" /> <span class="text-red-400">*</span>
                    </label>
                    <select
                      v-model="form.type"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option v-for="opt in taskTypeOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                  </div>

                  <!-- Account selection mode -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">
                      选择方式 <TipIcon text="单账号=为一个账号创建任务；按分组=为分组内所有活跃账号批量创建任务" />
                    </label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="selectionMode" value="single" class="text-purple-500 focus:ring-purple-500" />
                        <span class="text-sm text-slate-300">单账号</span>
                      </label>
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="selectionMode" value="group" class="text-purple-500 focus:ring-purple-500" />
                        <span class="text-sm text-slate-300">按分组批量</span>
                      </label>
                    </div>
                  </div>

                  <!-- Account (single mode) -->
                  <div v-if="selectionMode === 'single'">
                    <label class="block text-sm font-medium text-slate-300">
                      账号 <TipIcon text="选择执行此任务的抖音账号" /> <span class="text-red-400">*</span>
                    </label>
                    <select
                      v-model="form.account_id"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option value="" disabled>请选择账号</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Groups (batch mode) -->
                  <div v-if="selectionMode === 'group'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">
                      选择分组 <TipIcon text="选中的分组内所有活跃账号都会创建相同任务" /> <span class="text-red-400">*</span>
                    </label>
                    <div class="max-h-40 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                      <label
                        v-for="grp in groups"
                        :key="grp.id"
                        class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          :value="grp.id"
                          v-model="selectedGroupIds"
                          class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500"
                        />
                        <span class="text-sm text-slate-300">
                          {{ grp.name }}
                          <span class="text-slate-500">({{ grp.member_count || 0 }} 个账号)</span>
                        </span>
                      </label>
                      <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组，请先创建账号分组</p>
                    </div>
                  </div>

                  <!-- Device -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">
                      执行设备 <TipIcon text="选择运行任务的设备。留空则自动分配给该账号绑定的在线设备" />
                    </label>
                    <select
                      v-model="form.device_id"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option value="">自动分配（绑定设备领取）</option>
                      <option v-for="dev in filteredDevices" :key="dev.id" :value="dev.id">
                        {{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}
                      </option>
                    </select>
                  </div>

                  <!-- 养号参数 -->
                  <template v-if="form.type === 'nurture'">
                    <div>
                      <label class="block text-sm font-medium text-slate-300 mb-2">养号模式 <TipIcon text="简单模式=设定总时长，系统自动随机操作；高级模式=自定义多个子任务按顺序执行" width="w-80" /></label>
                      <div class="flex gap-4">
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input type="radio" v-model="nurtureMode" value="simple" class="text-purple-500 focus:ring-purple-500" />
                          <span class="text-sm text-slate-300">简单模式</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input type="radio" v-model="nurtureMode" value="advanced" class="text-purple-500 focus:ring-purple-500" />
                          <span class="text-sm text-slate-300">高级模式（子任务）</span>
                        </label>
                      </div>
                    </div>

                    <!-- 简单模式 -->
                    <div v-if="nurtureMode === 'simple'">
                      <label class="block text-sm font-medium text-slate-300">养号时长（分钟） <TipIcon text="简单模式下养号操作的总持续时间，建议 15-60 分钟" /></label>
                      <input
                        v-model.number="form.duration"
                        type="number"
                        min="1"
                        max="120"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      />
                    </div>

                    <!-- 高级模式 -->
                    <div v-else class="space-y-3">
                      <div>
                        <label class="block text-sm font-medium text-slate-300 mb-1">子任务列表 <TipIcon text="按顺序配置多个操作步骤。每个子任务指定类型和执行次数" /></label>
                        <p class="mt-1 text-xs text-slate-500">浏览/观看=刷视频，点赞/评论/关注=互动操作</p>
                        <div class="space-y-2">
                          <div v-for="(st, idx) in subTasks" :key="idx" class="flex items-center gap-2">
                            <select v-model="st.type" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                              <option v-for="opt in subTaskTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                            </select>
                            <input v-model.number="st.count" type="number" min="1" max="100" class="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" placeholder="次数" />
                            <select v-if="st.type === 'comment'" v-model="st.content_template_id" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                              <option value="">选择模板</option>
                              <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }}</option>
                            </select>
                            <button type="button" @click="removeSubTask(idx)" class="text-red-400 hover:text-red-300">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                          </div>
                        </div>
                        <button type="button" @click="addSubTask" class="mt-2 text-sm text-cyan-400 hover:text-cyan-300">+ 添加子任务</button>
                      </div>
                      <div class="grid grid-cols-2 gap-3">
                        <div>
                          <label class="block text-sm font-medium text-slate-300">完成模式 <TipIcon text="全部完成=所有子任务都必须完成才算成功；任一完成=任意一个子任务完成即可" /></label>
                          <select v-model="completionMode" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                            <option value="all">全部完成</option>
                            <option value="any">任一完成</option>
                          </select>
                        </div>
                        <div>
                          <label class="block text-sm font-medium text-slate-300">最大时长（分钟） <TipIcon text="高级模式下整个养号任务的最大执行时间，超时自动停止" /></label>
                          <input v-model.number="maxDuration" type="number" min="1" max="240" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                        </div>
                      </div>
                    </div>

                    <!-- 关键词过滤（可选） -->
                    <div>
                      <label class="block text-sm font-medium text-slate-300 mb-1">
                        关键词过滤 <TipIcon text="输入种子关键词，AI 扩展为关键词矩阵。养号时只对匹配关键词的内容进行点赞/评论/关注，不匹配的内容直接跳过。留空则不限制" />
                      </label>
                      <div class="flex gap-2">
                        <input
                          v-model="nurtureKeywords"
                          type="text"
                          class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                          placeholder="输入种子关键词，逗号分隔，如：养生,中医,食疗"
                        />
                        <button
                          type="button"
                          @click="expandNurtureKeywords"
                          :disabled="nurtureKeywordGenerating || !nurtureKeywords.trim()"
                          class="px-3 py-2 rounded-lg text-sm font-medium bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-50"
                        >
                          {{ nurtureKeywordGenerating ? '扩展中...' : 'AI 扩展' }}
                        </button>
                      </div>
                      <div v-if="nurtureKeywordMatrix.length > 0" class="mt-2 flex flex-wrap gap-1.5">
                        <span v-for="(kw, idx) in nurtureKeywordMatrix" :key="idx"
                          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-500/20 text-purple-300">
                          {{ kw }}
                          <button type="button" @click="nurtureKeywordMatrix.splice(idx, 1)" class="hover:text-purple-100">&times;</button>
                        </span>
                      </div>
                    </div>
                  </template>

                  <!-- 搜索类参数 -->
                  <template v-if="isSearchType">
                    <div>
                      <label class="block text-sm font-medium text-slate-300">
                        搜索关键词 <TipIcon text="输入种子词，点击 AI 扩展自动生成相关关键词" /> <span class="text-red-400">*</span>
                      </label>
                      <div class="flex gap-2 mt-1">
                        <input
                          v-model="form.keyword"
                          type="text"
                          maxlength="200"
                          class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                          placeholder="例：美食、养生"
                        />
                        <input
                          v-model.number="keywordExpandCount"
                          type="number"
                          min="3"
                          max="30"
                          class="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200 text-center"
                          title="扩展数量"
                        />
                        <button
                          type="button"
                          @click="expandCreateKeyword"
                          :disabled="keywordGenerating"
                          class="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors whitespace-nowrap"
                        >
                          {{ keywordGenerating ? '...' : 'AI 扩展' }}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-slate-300">排序方式 <TipIcon text="控制搜索结果排序，影响目标视频选择优先级" /></label>
                      <select
                        v-model="form.sort_by"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      >
                        <option value="">默认排序</option>
                        <option value="latest">最新发布</option>
                        <option value="most_liked">最多点赞</option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-slate-300">
                        {{ form.type === 'reply_comment' ? '每视频评论数' : '处理数量' }} <TipIcon text="每个搜索结果中要处理的数量" />
                      </label>
                      <input
                        v-model.number="form.count"
                        type="number"
                        min="1"
                        :max="form.type === 'search_like' ? 30 : 20"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      />
                    </div>
                  </template>

                  <!-- 评论回复特有参数 -->
                  <template v-if="form.type === 'reply_comment'">
                    <div>
                      <label class="block text-sm font-medium text-slate-300">处理视频数 <TipIcon text="要处理的视频数量，每个视频下最多操作指定条数" /></label>
                      <input
                        v-model.number="form.video_count"
                        type="number"
                        min="1"
                        max="10"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-slate-300">评论最大天数 <TipIcon text="只回复在此天数内发布的评论，超过的将被忽略" /></label>
                      <input
                        v-model.number="form.max_age_days"
                        type="number"
                        min="1"
                        max="30"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      />
                    </div>
                  </template>

                  <!-- 内容类任务的私信/评论内容 -->
                  <template v-if="['search_comment', 'search_dm', 'reply_comment'].includes(form.type)">
                    <!-- Template -->
                    <div v-if="filteredTemplates.length > 0">
                      <label class="block text-sm font-medium text-slate-300">内容模板 <TipIcon text="选择预设的评论/私信模板，模板中的变量会自动替换为实际值" /></label>
                      <select
                        v-model="selectedTemplateId"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      >
                        <option value="">不使用模板</option>
                        <option v-for="tpl in filteredTemplates" :key="tpl.id" :value="tpl.id">
                          {{ tpl.name }} ({{ tpl.category }})
                        </option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-slate-300">
                        {{ form.type === 'search_dm' ? '私信内容' : '评论/私信内容' }} <TipIcon text="发送的内容文本。支持 {keyword}、{username}、{video_title} 变量。留空则使用模板或 AI 生成" width="w-80" />
                      </label>
                      <textarea
                        v-model="form.content"
                        rows="3"
                        maxlength="500"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                        :placeholder="form.type === 'reply_comment' ? '留空则使用 AI 生成招呼语' : '输入内容...'"
                      />
                    </div>
                  </template>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showCreateDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="creating"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ creating ? '创建中...' : '创建' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Cancel Confirmation Dialog -->
    <ConfirmDialog
      :open="showCancelDialog"
      title="取消任务"
      :message="`确定要取消该任务吗？`"
      confirm-text="取消任务"
      :danger="true"
      @confirm="handleCancel"
      @cancel="showCancelDialog = false"
    />

    <!-- Keyword Search Dialog -->
    <TransitionRoot :show="showKeywordDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showKeywordDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="glass-card w-full max-w-xl p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">关键词搜索</DialogTitle>

                <div v-if="keywordError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ keywordError }}
                </div>

                <div class="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
                  <!-- Seed keyword input -->
                  <div class="flex gap-2 items-end">
                    <div class="flex-1">
                      <label class="block text-sm font-medium text-slate-300 mb-1">种子关键词 <TipIcon text="输入一个基础关键词，AI 会自动扩展出多个相关搜索词" /></label>
                      <input
                        v-model="keywordSeed"
                        type="text"
                        maxlength="50"
                        class="block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                        placeholder="输入种子关键词，如：美食"
                        @keyup.enter="handleGenerateKeywords"
                      />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-slate-300 mb-1">生成数量</label>
                      <input v-model.number="keywordGenerateCount" type="number" min="1" max="30" class="w-20 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                    </div>
                    <button
                      type="button"
                      :disabled="keywordGenerating"
                      class="px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25"
                      @click="handleGenerateKeywords"
                    >
                      {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
                    </button>
                  </div>

                  <!-- Generated keywords -->
                  <div v-if="keywordList.length > 0">
                    <label class="block text-sm font-medium text-slate-300 mb-1">关键词矩阵 <TipIcon text="AI 生成的关键词列表，点击 X 可删除不需要的，最终保留的将各创建一个任务" /></label>
                    <div class="flex flex-wrap gap-2 p-3 border border-white/10 rounded-lg max-h-32 overflow-y-auto">
                      <span
                        v-for="(kw, idx) in keywordList"
                        :key="idx"
                        class="inline-flex items-center gap-1 px-2.5 py-1 bg-purple-500/15 text-purple-300 text-sm rounded-full border border-purple-500/25"
                      >
                        {{ kw }}
                        <button type="button" @click="removeKeyword(idx)" class="text-purple-400 hover:text-purple-300">
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                      </span>
                    </div>
                  </div>

                  <!-- Action type + Processing count -->
                  <div class="grid grid-cols-2 gap-3">
                    <div>
                      <label class="block text-sm font-medium text-slate-300">操作类型 <TipIcon text="批量创建任务时使用的操作类型" /></label>
                      <select v-model="keywordActionType" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                        <option value="search_comment">搜索评论</option>
                        <option value="search_like">搜索点赞</option>
                        <option value="search_dm">搜索私信</option>
                        <option value="reply_comment">评论回复</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-slate-300">每关键词处理数 <TipIcon text="每个关键词搜索结果中要处理的视频数量" /></label>
                      <input v-model.number="keywordProcessingCount" type="number" min="1" max="30" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                    </div>
                  </div>

                  <!-- Selection mode -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">选择方式</label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="keywordSelectionMode" value="single" class="text-purple-500 focus:ring-purple-500" />
                        <span class="text-sm text-slate-300">单账号</span>
                      </label>
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="keywordSelectionMode" value="group" class="text-purple-500 focus:ring-purple-500" />
                        <span class="text-sm text-slate-300">按分组批量</span>
                      </label>
                    </div>
                  </div>

                  <!-- Account (single mode) -->
                  <div v-if="keywordSelectionMode === 'single'">
                    <label class="block text-sm font-medium text-slate-300">选择账号 <span class="text-red-400">*</span></label>
                    <select v-model="keywordSingleAccountId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="" disabled>请选择账号</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Groups (batch mode) -->
                  <div v-if="keywordSelectionMode === 'group'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">选择分组 <span class="text-red-400">*</span></label>
                    <div class="max-h-32 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                      <label
                        v-for="grp in groups"
                        :key="grp.id"
                        class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer"
                      >
                        <input type="checkbox" :value="grp.id" v-model="keywordSelectedGroupIds" class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500" />
                        <span class="text-sm text-slate-300">{{ grp.name }} <span class="text-slate-500">({{ grp.member_count || 0 }})</span></span>
                      </label>
                      <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组</p>
                    </div>
                  </div>

                  <!-- Sort by -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">排序方式</label>
                    <select v-model="keywordSortBy" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">默认排序</option>
                      <option value="latest">最新发布</option>
                      <option value="most_liked">最多点赞</option>
                    </select>
                  </div>

                  <!-- max_age_days (for comment task types) -->
                  <div v-if="['search_comment', 'reply_comment'].includes(keywordActionType)">
                    <label class="block text-sm font-medium text-slate-300">评论最大天数 <TipIcon text="只回复在此天数内发布的评论，超过的将被忽略" /></label>
                    <input
                      v-model.number="keywordMaxAgeDays"
                      type="number"
                      min="1"
                      max="30"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>

                  <!-- Content template / content (for content task types) -->
                  <template v-if="['search_comment', 'search_dm', 'reply_comment'].includes(keywordActionType)">
                    <div v-if="templates.length > 0">
                      <label class="block text-sm font-medium text-slate-300">内容模板</label>
                      <select v-model="keywordTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                        <option value="">不使用模板</option>
                        <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.category }})</option>
                      </select>
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-slate-300">评论/私信内容 <TipIcon text="留空则使用模板或 AI 生成" /></label>
                      <textarea
                        v-model="keywordContent"
                        rows="2"
                        maxlength="500"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                        placeholder="输入内容...（留空用模板）"
                      />
                    </div>
                  </template>

                  <!-- Device -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">执行设备</label>
                    <select v-model="keywordDeviceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">自动分配</option>
                      <option v-for="dev in devices" :key="dev.id" :value="dev.id">
                        {{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}
                      </option>
                    </select>
                  </div>
                </div>

                <div class="flex justify-end gap-3 pt-4">
                  <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showKeywordDialog = false">取消</button>
                  <button
                    type="button"
                    :disabled="creating || keywordList.length === 0"
                    class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    @click="handleBatchCreateKeywordTasks"
                  >
                    <span class="relative z-10">{{ creating ? '创建中...' : `批量创建 ${keywordList.length} 个任务` }}</span>
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
    </div>
    <!-- ==================== End 任务管理 Tab ==================== -->

    <!-- ==================== 任务通道 Tab ==================== -->
    <div v-if="activeTab === 'channels'">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-white">任务通道</h2>
        <span class="text-sm text-slate-400">通过关键词搜索批量创建任务时自动生成</span>
      </div>

      <!-- Channel cards -->
      <div v-if="channelsLoading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="channels.length === 0" class="text-center py-12 text-slate-400">
        暂无通道，点击上方按钮创建
      </div>
      <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="ch in channels"
          :key="ch.id"
          class="bg-slate-800/50 backdrop-blur rounded-lg shadow p-4 border border-slate-700 hover:border-slate-500 transition-all cursor-pointer"
          @click="openChannelDetail(ch)"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-white">
              {{ ch.group_name }} · {{ channelTaskTypeLabel(ch.task_type) }}
            </span>
            <span :class="channelStatusClass(ch.status)" class="px-2 py-0.5 text-xs rounded-full">
              {{ channelStatusLabel(ch.status) }}
            </span>
          </div>
          <div class="mb-2">
            <div class="flex justify-between text-xs text-slate-400 mb-1">
              <span>{{ ch.completed }}/{{ ch.total }} 完成</span>
              <span>{{ ch.pending }} 待处理</span>
            </div>
            <div class="w-full bg-slate-700 rounded-full h-2">
              <div
                class="bg-green-500 h-2 rounded-full transition-all"
                :style="{ width: ch.total ? (ch.completed / ch.total * 100) + '%' : '0%' }"
              />
            </div>
          </div>
          <div class="flex items-center justify-between text-xs text-slate-500">
            <span>{{ ch.account_mode === 'single_account' ? '单账号' : '轮转' }}</span>
            <span>{{ ch.assigned }} 执行中</span>
          </div>
          <div class="flex gap-2 mt-3">
            <button
              v-if="ch.status === 'active'"
              @click.stop="pauseChannel(ch)"
              class="px-3 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 transition-colors"
            >暂停</button>
            <button
              v-if="ch.status === 'paused'"
              @click.stop="resumeChannel(ch)"
              class="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors"
            >恢复</button>
            <button
              v-if="ch.status !== 'cancelled' && ch.status !== 'completed'"
              @click.stop="cancelChannel(ch)"
              class="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
            >取消</button>
            <button
              @click.stop="deleteChannel(ch)"
              class="px-3 py-1 text-xs bg-slate-600/50 text-slate-300 rounded hover:bg-slate-600 transition-colors"
            >删除</button>
          </div>
        </div>
      </div>

      <!-- Channel detail dialog -->
      <ChannelDetail
        v-if="detailChannel"
        :channel="detailChannel"
        @close="detailChannel = null"
        @refresh="fetchChannels"
      />
    </div>
    <!-- ==================== End 任务通道 Tab ==================== -->
  </div>
</template>
