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
import { listTemplates } from '../api/content.js'
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
  params: '{}',
}
const form = reactive({ ...defaultForm })

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

  // Parse params JSON
  let parsedParams = {}
  if (form.params.trim()) {
    try {
      parsedParams = JSON.parse(form.params)
    } catch {
      createError.value = '参数格式错误，请输入合法的 JSON'
      return
    }
  }

  if (selectedTemplateId.value) {
    parsedParams.content_template_id = selectedTemplateId.value
  }

  creating.value = true
  createError.value = null

  try {
    await createTask({
      type: form.type,
      account_id: Number(form.account_id),
      params: parsedParams,
    })
    showCreateDialog.value = false
    // Reset to first page and re-fetch
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

// --- Init ---
onMounted(() => {
  fetchTasks()
  fetchAccounts()
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
                    <label
                      for="task-type"
                      class="block text-sm font-medium text-gray-700"
                    >
                      任务类型 <span class="text-red-500">*</span>
                    </label>
                    <select
                      id="task-type"
                      v-model="form.type"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option
                        v-for="opt in taskTypeOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </option>
                    </select>
                  </div>

                  <!-- Account -->
                  <div>
                    <label
                      for="task-account"
                      class="block text-sm font-medium text-gray-700"
                    >
                      账号 <span class="text-red-500">*</span>
                    </label>
                    <select
                      id="task-account"
                      v-model="form.account_id"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="" disabled>请选择账号</option>
                      <option
                        v-for="acct in accounts"
                        :key="acct.id"
                        :value="acct.id"
                      >
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Template (optional, not for nurture) -->
                  <div v-if="filteredTemplates.length > 0">
                    <label
                      for="task-template"
                      class="block text-sm font-medium text-gray-700"
                    >
                      内容模板
                    </label>
                    <select
                      id="task-template"
                      v-model="selectedTemplateId"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="">不使用模板</option>
                      <option
                        v-for="tpl in filteredTemplates"
                        :key="tpl.id"
                        :value="tpl.id"
                      >
                        {{ tpl.name }} ({{ tpl.category }})
                      </option>
                    </select>
                  </div>

                  <!-- Params -->
                  <div>
                    <label
                      for="task-params"
                      class="block text-sm font-medium text-gray-700"
                    >
                      参数 (JSON)
                    </label>
                    <textarea
                      id="task-params"
                      v-model="form.params"
                      rows="4"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                      placeholder="{}"
                    />
                  </div>

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
  </div>
</template>
