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
import TipIcon from '../components/TipIcon.vue'
import { listInstances, getInstance, createInstances, cancelInstance, retryInstance } from '../api/chains.js'
import { listTemplates } from '../api/chains.js'
import { listAccounts } from '../api/accounts.js'
import { listDevices } from '../api/devices.js'
import { listGroups } from '../api/accountGroups.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'

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
const devices = ref([])

const createForm = reactive({
  template_id: '',
  selectionMode: 'accounts', // 'accounts' or 'groups'
  account_ids: [],
  group_ids: [],
  device_id: '',
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

const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'chains_changed') fetchInstances()
  },
})

// --- Table columns ---
const columns = [
  { key: 'template_name', label: '模板' },
  { key: 'account_nickname', label: '账号' },
  { key: 'device_name', label: '设备' },
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
    toast.error('加载实例列表失败')
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
  createForm.device_id = ''
  createError.value = null
  showCreateDialog.value = true
  await Promise.all([fetchTemplatesForSelect(), fetchAccountsForSelect(), fetchGroupsForSelect(), fetchDevicesForSelect()])
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

async function fetchDevicesForSelect() {
  try {
    const res = await listDevices({ limit: 100 })
    devices.value = (res.data.devices || []).filter(d => d.status === 'online')
  } catch (e) {
    devices.value = []
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
  if (createForm.device_id) {
    payload.device_id = createForm.device_id
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
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 rounded-xl px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">链实例<TipIcon text="任务链的运行实例，每个实例对应一个账号正在执行或已完成的任务链" /></h1>
      <div class="flex items-center gap-3">
        <select
          v-model="statusFilter"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
        >
          <option value="">全部状态</option>
          <option value="pending">待执行</option>
          <option value="running">执行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <button
          class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
          @click="openCreateDialog"
        >
          <span class="relative z-10 inline-flex items-center">
            <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
            </svg>
            批量创建
          </span>
        </button>
        <TipIcon text="选择模板和账号后，为每个账号创建一个链实例。繁忙的账号会自动跳过" />
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
          <div class="flex-1 bg-white/10 rounded-full h-1.5 max-w-[60px]">
            <div
              class="bg-cyan-400 h-1.5 rounded-full"
              :style="{ width: Math.round(row.current_step / row.total_steps * 100) + '%' }"
            ></div>
          </div>
        </div>
      </template>

      <template #cell-device_name="{ value }">
        <span class="text-sm" :class="value ? 'text-slate-200' : 'text-slate-500'">{{ value || '自动分配' }}</span>
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
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
            @click="openDetailDialog(row)"
          >
            详情
          </button>
          <button
            v-if="row.status === 'pending' || row.status === 'running'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
            @click="openCancelDialog(row)"
          >
            取消
          </button>
          <button
            v-if="row.status === 'failed'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
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
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">批量创建链实例</DialogTitle>
                <div v-if="createError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ createError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                  <!-- Template selection -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">选择模板 <span class="text-red-400">*</span></label>
                    <select v-model="createForm.template_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500">
                      <option value="" disabled>请选择模板</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                        {{ tpl.name }} ({{ tpl.steps?.length || 0 }} 步)
                      </option>
                    </select>
                  </div>

                  <!-- Selection mode -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">账号选择方式 <TipIcon text="直接选账号=逐个选择；按分组选=选择账号分组，组内所有活跃账号都会创建实例" width="w-80" /></label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="accounts" class="text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">直接选账号</span>
                      </label>
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="groups" class="text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">按分组选</span>
                      </label>
                    </div>
                  </div>

                  <!-- Account selection -->
                  <div v-if="createForm.selectionMode === 'accounts'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">选择账号</label>
                    <div class="border border-white/10 rounded-lg p-3 max-h-48 overflow-y-auto">
                      <label v-for="acct in accounts" :key="acct.id" class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer">
                        <input type="checkbox" :value="acct.id" v-model="createForm.account_ids" class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">{{ acct.nickname || acct.douyin_id || acct.id }}</span>
                      </label>
                    </div>
                  </div>

                  <!-- Group selection -->
                  <div v-if="createForm.selectionMode === 'groups'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">选择分组</label>
                    <div class="border border-white/10 rounded-lg p-3 max-h-48 overflow-y-auto">
                      <div v-if="groups.length === 0" class="text-sm text-slate-500 text-center py-2">暂无分组</div>
                      <label v-for="group in groups" :key="group.id" class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer">
                        <input type="checkbox" :value="group.id" v-model="createForm.group_ids" class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">{{ group.name }} ({{ group.member_count }} 人)</span>
                      </label>
                    </div>
                  </div>

                  <!-- Device selection -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">指定设备 <TipIcon text="可选。指定后所有任务推送到该设备执行。不指定则自动分配账号绑定的设备" /></label>
                    <select v-model="createForm.device_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">自动分配</option>
                      <option v-for="dev in devices" :key="dev.id" :value="dev.id">
                        {{ dev.name }}{{ dev.bound_account_id ? ' (已绑定)' : '' }}
                      </option>
                    </select>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showCreateDialog = false">取消</button>
                    <button type="submit" :disabled="creating" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
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

    <!-- Detail Dialog -->
    <TransitionRoot :show="showDetailDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showDetailDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  链实例详情
                </DialogTitle>
                <div v-if="detailLoading" class="mt-4 text-center text-slate-500">加载中...</div>
                <div v-else-if="detailInstance" class="mt-4 space-y-4">
                  <div class="grid grid-cols-2 gap-3 text-sm">
                    <div><span class="text-slate-400">模板：</span>{{ detailInstance.template_name }}</div>
                    <div><span class="text-slate-400">账号：</span>{{ detailInstance.account_nickname }}</div>
                    <div><span class="text-slate-400">设备：</span>{{ detailInstance.device_name || '自动分配' }}</div>
                    <div><span class="text-slate-400">状态：</span><StatusBadge :status="detailInstance.status" /></div>
                    <div><span class="text-slate-400">进度：</span>{{ detailInstance.current_step }} / {{ detailInstance.total_steps }}</div>
                  </div>

                  <!-- Step timeline -->
                  <div>
                    <h4 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">步骤时间线<TipIcon text="灰色=待执行，蓝色=执行中，绿色=已完成，红色=失败" /></h4>
                    <div class="space-y-2">
                      <div
                        v-for="task in (detailInstance.tasks || [])"
                        :key="task.id"
                        class="flex items-start gap-3 p-2 rounded-lg"
                        :class="{
                          'bg-emerald-500/10': task.status === 'completed',
                          'bg-cyan-400/10': task.status === 'running' || task.status === 'pending',
                          'bg-red-500/10': task.status === 'failed',
                          'bg-white/5': task.status === 'cancelled',
                        }"
                      >
                        <div class="flex-shrink-0 mt-0.5">
                          <div v-if="task.status === 'completed'" class="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                          </div>
                          <div v-else-if="task.status === 'running'" class="w-5 h-5 rounded-full bg-cyan-400 animate-pulse"></div>
                          <div v-else-if="task.status === 'failed'" class="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12"/></svg>
                          </div>
                          <div v-else class="w-5 h-5 rounded-full bg-white/20"></div>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="text-sm font-medium text-slate-200">步骤 {{ task.step_order }}: {{ task.type }}</div>
                          <div class="text-xs text-slate-400 mt-0.5">
                            <span v-if="task.started_at">开始: {{ formatDate(task.started_at) }}</span>
                            <span v-if="task.completed_at"> | 完成: {{ formatDate(task.completed_at) }}</span>
                          </div>
                          <div v-if="task.result" class="text-xs text-slate-400 mt-1">{{ JSON.stringify(task.result) }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="flex justify-end mt-4">
                  <button class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showDetailDialog = false">关闭</button>
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
