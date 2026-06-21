<!-- 管理端业务页面：承载 DevicesPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
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
import {
  listDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  disconnectDevice,
  listPairRequests,
  approvePairRequest,
  rejectPairRequest,
} from '../api/devices.js'
import { listAccounts } from '../api/accounts.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'

// --- Tab state ---
const activeTab = ref('devices') // "devices" | "pairing"

// --- Data state ---
const devices = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

// --- Accounts list for binding dropdown ---
const accounts = ref([])
async function fetchAccounts() {
  try {
    const res = await listAccounts({ limit: 200 })
    accounts.value = res.data.accounts || []
  } catch { /* ignore */ }
}

// --- Pair requests state ---
const pairRequests = ref([])
const pairLoading = ref(false)
const pairActionLoading = ref(null) // request id being acted on
const pendingCount = computed(() => pairRequests.value.length)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  name: '',
  ip: '',
  bound_account_id: '',
  proxy_config: '',
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)
const proxyError = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingDevice = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- Table columns ---
const columns = [
  { key: 'name', label: '设备名称' },
  { key: 'id', label: '设备ID' },
  { key: 'ip', label: 'IP 地址' },
  { key: 'status', label: '状态' },
  { key: 'bound_account_id', label: '绑定账号' },
  { key: 'last_seen_at', label: '最近在线' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch devices ---
async function fetchDevices() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listDevices({ skip, limit: pageSize })
    devices.value = res.data.devices || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载设备列表失败')
    devices.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchDevices()
}

// --- Fetch pair requests ---
async function fetchPairRequests() {
  pairLoading.value = true
  try {
    const res = await listPairRequests('pending')
    pairRequests.value = res.data.requests || []
  } catch (e) {
    toast.error('加载配对请求失败')
    pairRequests.value = []
  } finally {
    pairLoading.value = false
  }
}

async function handleApprove(req) {
  pairActionLoading.value = req.id
  try {
    await approvePairRequest(req.id)
    // WS will handle list update; fallback refresh if WS disconnected
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchPairRequests()
      fetchDevices()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '审批失败，请重试'
  } finally {
    pairActionLoading.value = null
  }
}

async function handleReject(req) {
  pairActionLoading.value = req.id
  try {
    await rejectPairRequest(req.id)
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchPairRequests()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '拒绝失败，请重试'
  } finally {
    pairActionLoading.value = null
  }
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'pairing') fetchPairRequests()
  else fetchDevices()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  proxyError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(device) {
  isEditing.value = true
  editingId.value = device.id
  form.name = device.name || ''
  form.ip = device.ip || ''
  form.bound_account_id = device.bound_account_id != null ? String(device.bound_account_id) : ''
  form.proxy_config = device.proxy_config ? JSON.stringify(device.proxy_config) : ''
  formError.value = null
  proxyError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '设备名称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    ip: form.ip.trim() || undefined,
  }

  if (form.proxy_config.trim()) {
    try {
      const parsed = JSON.parse(form.proxy_config)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        payload.proxy_config = parsed
        proxyError.value = null
      } else {
        proxyError.value = '代理配置需为 JSON 对象格式，如 {"server": "socks5://host:port"}'
        saving.value = false
        return
      }
    } catch {
      proxyError.value = 'JSON 格式不正确，请检查'
      saving.value = false
      return
    }
  }

  payload.bound_account_id = form.bound_account_id || null

  try {
    if (isEditing.value) {
      await updateDevice(editingId.value, payload)
    } else {
      await createDevice(payload)
    }
    showFormDialog.value = false
    fetchDevices()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(device) {
  deletingDevice.value = device
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingDevice.value) return
  deleting.value = true
  try {
    await deleteDevice(deletingDevice.value.id)
    showDeleteDialog.value = false
    deletingDevice.value = null
    if (devices.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchDevices()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Force disconnect ---
const disconnectingId = ref(null)

async function handleDisconnect(device) {
  disconnectingId.value = device.id
  try {
    await disconnectDevice(device.id)
    // Status will update via WS event; fallback refresh
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchDevices()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '断开失败，请重试'
  } finally {
    disconnectingId.value = null
  }
}

// --- WebSocket for real-time pair events ---
let ws = null
let wsReconnectTimer = null
let wsDisposed = false

function connectPairWS() {
  if (wsDisposed || ws) return
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = localStorage.getItem('token') || ''
  const wsUrl = `${proto}//${window.location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log('Pair events WS connected')
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.event === 'new_pair_request') {
        // New device requesting pairing — add to list and switch tab
        pairRequests.value.unshift(data.request)
        if (activeTab.value !== 'pairing') {
          activeTab.value = 'pairing'
        }
      } else if (data.event === 'pair_approved' || data.event === 'pair_rejected') {
        // Request resolved — remove from pending list
        pairRequests.value = pairRequests.value.filter(r => r.id !== data.request_id)
        if (data.event === 'pair_approved') {
          fetchDevices() // refresh device list
        }
      } else if (data.event === 'device_status_changed') {
        if (data.status === 'deleted') {
          // Device was removed — remove from list
          devices.value = devices.value.filter(d => d.id !== data.device_id)
        } else {
          // Device status changed (e.g. went offline/online)
          const dev = devices.value.find(d => d.id === data.device_id)
          if (dev) {
            dev.status = data.status
          }
        }
      } else if (data.event === 'devices_changed') {
        fetchDevices()
      }
    } catch (e) {
      console.error('WS message parse error:', e)
    }
  }

  ws.onclose = () => {
    ws = null
    // Reconnect after 3s (only if component is still mounted)
    if (!wsDisposed) {
      wsReconnectTimer = setTimeout(connectPairWS, 3000)
    }
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function disconnectPairWS() {
  wsDisposed = true
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (ws) {
    ws.close()
    ws = null
  }
}

// --- Init ---
onMounted(() => {
  fetchDevices()
  fetchAccounts()
  fetchPairRequests()
  connectPairWS()
})

onUnmounted(() => {
  disconnectPairWS()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">设备管理 <TipIcon text="管理自动化设备，配置绑定关系和网络代理" /></h1>
      <button
        v-if="activeTab === 'devices'"
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg
          class="-ml-1 mr-2 h-5 w-5 relative z-10"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
          />
        </svg>
        <span class="relative z-10">添加设备</span>
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-white/10 mb-6">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'devices'
          ? 'border-cyan-400 text-cyan-400'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-white/20'"
        @click="switchTab('devices')"
      >
        设备列表
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors relative"
        :class="activeTab === 'pairing'
          ? 'border-cyan-400 text-cyan-400'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-white/20'"
        @click="switchTab('pairing')"
      >
        待配对
        <TipIcon text="新设备发起配对请求后需要在此审批通过才能加入系统" />
        <span
          v-if="pendingCount > 0"
          class="ml-1.5 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white bg-red-500 rounded-full"
        >
          {{ pendingCount }}
        </span>
      </button>
    </div>

    <!-- Pair Requests List -->
    <div v-if="activeTab === 'pairing'">
      <div v-if="pairLoading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="pairRequests.length === 0" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="mt-2 text-sm text-slate-400">暂无待配对设备</p>
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="req in pairRequests"
          :key="req.id"
          class="glass-card p-4 flex items-center justify-between"
        >
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold text-white">{{ req.device_name }}</span>
              <span class="text-xs text-slate-500 font-mono">{{ req.device_id }}</span>
            </div>
            <div class="mt-1 flex items-center gap-4 text-xs text-slate-400">
              <span v-if="req.os_version">系统: {{ req.os_version }}</span>
              <span v-if="req.app_version">版本: {{ req.app_version }}</span>
              <span>申请时间: {{ formatDate(req.created_at) }}</span>
            </div>
          </div>
          <div class="flex gap-2 ml-4">
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-lg transition-all shadow-lg shadow-emerald-500/25 disabled:opacity-50"
              :disabled="pairActionLoading === req.id"
              @click="handleApprove(req)"
            >
              {{ pairActionLoading === req.id ? '处理中...' : '批准' }}
            </button>
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-400 hover:text-red-300 border border-red-500/30 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
              :disabled="pairActionLoading === req.id"
              @click="handleReject(req)"
            >
              拒绝
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Table -->
    <DataTable v-if="activeTab === 'devices'"
      :columns="columns"
      :data="devices"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <!-- Status column -->
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <!-- Bound account column -->
      <template #cell-bound_account_id="{ value }">
        <span v-if="value" class="text-slate-200">
          {{ accounts.find(a => a.id === value)?.nickname || value }}
        </span>
        <span v-else class="text-slate-500">—</span>
      </template>

      <!-- Last seen at column -->
      <template #cell-last_seen_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            v-if="row.status === 'online'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-amber-400 hover:text-amber-300 hover:bg-amber-400/10 rounded-lg transition-colors disabled:opacity-50"
            :disabled="disconnectingId === row.id"
            @click="handleDisconnect(row)"
          >
            {{ disconnectingId === row.id ? '断开中...' : '断开' }}
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded-lg transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
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
                  {{ isEditing ? '编辑设备' : '添加设备' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>
                <div
                  v-if="proxyError"
                  class="mt-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ proxyError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Name -->
                  <div>
                    <label
                      for="device-name"
                      class="block text-sm font-medium text-slate-300"
                    >
                      设备名称 <span class="text-red-400">*</span>
                    </label>
                    <input
                      id="device-name"
                      v-model="form.name"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入设备名称"
                    />
                  </div>

                  <!-- IP -->
                  <div>
                    <label
                      for="device-ip"
                      class="block text-sm font-medium text-slate-300"
                    >
                      IP 地址
                    </label>
                    <input
                      id="device-ip"
                      v-model="form.ip"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如 192.168.1.100"
                    />
                  </div>

                  <!-- Bound Account -->
                  <div>
                    <label
                      for="device-bound-account"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      绑定账号
                      <TipIcon text="绑定后该设备只执行该账号的任务，留空为通用设备" />
                    </label>
                    <select
                      id="device-bound-account"
                      v-model="form.bound_account_id"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option value="">不绑定（通用设备）</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Proxy Config -->
                  <div>
                    <label
                      for="device-proxy"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      代理配置
                      <TipIcon text="JSON 格式代理配置，如 {&quot;server&quot;: &quot;socks5://host:port&quot;, &quot;username&quot;: &quot;user&quot;, &quot;password&quot;: &quot;pass&quot;}" width="w-96" />
                    </label>
                    <textarea
                      id="device-proxy"
                      v-model="form.proxy_config"
                      rows="3"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                      placeholder='{"server": "socks5://user:pass@host:port"}'
                    ></textarea>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除设备"
      :message="`确定要删除设备「${deletingDevice?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
