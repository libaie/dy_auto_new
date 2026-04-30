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
import { listTasks, createTask, cancelTask } from '../api/tasks.js'
import { listAccounts } from '../api/accounts.js'
import { listDevices } from '../api/devices.js'
import { listTemplates, generateKeywords } from '../api/content.js'
import { formatDate } from '../utils/format.js'

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
  subTasks.value.splice(index, 1)
}

// --- Keyword search dialog state ---
const showKeywordDialog = ref(false)
const keywordSeed = ref('')
const keywordList = ref([])
const keywordGenerating = ref(false)
const keywordError = ref(null)
const keywordActionType = ref('search_comment')
const keywordAccountId = ref('')
const keywordCount = ref(10)

// --- Cancel confirmation state ---
const showCancelDialog = ref(false)
const cancellingTask = ref(null)
const cancelling = ref(false)

// --- Page-level error ---
const pageError = ref(null)

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
    console.error('Failed to fetch tasks:', e)
    tasks.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// --- Fetch accounts for create form ---
async function fetchAccounts() {
  try {
    const res = await listAccounts({ limit: 100 })
    accounts.value = res.data.accounts || []
  } catch (e) {
    console.error('Failed to fetch accounts:', e)
    accounts.value = []
  }
}

// --- Fetch devices for create form ---
async function fetchDevices() {
  try {
    const res = await listDevices({ limit: 100 })
    devices.value = res.data.devices || []
  } catch (e) {
    console.error('Failed to fetch devices:', e)
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
    console.error('Failed to fetch templates:', e)
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
  createError.value = null
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
    if (nurtureMode.value === 'advanced' && subTasks.value.length > 0) {
      return {
        sub_tasks: subTasks.value.map(st => ({
          type: st.type,
          count: st.count,
          ...(st.type === 'comment' && st.content_template_id ? { content_template_id: st.content_template_id } : {}),
        })),
        completion_mode: completionMode.value,
        duration: maxDuration.value,
      }
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
  if (!form.account_id) {
    createError.value = '请选择账号'
    return
  }
  if (isSearchType.value && !form.keyword) {
    createError.value = '请输入搜索关键词'
    return
  }

  creating.value = true
  createError.value = null

  try {
    const payload = {
      type: form.type,
      account_id: form.account_id,
      params: buildParams(),
    }
    if (form.device_id) {
      payload.device_id = form.device_id
    }
    await createTask(payload)
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

// --- Keyword search ---
function openKeywordDialog() {
  keywordSeed.value = ''
  keywordList.value = []
  keywordError.value = null
  keywordActionType.value = 'search_comment'
  keywordAccountId.value = ''
  keywordCount.value = 10
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
    const res = await generateKeywords(keywordSeed.value.trim(), keywordCount.value)
    keywordList.value = res.data.keywords || []
    if (keywordList.value.length === 0) {
      keywordError.value = '未生成关键词，请重试'
    }
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '生成失败，请重试'
  } finally {
    keywordGenerating.value = false
  }
}

function removeKeyword(idx) {
  keywordList.value.splice(idx, 1)
}

async function handleBatchCreateKeywordTasks() {
  if (keywordList.value.length === 0) {
    keywordError.value = '请先生成关键词'
    return
  }
  if (!keywordAccountId.value) {
    keywordError.value = '请选择账号'
    return
  }

  creating.value = true
  keywordError.value = null

  let successCount = 0
  let failCount = 0

  for (const kw of keywordList.value) {
    try {
      const params = { keyword: kw, count: 5 }
      if (['search_comment', 'search_dm', 'reply_comment'].includes(keywordActionType.value)) {
        params.content = ''
      }
      await createTask({
        type: keywordActionType.value,
        account_id: keywordAccountId.value,
        params,
      })
      successCount++
    } catch (e) {
      failCount++
    }
  }

  creating.value = false
  showKeywordDialog.value = false
  page.value = 1
  fetchTasks()

  if (failCount > 0) {
    pageError.value = `批量创建完成：成功 ${successCount} 个，失败 ${failCount} 个`
  }
}

// --- Init ---
onMounted(() => {
  fetchTasks()
  fetchAccounts()
  fetchDevices()
  fetchTemplates()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-500 hover:text-red-700 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">任务中心</h1>
      <div class="flex items-center gap-3">
        <!-- Status filter -->
        <select
          v-model="statusFilter"
          class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
          class="inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700 transition-colors"
          @click="openKeywordDialog"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          关键词搜索
        </button>
        <!-- Create button -->
        <button
          class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
          @click="openCreateDialog"
        >
          <svg
            class="-ml-1 mr-2 h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
            />
          </svg>
          创建任务
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
        <span class="text-gray-700">
          {{ accounts.find(a => a.id === value)?.nickname || value }}
        </span>
      </template>

      <!-- Device column -->
      <template #cell-device_id="{ value }">
        <span v-if="value" class="text-gray-700">
          {{ devices.find(d => d.id === value)?.name || value }}
        </span>
        <span v-else class="text-gray-400">自动分配</span>
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
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
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
          <div class="fixed inset-0 bg-black/30" />
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
                class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
              >
                <DialogTitle class="text-lg font-medium text-gray-900">
                  创建任务
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="createError"
                  class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded"
                >
                  {{ createError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                  <!-- Task Type -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">
                      任务类型 <span class="text-red-500">*</span>
                    </label>
                    <select
                      v-model="form.type"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option v-for="opt in taskTypeOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                  </div>

                  <!-- Account -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">
                      账号 <span class="text-red-500">*</span>
                    </label>
                    <select
                      v-model="form.account_id"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="" disabled>请选择账号</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Device -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">
                      执行设备
                    </label>
                    <select
                      v-model="form.device_id"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
                      <label class="block text-sm font-medium text-gray-700 mb-2">养号模式</label>
                      <div class="flex gap-4">
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input type="radio" v-model="nurtureMode" value="simple" class="text-indigo-600 focus:ring-indigo-500" />
                          <span class="text-sm">简单模式</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer">
                          <input type="radio" v-model="nurtureMode" value="advanced" class="text-indigo-600 focus:ring-indigo-500" />
                          <span class="text-sm">高级模式（子任务）</span>
                        </label>
                      </div>
                    </div>

                    <!-- 简单模式 -->
                    <div v-if="nurtureMode === 'simple'">
                      <label class="block text-sm font-medium text-gray-700">养号时长（分钟）</label>
                      <input
                        v-model.number="form.duration"
                        type="number"
                        min="1"
                        max="120"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>

                    <!-- 高级模式 -->
                    <div v-else class="space-y-3">
                      <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">子任务列表</label>
                        <div class="space-y-2">
                          <div v-for="(st, idx) in subTasks" :key="idx" class="flex items-center gap-2">
                            <select v-model="st.type" class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                              <option v-for="opt in subTaskTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                            </select>
                            <input v-model.number="st.count" type="number" min="1" max="100" class="w-20 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="次数" />
                            <select v-if="st.type === 'comment'" v-model="st.content_template_id" class="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                              <option value="">选择模板</option>
                              <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }}</option>
                            </select>
                            <button type="button" @click="removeSubTask(idx)" class="text-red-500 hover:text-red-700">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                          </div>
                        </div>
                        <button type="button" @click="addSubTask" class="mt-2 text-sm text-indigo-600 hover:text-indigo-800">+ 添加子任务</button>
                      </div>
                      <div class="grid grid-cols-2 gap-3">
                        <div>
                          <label class="block text-sm font-medium text-gray-700">完成模式</label>
                          <select v-model="completionMode" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                            <option value="all">全部完成</option>
                            <option value="any">任一完成</option>
                          </select>
                        </div>
                        <div>
                          <label class="block text-sm font-medium text-gray-700">最大时长（分钟）</label>
                          <input v-model.number="maxDuration" type="number" min="1" max="240" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                        </div>
                      </div>
                    </div>
                  </template>

                  <!-- 搜索类参数 -->
                  <template v-if="isSearchType">
                    <div>
                      <label class="block text-sm font-medium text-gray-700">
                        搜索关键词 <span class="text-red-500">*</span>
                      </label>
                      <input
                        v-model="form.keyword"
                        type="text"
                        maxlength="50"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        placeholder="例：美食、养生"
                      />
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-gray-700">排序方式</label>
                      <select
                        v-model="form.sort_by"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        <option value="">默认排序</option>
                        <option value="latest">最新发布</option>
                        <option value="most_liked">最多点赞</option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-gray-700">
                        {{ form.type === 'reply_comment' ? '每视频评论数' : '处理数量' }}
                      </label>
                      <input
                        v-model.number="form.count"
                        type="number"
                        min="1"
                        :max="form.type === 'search_like' ? 30 : 20"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  </template>

                  <!-- 评论回复特有参数 -->
                  <template v-if="form.type === 'reply_comment'">
                    <div>
                      <label class="block text-sm font-medium text-gray-700">处理视频数</label>
                      <input
                        v-model.number="form.video_count"
                        type="number"
                        min="1"
                        max="10"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                    <div>
                      <label class="block text-sm font-medium text-gray-700">评论最大天数</label>
                      <input
                        v-model.number="form.max_age_days"
                        type="number"
                        min="1"
                        max="30"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  </template>

                  <!-- 内容类任务的私信/评论内容 -->
                  <template v-if="['search_comment', 'search_dm', 'reply_comment'].includes(form.type)">
                    <!-- Template -->
                    <div v-if="filteredTemplates.length > 0">
                      <label class="block text-sm font-medium text-gray-700">内容模板</label>
                      <select
                        v-model="selectedTemplateId"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        <option value="">不使用模板</option>
                        <option v-for="tpl in filteredTemplates" :key="tpl.id" :value="tpl.id">
                          {{ tpl.name }} ({{ tpl.category }})
                        </option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-sm font-medium text-gray-700">
                        {{ form.type === 'search_dm' ? '私信内容' : '评论/私信内容' }}
                      </label>
                      <textarea
                        v-model="form.content"
                        rows="3"
                        maxlength="500"
                        class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        :placeholder="form.type === 'reply_comment' ? '留空则使用 AI 生成招呼语' : '输入内容...'"
                      />
                    </div>
                  </template>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                      @click="showCreateDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="creating"
                      class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {{ creating ? '创建中...' : '创建' }}
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
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">关键词搜索</DialogTitle>

                <div v-if="keywordError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ keywordError }}
                </div>

                <div class="mt-4 space-y-4">
                  <!-- Seed keyword input -->
                  <div class="flex gap-2">
                    <input
                      v-model="keywordSeed"
                      type="text"
                      maxlength="50"
                      class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="输入种子关键词，如：美食"
                      @keyup.enter="handleGenerateKeywords"
                    />
                    <input v-model.number="keywordCount" type="number" min="1" max="30" class="w-20 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                    <button
                      type="button"
                      :disabled="keywordGenerating"
                      class="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      @click="handleGenerateKeywords"
                    >
                      {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
                    </button>
                  </div>

                  <!-- Generated keywords -->
                  <div v-if="keywordList.length > 0">
                    <label class="block text-sm font-medium text-gray-700 mb-1">关键词矩阵（可编辑删除）</label>
                    <div class="flex flex-wrap gap-2 p-3 border rounded-lg max-h-40 overflow-y-auto">
                      <span
                        v-for="(kw, idx) in keywordList"
                        :key="idx"
                        class="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-50 text-indigo-700 text-sm rounded-full"
                      >
                        {{ kw }}
                        <button type="button" @click="removeKeyword(idx)" class="text-indigo-400 hover:text-indigo-600">
                          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                      </span>
                    </div>
                  </div>

                  <!-- Action type -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">操作类型</label>
                    <select v-model="keywordActionType" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      <option value="search_comment">搜索评论</option>
                      <option value="search_like">搜索点赞</option>
                      <option value="search_dm">搜索私信</option>
                      <option value="reply_comment">评论回复</option>
                    </select>
                  </div>

                  <!-- Account selection -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">选择账号 <span class="text-red-500">*</span></label>
                    <select v-model="keywordAccountId" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      <option value="" disabled>请选择账号</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>
                </div>

                <div class="flex justify-end gap-3 pt-4">
                  <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showKeywordDialog = false">取消</button>
                  <button
                    type="button"
                    :disabled="creating || keywordList.length === 0"
                    class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    @click="handleBatchCreateKeywordTasks"
                  >
                    {{ creating ? '创建中...' : `批量创建 ${keywordList.length} 个任务` }}
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
  </div>
</template>
