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
import { formatDate } from '../utils/format.js'

// --- Tab state ---
const activeTab = ref('devices') // "devices" | "pairing"

// --- Data state ---
const devices = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

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

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingDevice = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Table columns ---
const columns = [
  { key: 'name', label: '设备名称' },
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
    console.error('Failed to fetch devices:', e)
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
    console.error('Failed to fetch pair requests:', e)
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
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(device) {
  isEditing.value = true
  editingId.value = device.id
  form.name = device.name || ''
  form.ip = device.ip || ''
  form.bound_account_id = device.bound_account_id != null ? String(device.bound_account_id) : ''
  form.proxy_config = device.proxy_config || ''
  formError.value = null
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
    proxy_config: form.proxy_config.trim() || undefined,
  }

  if (form.bound_account_id.trim()) {
    const n = Number(form.bound_account_id)
    if (!isNaN(n)) payload.bound_account_id = n
  }

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

function connectPairWS() {
  if (ws) return
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${proto}//${window.location.host}/api/devices/ws/pair-events`
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
      }
    } catch (e) {
      console.error('WS message parse error:', e)
    }
  }

  ws.onclose = () => {
    ws = null
    // Reconnect after 3s
    wsReconnectTimer = setTimeout(connectPairWS, 3000)
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function disconnectPairWS() {
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
    <div v-if="pageError" class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-500 hover:text-red-700 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">设备管理</h1>
      <button
        v-if="activeTab === 'devices'"
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
        添加设备
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-gray-200 mb-6">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'devices'
          ? 'border-indigo-600 text-indigo-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
        @click="switchTab('devices')"
      >
        设备列表
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors relative"
        :class="activeTab === 'pairing'
          ? 'border-indigo-600 text-indigo-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
        @click="switchTab('pairing')"
      >
        待配对
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
      <div v-if="pairLoading" class="text-center py-12 text-gray-500">加载中...</div>
      <div v-else-if="pairRequests.length === 0" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="mt-2 text-sm text-gray-500">暂无待配对设备</p>
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="req in pairRequests"
          :key="req.id"
          class="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition-shadow"
        >
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold text-gray-900">{{ req.device_name }}</span>
              <span class="text-xs text-gray-400 font-mono">{{ req.device_id }}</span>
            </div>
            <div class="mt-1 flex items-center gap-4 text-xs text-gray-500">
              <span v-if="req.os_version">系统: {{ req.os_version }}</span>
              <span v-if="req.app_version">版本: {{ req.app_version }}</span>
              <span>申请时间: {{ formatDate(req.created_at) }}</span>
            </div>
          </div>
          <div class="flex gap-2 ml-4">
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md transition-colors disabled:opacity-50"
              :disabled="pairActionLoading === req.id"
              @click="handleApprove(req)"
            >
              {{ pairActionLoading === req.id ? '处理中...' : '批准' }}
            </button>
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-600 bg-white hover:bg-red-50 border border-red-300 rounded-md transition-colors disabled:opacity-50"
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

      <!-- Last seen at column -->
      <template #cell-last_seen_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            v-if="row.status === 'online'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-orange-600 hover:text-orange-800 hover:bg-orange-50 rounded transition-colors disabled:opacity-50"
            :disabled="disconnectingId === row.id"
            @click="handleDisconnect(row)"
          >
            {{ disconnectingId === row.id ? '断开中...' : '断开' }}
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
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
                  {{ isEditing ? '编辑设备' : '添加设备' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded"
                >
                  {{ formError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Name -->
                  <div>
                    <label
                      for="device-name"
                      class="block text-sm font-medium text-gray-700"
                    >
                      设备名称 <span class="text-red-500">*</span>
                    </label>
                    <input
                      id="device-name"
                      v-model="form.name"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入设备名称"
                    />
                  </div>

                  <!-- IP -->
                  <div>
                    <label
                      for="device-ip"
                      class="block text-sm font-medium text-gray-700"
                    >
                      IP 地址
                    </label>
                    <input
                      id="device-ip"
                      v-model="form.ip"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="例如 192.168.1.100"
                    />
                  </div>

                  <!-- Bound Account ID -->
                  <div>
                    <label
                      for="device-bound-account"
                      class="block text-sm font-medium text-gray-700"
                    >
                      绑定账号 ID
                    </label>
                    <input
                      id="device-bound-account"
                      v-model="form.bound_account_id"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入绑定的账号 ID"
                    />
                  </div>

                  <!-- Proxy Config -->
                  <div>
                    <label
                      for="device-proxy"
                      class="block text-sm font-medium text-gray-700"
                    >
                      代理配置
                    </label>
                    <input
                      id="device-proxy"
                      v-model="form.proxy_config"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="例如 socks5://user:pass@host:port"
                    />
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {{ saving ? '保存中...' : '保存' }}
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
