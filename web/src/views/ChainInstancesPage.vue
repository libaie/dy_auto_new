<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
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
import { listInstances, getInstance, createInstances, cancelInstance, retryInstance } from '../api/chains.js'
import { listTemplates } from '../api/chains.js'
import { listAccounts } from '../api/accounts.js'
import { listGroups } from '../api/accountGroups.js'
import { formatDate } from '../utils/format.js'

const statusMap = {
  pending: '待执行',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

// --- Data state ---
const instances = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')

// --- Create dialog state ---
const showCreateDialog = ref(false)
const creating = ref(false)
const createError = ref(null)
const templates = ref([])
const accounts = ref([])
const groups = ref([])

const createForm = reactive({
  template_id: '',
  selectionMode: 'accounts', // 'accounts' or 'groups'
  account_ids: [],
  group_ids: [],
})

// --- Detail dialog state ---
const showDetailDialog = ref(false)
const detailInstance = ref(null)
const detailLoading = ref(false)

// --- Cancel / Retry ---
const showCancelDialog = ref(false)
const cancellingInstance = ref(null)
const cancelling = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Table columns ---
const columns = [
  { key: 'template_name', label: '模板' },
  { key: 'account_nickname', label: '账号' },
  { key: 'current_step', label: '当前步骤' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch instances ---
async function fetchInstances() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const params = { skip, limit: pageSize }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await listInstances(params)
    instances.value = res.data.instances || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to fetch instances:', e)
    instances.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchInstances()
}

watch(statusFilter, () => {
  page.value = 1
  fetchInstances()
})

// --- Create dialog ---
async function openCreateDialog() {
  createForm.template_id = ''
  createForm.selectionMode = 'accounts'
  createForm.account_ids = []
  createForm.group_ids = []
  createError.value = null
  showCreateDialog.value = true
  await Promise.all([fetchTemplatesForSelect(), fetchAccountsForSelect(), fetchGroupsForSelect()])
}

async function fetchTemplatesForSelect() {
  try {
    const res = await listTemplates({ limit: 100 })
    templates.value = res.data.templates || []
  } catch (e) {
    templates.value = []
  }
}

async function fetchAccountsForSelect() {
  try {
    const res = await listAccounts({ limit: 200 })
    accounts.value = (res.data.accounts || []).filter(a => a.status === 'active')
  } catch (e) {
    accounts.value = []
  }
}

async function fetchGroupsForSelect() {
  try {
    const res = await listGroups({ limit: 100 })
    groups.value = res.data.groups || []
  } catch (e) {
    groups.value = []
  }
}

async function handleCreate() {
  if (!createForm.template_id) {
    createError.value = '请选择模板'
    return
  }
  if (createForm.selectionMode === 'accounts' && createForm.account_ids.length === 0) {
    createError.value = '请选择至少一个账号'
    return
  }
  if (createForm.selectionMode === 'groups' && createForm.group_ids.length === 0) {
    createError.value = '请选择至少一个分组'
    return
  }

  creating.value = true
  createError.value = null

  const payload = { template_id: createForm.template_id }
  if (createForm.selectionMode === 'accounts') {
    payload.account_ids = createForm.account_ids
  } else {
    payload.group_ids = createForm.group_ids
  }

  try {
    const res = await createInstances(payload)
    const data = res.data
    showCreateDialog.value = false
    page.value = 1
    fetchInstances()

    if (data.skipped_busy_count > 0) {
      pageError.value = `创建成功 ${data.created_count} 个，跳过 ${data.skipped_busy_count} 个（账号繁忙）`
    }
  } catch (e) {
    createError.value = e.response?.data?.detail || '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

// --- Detail dialog ---
async function openDetailDialog(instance) {
  showDetailDialog.value = true
  detailLoading.value = true
  try {
    const res = await getInstance(instance.id)
    detailInstance.value = res.data
  } catch (e) {
    pageError.value = '获取详情失败'
    showDetailDialog.value = false
  } finally {
    detailLoading.value = false
  }
}

// --- Cancel ---
function openCancelDialog(instance) {
  cancellingInstance.value = instance
  showCancelDialog.value = true
}

async function handleCancel() {
  if (!cancellingInstance.value) return
  cancelling.value = true
  try {
    await cancelInstance(cancellingInstance.value.id)
    showCancelDialog.value = false
    cancellingInstance.value = null
    fetchInstances()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '取消失败'
  } finally {
    cancelling.value = false
  }
}

// --- Retry ---
async function handleRetry(instance) {
  try {
    await retryInstance(instance.id)
    fetchInstances()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '重试失败'
  }
}

onMounted(fetchInstances)
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
      <h1 class="text-2xl font-bold text-gray-800">链实例</h1>
      <div class="flex items-center gap-3">
        <select
          v-model="statusFilter"
          class="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">全部状态</option>
          <option value="pending">待执行</option>
          <option value="running">执行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <button
          class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
          @click="openCreateDialog"
        >
          <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          批量创建
        </button>
      </div>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="instances"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-current_step="{ row }">
        <div class="flex items-center gap-2">
          <span class="text-sm">{{ row.current_step }} / {{ row.total_steps }}</span>
          <div class="flex-1 bg-gray-200 rounded-full h-1.5 max-w-[60px]">
            <div
              class="bg-indigo-600 h-1.5 rounded-full"
              :style="{ width: Math.round(row.current_step / row.total_steps * 100) + '%' }"
            ></div>
          </div>
        </div>
      </template>

      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
            @click="openDetailDialog(row)"
          >
            详情
          </button>
          <button
            v-if="row.status === 'pending' || row.status === 'running'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
            @click="openCancelDialog(row)"
          >
            取消
          </button>
          <button
            v-if="row.status === 'failed'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-green-600 hover:text-green-800 hover:bg-green-50 rounded transition-colors"
            @click="handleRetry(row)"
          >
            重试
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create Dialog -->
    <TransitionRoot :show="showCreateDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showCreateDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">批量创建链实例</DialogTitle>
                <div v-if="createError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ createError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                  <!-- Template selection -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">选择模板 <span class="text-red-500">*</span></label>
                    <select v-model="createForm.template_id" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      <option value="" disabled>请选择模板</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                        {{ tpl.name }} ({{ tpl.steps?.length || 0 }} 步)
                      </option>
                    </select>
                  </div>

                  <!-- Selection mode -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">账号选择方式</label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="accounts" class="text-indigo-600 focus:ring-indigo-500" />
                        <span class="text-sm">直接选账号</span>
                      </label>
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="groups" class="text-indigo-600 focus:ring-indigo-500" />
                        <span class="text-sm">按分组选</span>
                      </label>
                    </div>
                  </div>

                  <!-- Account selection -->
                  <div v-if="createForm.selectionMode === 'accounts'">
                    <label class="block text-sm font-medium text-gray-700 mb-1">选择账号</label>
                    <div class="border rounded-lg p-3 max-h-48 overflow-y-auto">
                      <label v-for="acct in accounts" :key="acct.id" class="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                        <input type="checkbox" :value="acct.id" v-model="createForm.account_ids" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                        <span class="text-sm">{{ acct.nickname || acct.douyin_id || acct.id }}</span>
                      </label>
                    </div>
                  </div>

                  <!-- Group selection -->
                  <div v-if="createForm.selectionMode === 'groups'">
                    <label class="block text-sm font-medium text-gray-700 mb-1">选择分组</label>
                    <div class="border rounded-lg p-3 max-h-48 overflow-y-auto">
                      <div v-if="groups.length === 0" class="text-sm text-gray-400 text-center py-2">暂无分组</div>
                      <label v-for="group in groups" :key="group.id" class="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                        <input type="checkbox" :value="group.id" v-model="createForm.group_ids" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                        <span class="text-sm">{{ group.name }} ({{ group.member_count }} 人)</span>
                      </label>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showCreateDialog = false">取消</button>
                    <button type="submit" :disabled="creating" class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
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

    <!-- Detail Dialog -->
    <TransitionRoot :show="showDetailDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showDetailDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  链实例详情
                </DialogTitle>
                <div v-if="detailLoading" class="mt-4 text-center text-gray-400">加载中...</div>
                <div v-else-if="detailInstance" class="mt-4 space-y-4">
                  <div class="grid grid-cols-2 gap-3 text-sm">
                    <div><span class="text-gray-500">模板：</span>{{ detailInstance.template_name }}</div>
                    <div><span class="text-gray-500">账号：</span>{{ detailInstance.account_nickname }}</div>
                    <div><span class="text-gray-500">状态：</span><StatusBadge :status="detailInstance.status" /></div>
                    <div><span class="text-gray-500">进度：</span>{{ detailInstance.current_step }} / {{ detailInstance.total_steps }}</div>
                  </div>

                  <!-- Step timeline -->
                  <div>
                    <h4 class="text-sm font-medium text-gray-700 mb-2">步骤时间线</h4>
                    <div class="space-y-2">
                      <div
                        v-for="task in (detailInstance.tasks || [])"
                        :key="task.id"
                        class="flex items-start gap-3 p-2 rounded-lg"
                        :class="{
                          'bg-green-50': task.status === 'completed',
                          'bg-blue-50': task.status === 'running' || task.status === 'pending',
                          'bg-red-50': task.status === 'failed',
                          'bg-gray-50': task.status === 'cancelled',
                        }"
                      >
                        <div class="flex-shrink-0 mt-0.5">
                          <div v-if="task.status === 'completed'" class="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                          </div>
                          <div v-else-if="task.status === 'running'" class="w-5 h-5 rounded-full bg-blue-500 animate-pulse"></div>
                          <div v-else-if="task.status === 'failed'" class="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12"/></svg>
                          </div>
                          <div v-else class="w-5 h-5 rounded-full bg-gray-300"></div>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="text-sm font-medium">步骤 {{ task.step_order }}: {{ task.type }}</div>
                          <div class="text-xs text-gray-500 mt-0.5">
                            <span v-if="task.started_at">开始: {{ formatDate(task.started_at) }}</span>
                            <span v-if="task.completed_at"> | 完成: {{ formatDate(task.completed_at) }}</span>
                          </div>
                          <div v-if="task.result" class="text-xs text-gray-600 mt-1">{{ JSON.stringify(task.result) }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="flex justify-end mt-4">
                  <button class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showDetailDialog = false">关闭</button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Cancel Confirmation Dialog -->
    <ConfirmDialog
      :open="showCancelDialog"
      title="取消链实例"
      message="确定要取消该链实例吗？当前执行中的步骤也会被取消。"
      confirm-text="取消链"
      :danger="true"
      @confirm="handleCancel"
      @cancel="showCancelDialog = false"
    />
  </div>
</template>
